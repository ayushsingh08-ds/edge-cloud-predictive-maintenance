"""
edge/ai/inference.py
--------------------
Anomaly detection inference for CMAPSS FD001 turbofan engines.
Loads trained Isolation Forest model and provides predict_anomaly().

Usage:
    from services.edge.anomaly_detection.inference import predict_anomaly, load_models
    score, is_anomaly = predict_anomaly(features_dict)
"""

import os
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Union

# ── Paths ──────────────────────────────────────────────────────────────────
MODEL_DIR   = Path(__file__).parent / "models"
MODEL_PATH  = MODEL_DIR / "isolation_forest.pkl"
SCALER_PATH = MODEL_DIR / "scaler.pkl"
META_PATH   = MODEL_DIR / "model_metadata.pkl"

# ── Physical sensor names (s1-s21 → real names) ────────────────────────────
SENSOR_NAMES = {
    's2' : 'T24',     's3' : 'T30',     's4' : 'T50',
    's7' : 'P30',     's8' : 'Nf',      's9' : 'Nc',
    's11': 'Ps30',    's12': 'Phi',     's13': 'NRf',
    's14': 'NRc',     's15': 'BPR',     's17': 'htBleed',
    's20': 'W31',     's21': 'W32',
}

GOOD_SENSORS = [
    'T24','T30','T50','P30','Nf','Nc',
    'Ps30','Phi','NRf','NRc','BPR','htBleed','W31','W32'
]

# ── Global model cache (load once, reuse) ──────────────────────────────────
_model  = None
_scaler = None
_meta   = None


def load_models(
    model_path:  Union[str, Path] = MODEL_PATH,
    scaler_path: Union[str, Path] = SCALER_PATH,
    meta_path:   Union[str, Path] = META_PATH,
) -> tuple:
    """
    Load model, scaler and metadata from disk.
    Caches globally so subsequent calls are instant.

    Returns:
        (model, scaler, meta) tuple
    """
    global _model, _scaler, _meta

    if _model is None:
        if not Path(model_path).exists():
            raise FileNotFoundError(f"Model not found: {model_path}")
        if not Path(scaler_path).exists():
            raise FileNotFoundError(f"Scaler not found: {scaler_path}")
        if not Path(meta_path).exists():
            raise FileNotFoundError(f"Metadata not found: {meta_path}")

        with open(model_path,  'rb') as f: _model  = pickle.load(f)
        with open(scaler_path, 'rb') as f: _scaler = pickle.load(f)
        with open(meta_path,   'rb') as f: _meta   = pickle.load(f)

        print(f"[inference] Models loaded.")
        print(f"  Threshold     : {_meta['threshold']:.4f}")
        print(f"  Contamination : {_meta['contamination']}")
        print(f"  Features      : {len(_meta['features'])}")

    return _model, _scaler, _meta


def build_features(
    sensor_readings: dict,
    history:         pd.DataFrame = None,
    window:          int = 15,
) -> np.ndarray:
    """
    Build the full 56-feature vector from raw sensor readings.

    Args:
        sensor_readings: dict of {sensor_name: value} for current cycle
                         e.g. {'T24': 642.5, 'T30': 1590.1, ...}
        history:         DataFrame of past cycles for this engine
                         (needed for rolling stats and baseline deviation)
                         Columns must include all GOOD_SENSORS + 'cycle'
        window:          Rolling window size (default 15, must match training)

    Returns:
        np.ndarray of shape (1, 56) ready for model inference
    """
    _, _, meta = load_models()

    if history is None or len(history) < window:
        # Not enough history — use raw values only, zero-fill engineered features
        # This gives degraded but functional inference during engine warm-up
        raw = [sensor_readings.get(s, 0.0) for s in GOOD_SENSORS]
        engineered = [0.0] * (len(GOOD_SENSORS) * 3)  # roll_mean, roll_std, roc
        baseline   = [0.0] * len(GOOD_SENSORS)         # dev
        cycle_norm = [0.0]
        features   = raw + engineered + baseline + cycle_norm
        return np.array(features).reshape(1, -1)

    # Append current reading to history for rolling calculation
    current_row = pd.DataFrame([sensor_readings])
    full        = pd.concat([history[GOOD_SENSORS], current_row], ignore_index=True)

    features = []

    # 1. Raw sensor values
    features += [sensor_readings.get(s, 0.0) for s in GOOD_SENSORS]

    # 2. Rolling mean
    features += [full[s].rolling(window=window).mean().iloc[-1] for s in GOOD_SENSORS]

    # 3. Rolling std
    features += [full[s].rolling(window=window).std().iloc[-1]  for s in GOOD_SENSORS]

    # 4. Rate of change (current - previous)
    prev = history[GOOD_SENSORS].iloc[-1]
    features += [sensor_readings.get(s, 0.0) - prev[s] for s in GOOD_SENSORS]

    # 5. Baseline deviation (drift from engine's own first 20 cycles)
    baseline_rows = history.head(20)[GOOD_SENSORS]
    baseline_mean = baseline_rows.mean()
    features += [sensor_readings.get(s, 0.0) - baseline_mean[s] for s in GOOD_SENSORS]

    # 6. Normalised cycle
    max_cycle  = len(history) + 1
    cycle_norm = (max_cycle) / max(max_cycle, 1)
    features  += [min(cycle_norm, 1.0)]

    return np.array(features).reshape(1, -1)


def predict_anomaly(
    features: Union[np.ndarray, dict, pd.DataFrame],
    history:  pd.DataFrame = None,
) -> tuple[float, bool]:
    """
    Predict whether current sensor reading is anomalous.

    Args:
        features: One of:
                  - np.ndarray of shape (1, 56) — pre-built feature vector
                  - dict of {sensor_name: value} — raw sensor readings
                    (requires history for full feature engineering)
                  - pd.DataFrame with one row — pre-built feature vector

    Returns:
        (score, is_anomaly)
            score      : float — anomaly score (lower = more anomalous)
                         Threshold is ~0.0222; below = anomaly
            is_anomaly : bool  — True if engine is anomalous

    Example:
        # Using pre-built feature vector
        score, is_anomaly = predict_anomaly(X_scaled_row)

        # Using raw sensor dict (needs history for full features)
        reading = {'T24': 642.5, 'T30': 1598.2, 'T50': 1422.0, ...}
        score, is_anomaly = predict_anomaly(reading, history=engine_history_df)
    """
    model, scaler, meta = load_models()

    # ── Accept multiple input formats ──
    if isinstance(features, dict):
        X = build_features(features, history=history)

    elif isinstance(features, pd.DataFrame):
        X = features[meta['features']].values if hasattr(features, 'columns') \
            else features.values
        if X.ndim == 1:
            X = X.reshape(1, -1)

    elif isinstance(features, np.ndarray):
        X = features.reshape(1, -1) if features.ndim == 1 else features

    else:
        raise TypeError(f"Unsupported features type: {type(features)}")

    # ── Validate shape ──
    expected = len(meta['features'])
    if X.shape[1] != expected:
        raise ValueError(
            f"Expected {expected} features, got {X.shape[1]}. "
            f"Check feature engineering matches training."
        )

    # ── Scale & predict ──
    X_scaled   = scaler.transform(X)
    score      = float(model.decision_function(X_scaled)[0])
    is_anomaly = score < meta['threshold']

    return score, is_anomaly


def predict_batch(
    X: Union[np.ndarray, pd.DataFrame],
) -> tuple[np.ndarray, np.ndarray]:
    """
    Run inference on multiple samples at once.

    Args:
        X: np.ndarray or DataFrame of shape (n_samples, 56)

    Returns:
        (scores, anomaly_flags)
            scores        : np.ndarray of floats, shape (n_samples,)
            anomaly_flags : np.ndarray of bools,  shape (n_samples,)
    """
    model, scaler, meta = load_models()

    if isinstance(X, pd.DataFrame):
        X = X[meta['features']].values

    X_scaled      = scaler.transform(X)
    scores        = model.decision_function(X_scaled)
    anomaly_flags = scores < meta['threshold']

    return scores, anomaly_flags


def get_model_info() -> dict:
    """Return model metadata — useful for logging and monitoring."""
    _, _, meta = load_models()
    return {
        'threshold'    : meta['threshold'],
        'contamination': meta['contamination'],
        'n_features'   : len(meta['features']),
        'precision'    : meta.get('precision'),
        'recall'       : meta.get('recall'),
        'f1'           : meta.get('f1'),
        'dataset'      : meta.get('dataset'),
    }


# ── Test / demo ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import time

    print("=" * 55)
    print("  Anomaly Inference — Test Suite")
    print("=" * 55)

    # ── Load test data to get real samples ──
    DATA_DIR = Path(__file__).parent.parent.parent / "dataset"

    COLS = [
        'engine_id', 'cycle', 'op1', 'op2', 'op3',
        's1','s2','s3','s4','s5','s6','s7','s8','s9','s10',
        's11','s12','s13','s14','s15','s16','s17','s18','s19','s20','s21'
    ]

    RENAME = {
        's2':'T24','s3':'T30','s4':'T50','s7':'P30','s8':'Nf','s9':'Nc',
        's11':'Ps30','s12':'Phi','s13':'NRf','s14':'NRc','s15':'BPR',
        's17':'htBleed','s20':'W31','s21':'W32'
    }

    # Load test set
    test = pd.read_csv(DATA_DIR / "test_FD001.txt", sep=' ', header=None)
    test = test.dropna(axis=1)
    test.columns = COLS
    test = test.rename(columns=RENAME)

    # Add RUL
    rul_final = pd.read_csv(DATA_DIR / "RUL_FD001.txt", header=None, names=['rul_final'])
    rul_final['engine_id'] = rul_final.index + 1
    max_cycles = test.groupby('engine_id')['cycle'].max().reset_index()
    max_cycles.columns = ['engine_id', 'max_cycle']
    test = test.merge(max_cycles, on='engine_id').merge(rul_final, on='engine_id')
    test['rul'] = test['rul_final'] + (test['max_cycle'] - test['cycle'])
    test['label'] = (test['rul'] <= 30).astype(int)

    # ── Feature engineering ──
    def engineer(df):
        dfs = []
        for eid in df['engine_id'].unique():
            e = df[df['engine_id'] == eid].copy()
            baseline = e[GOOD_SENSORS].head(20).mean()
            for s in GOOD_SENSORS:
                e[f'{s}_roll_mean'] = e[s].rolling(15).mean()
                e[f'{s}_roll_std']  = e[s].rolling(15).std()
                e[f'{s}_roc']       = e[s].diff()
                e[f'{s}_dev']       = e[s] - baseline[s]
            e['cycle_norm'] = e['cycle'] / e['cycle'].max()
            dfs.append(e)
        return pd.concat(dfs).dropna().reset_index(drop=True)

    print("\nEngineering features for test set...")
    test_fe = engineer(test)

    # ── Test 1: Single sample inference ──
    print("\n── Test 1: Single sample predict_anomaly() ──")
    _, _, meta = load_models()

    sample_normal  = test_fe[test_fe['label'] == 0].iloc[0]
    sample_anomaly = test_fe[test_fe['label'] == 1].iloc[0]

    for label, row in [('NORMAL', sample_normal), ('ANOMALY', sample_anomaly)]:
        X = row[meta['features']].values.reshape(1, -1)
        start = time.perf_counter()
        score, is_anomaly = predict_anomaly(X)
        elapsed = (time.perf_counter() - start) * 1000

        print(f"  [{label:7s}]  score={score:+.4f}  "
              f"is_anomaly={str(is_anomaly):5s}  "
              f"correct={is_anomaly == (label=='ANOMALY')}  "
              f"time={elapsed:.3f}ms")

    # ── Test 2: Batch inference ──
    print("\n── Test 2: Batch predict_batch() — 100 samples ──")
    sample_batch = test_fe.sample(100, random_state=42)
    X_batch      = sample_batch[meta['features']].values

    start  = time.perf_counter()
    scores, flags = predict_batch(X_batch)
    elapsed = (time.perf_counter() - start) * 1000

    correct = (flags == sample_batch['label'].values).sum()
    print(f"  Samples   : 100")
    print(f"  Correct   : {correct}/100")
    print(f"  Anomalies : {flags.sum()} flagged")
    print(f"  Time      : {elapsed:.2f}ms total  ({elapsed/100:.3f}ms per sample)")

    # ── Test 3: Score distribution ──
    print("\n── Test 3: Score distribution on full test set ──")
    X_full         = test_fe[meta['features']].values
    scores_all, _  = predict_batch(X_full)

    normal_scores  = scores_all[test_fe['label'].values == 0]
    anomaly_scores = scores_all[test_fe['label'].values == 1]

    print(f"  Normal  scores  — mean: {normal_scores.mean():+.4f}  "
          f"std: {normal_scores.std():.4f}  "
          f"min: {normal_scores.min():+.4f}")
    print(f"  Anomaly scores  — mean: {anomaly_scores.mean():+.4f}  "
          f"std: {anomaly_scores.std():.4f}  "
          f"min: {anomaly_scores.min():+.4f}")
    print(f"  Threshold       : {meta['threshold']:+.4f}")
    print(f"  Separation      : {normal_scores.mean() - anomaly_scores.mean():.4f}")

    # ── Test 4: Model info ──
    print("\n── Test 4: Model info ──")
    info = get_model_info()
    for k, v in info.items():
        print(f"  {k:15s}: {v}")

    print("\n" + "=" * 55)
    print("  All tests complete")
    print("=" * 55)
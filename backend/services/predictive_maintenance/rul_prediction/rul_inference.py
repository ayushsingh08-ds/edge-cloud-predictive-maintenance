"""RUL inference utilities.

Provides a single public function:
    predict_rul(sequence) -> (hours, confidence, status)

Status mapping:
- healthy : RUL >= 72
- warning : 24 <= RUL < 72
- critical: RUL < 24
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Tuple

import numpy as np

# Cached artifacts to avoid reloading for every prediction.
_MODEL = None
_SCALER = None

# Health thresholds in hours.
HEALTHY_HOURS = 72.0
WARNING_HOURS = 24.0

MODEL_PATH = Path(__file__).parent.parent / "model_registry" / "rul_lstm.h5"
SCALER_PATH = Path(__file__).parent.parent / "model_registry" / "scaler.pkl"


def _load_artifacts():
    """Load and cache the trained RUL model + scaler from disk."""
    global _MODEL, _SCALER

    if _MODEL is not None and _SCALER is not None:
        return _MODEL, _SCALER

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"RUL model not found: {MODEL_PATH}")
    if not SCALER_PATH.exists():
        raise FileNotFoundError(f"RUL scaler not found: {SCALER_PATH}")

    try:
        from tensorflow.keras.models import load_model
    except Exception as exc:
        raise ImportError(
            "TensorFlow is required for RUL inference. Install tensorflow in the runtime environment."
        ) from exc

    _MODEL = load_model(MODEL_PATH)
    with open(SCALER_PATH, "rb") as f:
        _SCALER = pickle.load(f)

    return _MODEL, _SCALER


def _to_3d_array(sequence: np.ndarray | list) -> np.ndarray:
    """Normalize input sequence to shape (1, timesteps, features)."""
    arr = np.asarray(sequence, dtype=np.float32)

    if arr.ndim == 2:
        # (timesteps, features)
        arr = np.expand_dims(arr, axis=0)
    elif arr.ndim == 3:
        # Allow only one sample for this helper function.
        if arr.shape[0] != 1:
            raise ValueError(
                f"predict_rul expects one sequence. Got batch size {arr.shape[0]}."
            )
    else:
        raise ValueError(
            "sequence must have shape (timesteps, features) or (1, timesteps, features)."
        )

    return arr


def _status_from_hours(hours: float) -> str:
    """Map predicted RUL to health status."""
    if hours >= HEALTHY_HOURS:
        return "healthy"
    if hours >= WARNING_HOURS:
        return "warning"
    return "critical"


def _confidence_from_hours(hours: float) -> float:
    """Heuristic confidence based on distance from decision boundaries.

    Confidence increases as prediction moves farther from 24h and 72h boundaries.
    Returns value in [0.50, 0.99].
    """
    distance = min(abs(hours - WARNING_HOURS), abs(hours - HEALTHY_HOURS))
    confidence = 0.50 + min(distance / 96.0, 0.49)
    return float(np.clip(confidence, 0.50, 0.99))


def predict_rul(sequence: np.ndarray | list) -> Tuple[float, float, str]:
    """Predict remaining useful life from one sensor sequence.

    Args:
        sequence: Sensor sequence shaped as (50, features) or (1, 50, features).

    Returns:
        (hours, confidence, status)
            hours: float predicted RUL in hours/cycles (non-negative)
            confidence: float in [0.0, 1.0]
            status: one of {'healthy', 'warning', 'critical'}
    """
    model, scaler = _load_artifacts()
    x = _to_3d_array(sequence)

    if x.shape[1] != 50:
        raise ValueError(f"Expected 50 timesteps, got {x.shape[1]}.")

    n_features = x.shape[2]

    # Apply same feature scaling used during model training.
    x_scaled = scaler.transform(x.reshape(-1, n_features)).reshape(1, x.shape[1], n_features)

    pred = model.predict(x_scaled, verbose=0)
    hours = float(max(0.0, float(pred.reshape(-1)[0])))

    status = _status_from_hours(hours)
    confidence = _confidence_from_hours(hours)

    return hours, confidence, status

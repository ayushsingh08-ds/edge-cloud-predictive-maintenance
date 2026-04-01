from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd

CMAPSS_COLUMNS = [
    "unit_nr",
    "time_cycles",
    "op_setting_1",
    "op_setting_2",
    "op_setting_3",
] + [f"s_{i}" for i in range(1, 22)]

KEY_SENSORS = ["s_2", "s_3", "s_4", "s_7", "s_11", "s_12", "s_15", "s_20", "s_21"]


@dataclass
class RULModelArtifacts:
    model: lgb.LGBMRegressor
    feature_columns: list[str]
    metrics: dict[str, float]
    shap_importance: list[dict[str, float]]


class RULPredictor:
    def __init__(self, artifacts: RULModelArtifacts) -> None:
        self.artifacts = artifacts

    def predict(self, feature_frame: pd.DataFrame) -> pd.DataFrame:
        frame = feature_frame.copy()
        frame = frame[self.artifacts.feature_columns]
        rul_pred = self.artifacts.model.predict(frame)

        output = feature_frame.copy()
        output["rul_pred"] = rul_pred
        output["health_index"] = compute_health_index(output["rul_pred"])
        return output


def load_cmapss_train(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"C-MAPSS file not found: {path}")

    frame = pd.read_csv(
        path,
        sep=r"\s+",
        header=None,
        names=CMAPSS_COLUMNS,
        engine="python",
    )

    max_cycles = frame.groupby("unit_nr")["time_cycles"].transform("max")
    frame["rul"] = max_cycles - frame["time_cycles"]
    return frame


def build_features(frame: pd.DataFrame, rolling_window: int = 5) -> pd.DataFrame:
    df = frame.sort_values(["unit_nr", "time_cycles"]).copy()

    for sensor in KEY_SENSORS:
        grp = df.groupby("unit_nr")[sensor]
        df[f"{sensor}_roll_mean"] = grp.transform(
            lambda x: x.rolling(rolling_window, min_periods=1).mean()
        )
        df[f"{sensor}_roll_std"] = grp.transform(
            lambda x: x.rolling(rolling_window, min_periods=1).std().fillna(0.0)
        )
        df[f"{sensor}_lag1"] = grp.shift(1).bfill().fillna(0.0)
        df[f"{sensor}_slope"] = grp.diff().fillna(0.0)

    df["cycle_ratio"] = df["time_cycles"] / df.groupby("unit_nr")["time_cycles"].transform("max")
    return df


def _compute_shap_importance(model: lgb.LGBMRegressor, x: pd.DataFrame) -> list[dict[str, float]]:
    try:
        import shap

        explainer = shap.TreeExplainer(model)
        sample = x.sample(n=min(len(x), 500), random_state=42)
        shap_values = explainer.shap_values(sample)

        if isinstance(shap_values, list):
            values = np.asarray(shap_values[0])
        else:
            values = np.asarray(shap_values)

        importance = np.abs(values).mean(axis=0)
        pairs = list(zip(sample.columns.tolist(), importance.tolist()))
        pairs.sort(key=lambda item: item[1], reverse=True)
        return [
            {"feature": feature, "mean_abs_shap": float(score)}
            for feature, score in pairs[:20]
        ]
    except Exception:
        return []


def compute_health_index(rul: pd.Series | np.ndarray) -> np.ndarray:
    arr = np.asarray(rul, dtype=float)
    arr = np.clip(arr, 0.0, None)
    max_val = max(float(arr.max()), 1.0)
    return np.clip(arr / max_val, 0.0, 1.0)


def train_rul_model(frame: pd.DataFrame) -> RULModelArtifacts:
    df = build_features(frame)

    excluded = {"rul", "unit_nr", "time_cycles"}
    feature_columns = [col for col in df.columns if col not in excluded]

    units = sorted(df["unit_nr"].unique().tolist())
    split_idx = int(len(units) * 0.8)
    train_units = set(units[:split_idx])

    train_df = df[df["unit_nr"].isin(train_units)]
    valid_df = df[~df["unit_nr"].isin(train_units)]

    x_train = train_df[feature_columns]
    y_train = train_df["rul"]
    x_valid = valid_df[feature_columns]
    y_valid = valid_df["rul"]

    model = lgb.LGBMRegressor(
        n_estimators=450,
        learning_rate=0.03,
        num_leaves=64,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="regression",
        random_state=42,
    )

    model.fit(
        x_train,
        y_train,
        eval_set=[(x_valid, y_valid)],
        eval_metric="l2",
    )

    pred = model.predict(x_valid)
    rmse = float(np.sqrt(np.mean((pred - y_valid.to_numpy()) ** 2)))
    mae = float(np.mean(np.abs(pred - y_valid.to_numpy())))

    shap_importance = _compute_shap_importance(model, x_valid)

    return RULModelArtifacts(
        model=model,
        feature_columns=feature_columns,
        metrics={"rmse": rmse, "mae": mae},
        shap_importance=shap_importance,
    )


def rul_prediction_api(artifacts: RULModelArtifacts, payload: pd.DataFrame) -> dict[str, Any]:
    predictor = RULPredictor(artifacts)
    predicted = predictor.predict(payload)

    records = predicted[["unit_nr", "time_cycles", "rul_pred", "health_index"]].head(20)
    return {"predictions": records.to_dict(orient="records")}

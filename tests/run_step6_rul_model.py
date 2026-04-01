from __future__ import annotations

import sys
from pathlib import Path
from random import Random

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.cloud_ai.rul_pipeline import (
    CMAPSS_COLUMNS,
    KEY_SENSORS,
    build_features,
    load_cmapss_train,
    rul_prediction_api,
    train_rul_model,
)


def generate_synthetic_cmapss(seed: int = 42) -> pd.DataFrame:
    rng = Random(seed)
    rows: list[dict[str, float | int]] = []

    for unit in range(1, 41):
        max_cycle = rng.randint(120, 260)
        degradation = rng.uniform(0.02, 0.08)

        for cycle in range(1, max_cycle + 1):
            row: dict[str, float | int] = {
                "unit_nr": unit,
                "time_cycles": cycle,
                "op_setting_1": rng.uniform(-1.0, 1.0),
                "op_setting_2": rng.uniform(-1.0, 1.0),
                "op_setting_3": rng.uniform(-1.0, 1.0),
            }
            for idx in range(1, 22):
                sensor_name = f"s_{idx}"
                base = 100.0 + rng.uniform(-4.0, 4.0)
                drift = degradation * cycle * (0.6 if sensor_name in KEY_SENSORS else 0.2)
                noise = rng.uniform(-1.5, 1.5)
                row[sensor_name] = base + drift + noise
            rows.append(row)

    frame = pd.DataFrame(rows, columns=CMAPSS_COLUMNS)
    max_cycles = frame.groupby("unit_nr")["time_cycles"].transform("max")
    frame["rul"] = max_cycles - frame["time_cycles"]
    return frame


def main() -> None:
    cmapss_file = ROOT_DIR / "data" / "cmapss" / "train_FD001.txt"
    if cmapss_file.exists():
        df = load_cmapss_train(cmapss_file)
        data_source = str(cmapss_file)
    else:
        df = generate_synthetic_cmapss(seed=11)
        data_source = "synthetic_cmapss_fallback"

    artifacts = train_rul_model(df)
    featured = build_features(df)
    payload = featured.head(50)
    api_result = rul_prediction_api(artifacts, payload)

    print("STEP 6 - Predictive Maintenance RUL Model")
    print("data_source:", data_source)
    print("metrics:", artifacts.metrics)
    print("feature_count:", len(artifacts.feature_columns))
    print("prediction_sample_size:", len(api_result["predictions"]))

    if artifacts.shap_importance:
        print("top_shap_feature:", artifacts.shap_importance[0])
    else:
        print("top_shap_feature: unavailable (install shap for feature attribution)")


if __name__ == "__main__":
    main()

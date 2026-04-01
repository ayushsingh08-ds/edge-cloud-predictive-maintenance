from __future__ import annotations

import sys
from pathlib import Path
from random import Random

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.cloud_ai.rul_pipeline import CMAPSS_COLUMNS, train_rul_model


def make_small_dataset(seed: int = 3) -> pd.DataFrame:
    rng = Random(seed)
    rows: list[dict[str, float | int]] = []

    for unit in range(1, 11):
        max_cycle = rng.randint(80, 120)
        for cycle in range(1, max_cycle + 1):
            row: dict[str, float | int] = {
                "unit_nr": unit,
                "time_cycles": cycle,
                "op_setting_1": rng.uniform(-1.0, 1.0),
                "op_setting_2": rng.uniform(-1.0, 1.0),
                "op_setting_3": rng.uniform(-1.0, 1.0),
            }
            for idx in range(1, 22):
                row[f"s_{idx}"] = 80.0 + 0.03 * cycle + rng.uniform(-0.6, 0.6)
            rows.append(row)

    frame = pd.DataFrame(rows, columns=CMAPSS_COLUMNS)
    max_cycles = frame.groupby("unit_nr")["time_cycles"].transform("max")
    frame["rul"] = max_cycles - frame["time_cycles"]
    return frame


def test_step6_rul_training_runs() -> None:
    frame = make_small_dataset()
    artifacts = train_rul_model(frame)

    assert artifacts.metrics["rmse"] >= 0.0
    assert artifacts.metrics["mae"] >= 0.0
    assert len(artifacts.feature_columns) > 0

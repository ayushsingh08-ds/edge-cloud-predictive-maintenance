# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray


SENSOR_COLUMNS = [
	"Vibration_Level",
	"Temperature_Readings",
	"Pressure_Data",
	"Acoustic_Signals",
	"Humidity_Levels",
	"Motor_Speed",
	"Torque_Data",
	"Machine_Load_Percentage",
	"Component_Degradation_Index",
	"Machine_Health_Index",
]

# Features produced by simulation.machine.Machine.sensor_payload()
SIM_SENSOR_FEATURE_SCHEMA = [
	"temperature",
	"vibration",
	"pressure",
	"speed",
	"load",
	"flow",
	"humidity",
	"wear",
	"health",
	"operating_time",
]

SIM_SENSOR_TO_DATASET = {
	"temperature": "Temperature_Readings",
	"vibration": "Vibration_Level",
	"pressure": "Pressure_Data",
	"speed": "Motor_Speed",
	"load": "Machine_Load_Percentage",
	"flow": "Production_Rate",
	"humidity": "Humidity_Levels",
	"wear": "Component_Degradation_Index",
	"health": "Machine_Health_Index",
	"operating_time": "Cycle_Time_Per_Operation",
}

OPERATING_COLUMNS = [
	"Energy_Consumption",
	"Production_Rate",
	"Tool_Wear_Rate",
	"Machine_Utilization_Rate",
	"Cycle_Time_Per_Operation",
	"Idle_Time",
	"Ambient_Temperature",
	"Humidity",
	"Air_Quality_Index",
	"Controller_Setpoints",
	"Actual_vs_Setpoint_Values",
	"Operator_Shift_Data",
]

EVENT_COLUMNS = [
	"Machine_Start_Stop_Events",
	"Maintenance_Logs",
	"Downtime_Incidents",
	"Fault_Trigger_Timestamps",
	"Failure_Mode_Indicators",
	"Repair_Logs",
]


def derive_machine_ids(df: pd.DataFrame, records_per_machine: int = 200) -> pd.DataFrame:
	"""Create pseudo machine ids when the dataset has no explicit machine identifier."""
	output = df.copy()
	output["Machine_ID"] = (np.arange(len(output)) // records_per_machine) + 1
	return output


def infer_run_ids_from_events(
	df: pd.DataFrame,
	timestamp_col: str,
	min_gap_minutes: int = 180,
	event_break_score: int = 3,
) -> pd.DataFrame:
	"""Infer lifecycle runs when no explicit machine id exists.

	A new run starts when:
	- a start/stop event fires,
	- the previous row indicates a failure/repair/downtime/maintenance event,
	- or there is a large timestamp gap.
	"""
	output = df.copy()
	for col in EVENT_COLUMNS:
		if col not in output.columns:
			output[col] = 0

	output = output.sort_values(timestamp_col).reset_index(drop=True)
	time_gap = output[timestamp_col].diff().dt.total_seconds().div(60.0).fillna(0.0)
	event_score = output[EVENT_COLUMNS].fillna(0).sum(axis=1)
	run_break = (time_gap >= float(min_gap_minutes)) | (event_score >= int(event_break_score))
	run_break.iloc[0] = True

	output["Machine_ID"] = run_break.astype(int).cumsum().astype(int)
	output["Run_ID"] = output["Machine_ID"].astype(str).radd("RUN_")
	return output


def choose_machine_column(df: pd.DataFrame) -> str | None:
	for candidate in ["Machine_ID", "machine_id", "UnitNumber", "unit", "Engine_ID"]:
		if candidate in df.columns:
			return candidate
	return None


def choose_timestamp_column(df: pd.DataFrame) -> str | None:
	for candidate in ["Timestamp", "timestamp", "Datetime", "DateTime", "date"]:
		if candidate in df.columns:
			return candidate
	return None


def standardize(
	train_df: pd.DataFrame, test_df: pd.DataFrame, feature_cols: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, dict[str, float]]]:
	train_scaled = train_df.copy()
	test_scaled = test_df.copy()

	mean = train_scaled[feature_cols].mean()
	std = train_scaled[feature_cols].std().replace(0, 1.0)
	scaling_stats = {
		column: {"mean": float(mean[column]), "std": float(std[column])}
		for column in feature_cols
	}

	train_scaled[feature_cols] = (train_scaled[feature_cols] - mean) / std
	test_scaled[feature_cols] = (test_scaled[feature_cols] - mean) / std
	return train_scaled, test_scaled, scaling_stats


def build_windows(
	df: pd.DataFrame, machine_col: str, feature_cols: list[str], window_size: int
) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
	X: list[NDArray[np.float32]] = []
	y: list[float] = []

	for _, group in df.groupby(machine_col):
		group_sorted = group.sort_values("cycle")
		values = group_sorted[feature_cols].to_numpy(dtype=np.float32)
		labels = group_sorted["RUL"].to_numpy(dtype=np.float32)

		if len(group_sorted) < window_size:
			continue

		for idx in range(window_size - 1, len(group_sorted)):
			X.append(values[idx - window_size + 1 : idx + 1])
			y.append(labels[idx])

	if not X:
		return (
			np.empty((0, window_size, len(feature_cols)), dtype=np.float32),
			np.empty((0,), dtype=np.float32),
		)

	return np.stack(X).astype(np.float32), np.array(y, dtype=np.float32)


def preprocess_rul_dataset(
	dataset_path: Path,
	output_dir: Path,
	window_size: int = 30,
	train_split_ratio: float = 0.8,
	records_per_machine: int = 200,
	event_break_score: int = 3,
	feature_mode: str = "sensor_simulation",
) -> dict[str, Any]:
	df = pd.read_csv(dataset_path)

	timestamp_col = choose_timestamp_column(df)
	if timestamp_col is not None:
		df[timestamp_col] = pd.to_datetime(df[timestamp_col], errors="coerce")
		df = df.dropna(subset=[timestamp_col])

	machine_col = choose_machine_column(df)
	inference_method = "provided_machine_id"
	if machine_col is None and timestamp_col is not None:
		df = infer_run_ids_from_events(df, timestamp_col=timestamp_col, event_break_score=event_break_score)
		machine_col = "Machine_ID"
		inference_method = "event_based_run_segmentation"
		usable_runs = int((df.groupby(machine_col).size() >= window_size).sum())
		if usable_runs < 20:
			df = derive_machine_ids(df, records_per_machine=records_per_machine)
			machine_col = "Machine_ID"
			inference_method = "fixed_record_chunking_fallback"
	elif machine_col is None:
		df = derive_machine_ids(df, records_per_machine=records_per_machine)
		machine_col = "Machine_ID"
		inference_method = "fixed_record_chunking_fallback"

	if timestamp_col is not None:
		df = df.sort_values([machine_col, timestamp_col]).reset_index(drop=True)
	else:
		df = df.sort_values([machine_col]).reset_index(drop=True)

	df["cycle"] = df.groupby(machine_col).cumcount() + 1
	df = df[df.groupby(machine_col)["cycle"].transform("max") >= window_size].copy()
	max_cycle = df.groupby(machine_col)["cycle"].transform("max")
	df["RUL"] = (max_cycle - df["cycle"]).astype(np.float32)
	rul_mean = float(df["RUL"].mean())
	rul_std = float(df["RUL"].std())
	if rul_std == 0.0:
		rul_std = 1.0

	feature_cols: list[str]
	serving_features: list[str] = []
	feature_mapping_used: dict[str, str] = {}
	if feature_mode == "sensor_simulation":
		for serving_feature in SIM_SENSOR_FEATURE_SCHEMA:
			dataset_col = SIM_SENSOR_TO_DATASET.get(serving_feature)
			if dataset_col is not None and dataset_col in df.columns:
				serving_features.append(serving_feature)
				feature_mapping_used[serving_feature] = dataset_col
		feature_cols = [feature_mapping_used[name] for name in serving_features]
	else:
		feature_cols = [col for col in (SENSOR_COLUMNS + OPERATING_COLUMNS) if col in df.columns]
	if not feature_cols:
		numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
		feature_cols = [col for col in numeric_cols if col not in {"RUL", "cycle"}]
		if not serving_features:
			serving_features = list(feature_cols)

	machine_ids = sorted(df[machine_col].unique().tolist())
	split_idx = max(1, int(len(machine_ids) * train_split_ratio))
	if split_idx >= len(machine_ids):
		split_idx = max(1, len(machine_ids) - 1)

	train_ids = set(machine_ids[:split_idx])
	test_ids = set(machine_ids[split_idx:])

	train_df = df[df[machine_col].isin(train_ids)].copy()
	test_df = df[df[machine_col].isin(test_ids)].copy()

	train_df, test_df, feature_scaling = standardize(train_df, test_df, feature_cols)
	serving_feature_scaling = dict(feature_scaling)
	if serving_features and feature_mapping_used:
		serving_feature_scaling = {
			serving_name: dict(feature_scaling.get(dataset_col, {"mean": 0.0, "std": 1.0}))
			for serving_name, dataset_col in feature_mapping_used.items()
		}

	X_train, y_train = build_windows(train_df, machine_col, feature_cols, window_size)
	X_test, y_test = build_windows(test_df, machine_col, feature_cols, window_size)

	output_dir.mkdir(parents=True, exist_ok=True)
	np.save(output_dir / "X_train.npy", X_train)
	np.save(output_dir / "y_train.npy", y_train)
	np.save(output_dir / "X_test.npy", X_test)
	np.save(output_dir / "y_test.npy", y_test)

	metadata = {
		"dataset_path": str(dataset_path),
		"machine_column": machine_col,
		"machine_id_inference": inference_method,
		"timestamp_column": timestamp_col,
		"event_break_score": event_break_score,
		"feature_mode": feature_mode,
		"serving_features": serving_features,
		"feature_mapping": feature_mapping_used,
		"window_size": window_size,
		"feature_count": len(feature_cols),
		"features": feature_cols,
		"train_machines": len(train_ids),
		"test_machines": len(test_ids),
		"X_train_shape": list(X_train.shape),
		"y_train_shape": list(y_train.shape),
		"X_test_shape": list(X_test.shape),
		"y_test_shape": list(y_test.shape),
		"feature_scaling": serving_feature_scaling,
		"target_scaling": {
			"name": "standard_score",
			"mean": rul_mean,
			"std": rul_std,
		},
	}
	(output_dir / "preprocessing_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
	(output_dir / "feature_schema.json").write_text(
		json.dumps(
			{
				"feature_mode": feature_mode,
				"serving_features": serving_features,
				"dataset_features": feature_cols,
				"feature_mapping": feature_mapping_used,
				"feature_scaling": serving_feature_scaling,
				"window_size": window_size,
			},
			indent=2,
		),
		encoding="utf-8",
	)
	return metadata


def main() -> None:
	project_root = Path(__file__).resolve().parents[1]
	dataset_path = project_root / "data" / "IndFD-PM-DT" / "IndFD-PM-DT dataset.csv"
	output_dir = project_root / "data" / "predictions"

	metadata = preprocess_rul_dataset(
		dataset_path=dataset_path,
		output_dir=output_dir,
		window_size=30,
		train_split_ratio=0.8,
		records_per_machine=200,
		event_break_score=3,
		feature_mode="sensor_simulation",
	)
	print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
	main()

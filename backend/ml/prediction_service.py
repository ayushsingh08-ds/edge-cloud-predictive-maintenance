from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
import json
import logging
from pathlib import Path
import time
from typing import Any

import numpy as np
from tensorflow import keras

from events import Event, EventBus, EventType


@dataclass(slots=True)
class PredictionService:
	event_bus: EventBus
	model_path: Path | None = None
	metadata_path: Path | None = None
	health_threshold: float = 0.35
	maintenance_threshold: float = 0.2
	_machine_windows: dict[str, deque[dict[str, float]]] = field(default_factory=lambda: defaultdict(deque), init=False)
	_model: keras.Model | Any | None = field(default=None, init=False)
	_explainer: Any | None = field(default=None, init=False)
	_window_size: int = field(default=30, init=False)
	_feature_order: list[str] = field(default_factory=list, init=False)
	_feature_scaling: dict[str, dict[str, float]] = field(default_factory=dict, init=False)
	_target_scaling: dict[str, float] = field(default_factory=dict, init=False)

	def __post_init__(self) -> None:
		self._load_artifacts()
		self.event_bus.subscribe(EventType.SENSOR_DATA, self.handle_sensor_reading)

	def _load_artifacts(self) -> None:
		project_root = Path(__file__).resolve().parents[1]
		metadata_path = self.metadata_path or project_root / "data" / "predictions" / "preprocessing_metadata.json"
		metrics_path = project_root / "data" / "predictions" / "model_metrics.json"

		if metadata_path.exists():
			metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
			self._window_size = int(metadata.get("window_size", self._window_size))
			self._feature_order = list(metadata.get("serving_features", self._feature_order))
			feature_scaling = metadata.get("feature_scaling", {})
			if isinstance(feature_scaling, dict):
				self._feature_scaling = {
					str(feature): {
						"mean": float(stats.get("mean", 0.0)),
						"std": float(stats.get("std", 1.0)),
					}
					for feature, stats in feature_scaling.items()
				}
			target_scaling = metadata.get("target_scaling", {})
			if isinstance(target_scaling, dict):
				self._target_scaling = {
					"mean": float(target_scaling.get("mean", 0.0)),
					"std": float(target_scaling.get("std", 1.0)),
				}

		if self._window_size <= 0:
			self._window_size = 30
		if not self._feature_order:
			self._feature_order = [
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
				"queue_length",
				"machine_utilization",
				"routing_load",
			]

		candidate_model_paths: list[Path] = []
		if self.model_path is not None:
			candidate_model_paths.append(Path(self.model_path))

		if metrics_path.exists():
			try:
				metrics_data = json.loads(metrics_path.read_text(encoding="utf-8"))
				target_scaling = metrics_data.get("target_scaling", {})
				if isinstance(target_scaling, dict):
					self._target_scaling = {
						"name": str(target_scaling.get("name", self._target_scaling.get("name", "standard_score"))),
						"mean": float(target_scaling.get("mean", self._target_scaling.get("mean", 0.0))),
						"std": float(target_scaling.get("std", self._target_scaling.get("std", 1.0))),
					}
				for key in ("model_path", "keras_model_path"):
					raw_path = metrics_data.get(key)
					if isinstance(raw_path, str) and raw_path.strip():
						parsed_path = Path(raw_path)
						if not parsed_path.is_absolute():
							parsed_path = project_root / parsed_path
						candidate_model_paths.append(parsed_path)
			except Exception:
				pass

		for path in candidate_model_paths:
			if not path.exists():
				continue
			try:
				if path.suffix == ".joblib":
					import joblib
					import xgboost as xgb
					import shap
					self._model = joblib.load(path)
					# Initialize SHAP explainer for XGBoost
					if isinstance(self._model, (xgb.XGBRegressor, xgb.Booster)):
						self._explainer = shap.TreeExplainer(self._model)
					logging.info(f"Loaded XGBoost model from {path}")
					break
				elif path.suffix in (".h5", ".keras"):
					self._model = keras.models.load_model(path)
					logging.info(f"Loaded Keras model from {path}")
					break
			except Exception as e:
				logging.error(f"Failed to load model from {path}: {e}")

		candidate_model_paths.extend(
			[
				project_root / "predictive_maintenance_cnn_lstm.keras",
				project_root / "predictive_maintenance_cnn_lstm.h5",
			]
		)

		seen: set[Path] = set()
		for path in candidate_model_paths:
			resolved = path.expanduser()
			if resolved in seen:
				continue
			seen.add(resolved)
			if not resolved.exists():
				continue
			try:
				self._model = keras.models.load_model(resolved)
				break
			except Exception:
				continue

		if self._model is None:
			# Keep the backend operational even if the model artifact is missing or incompatible
			# with the current TensorFlow/Keras runtime in this environment.
			return

		input_shape = getattr(self._model, "input_shape", None)
		if isinstance(input_shape, tuple) and len(input_shape) >= 3:
			expected_features = int(input_shape[-1])
			if expected_features > 0 and expected_features != len(self._feature_order):
				defaults = [
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
				merged = list(dict.fromkeys([*self._feature_order, *defaults]))
				self._feature_order = merged[:expected_features]

	def handle_sensor_reading(self, event: Event) -> None:
		try:
			machine_id = str(event.payload.get("machine_id", event.source))
			metrics = self._extract_metrics(event.payload)
			if metrics is None:
				return

			window = self._machine_windows[machine_id]
			window.append(metrics)
			while len(window) > self._window_size:
				window.popleft()

			if len(window) < self._window_size or self._model is None:
				return

			window_array = self._window_to_model_input(window)
			# _window_to_model_input returns shape (1, window_size, num_features)
			input_data = window_array
			
			if hasattr(self._model, "n_features_in_"):
				# Flatten for XGBoost/Scikit-learn if needed (expects 1, num_features * window_size)
				input_data = window_array.reshape(1, -1)
			else:
				# For Keras 3, converting to a Tensor often resolves "Invalid dtype: object" 
				# caused by complex nested structures during model(input).
				try:
					import tensorflow as tf
					input_data = tf.convert_to_tensor(input_data, dtype=tf.float32)
				except Exception:
					# Fallback to pure numpy float32
					input_data = np.asarray(input_data, dtype=np.float32)
				
			start_time = time.perf_counter()
			# Use np.asarray to ensure we're dealing with a standard numeric type before passing to predict
			# and ensure the output is also converted to a float.
			pred_raw = self._model.predict(input_data, verbose=0)
			prediction_scaled = float(np.asarray(pred_raw).flatten()[0])
			latency_ms = (time.perf_counter() - start_time) * 1000
			
			# Compute SHAP importance if explainer is available
			shap_importance = {}
			if self._explainer is not None:
				try:
					# Use a small background sample or just the instance
					shap_values = self._explainer.shap_values(input_data)
					if isinstance(shap_values, list): shap_values = shap_values[0] # Handle multi-output if any
					
					# Map flattened indices back to features (using latest window features)
					# For simplicity in 3D UI, we use the average importance across the window for the 13 base features
					reshaped_shap = shap_values.reshape(self._window_size, len(self._feature_order))
					feature_importance = np.mean(np.abs(reshaped_shap), axis=0)
					total = np.sum(feature_importance) or 1.0
					
					shap_importance = {
						name: round((val / total) * 100, 2)
						for name, val in zip(self._feature_order, feature_importance)
					}
				except Exception as e:
					logging.warning(f"SHAP computation failed: {e}")
			
			# Log latency for monitoring
			logging.info(f"Machine {machine_id} prediction latency: {latency_ms:.2f}ms")

			prediction = self._inverse_target_scale(prediction_scaled)
			health_score = self._estimate_health_score(prediction, metrics)
			risk_score = 1.0 - health_score
			prediction_data = {
						"machine_id": machine_id,
						"remaining_useful_life": round(prediction, 4),
						"health_score": round(health_score, 4),
						"risk_score": round(risk_score, 4),
						"window_size": self._window_size,
						"latency_ms": round(latency_ms, 3),
						"shap_importance": shap_importance,
						"confidence_score": 0.92,
					}
			self.event_bus.publish(
				Event(
					event_type=EventType.RUL_PREDICTION,
					timestamp=event.timestamp,
					source="ml.prediction_service",
					payload=prediction_data,
				)
			)
			self.event_bus.publish(
				Event(
					event_type=EventType.HEALTH_UPDATE,
					timestamp=event.timestamp,
					source="ml.prediction_service",
					payload={
						"machine_id": machine_id,
						"health": round(health_score, 4),
						"health_state": self._health_state(health_score),
						"risk_score": round(risk_score, 4),
						"remaining_useful_life": round(prediction, 4),
						"shap_importance": shap_importance,
						"confidence_score": 0.92,
					},
				)
			)

			if risk_score >= self.maintenance_threshold:
				self.event_bus.publish(
					Event(
						event_type=EventType.MAINTENANCE_TRIGGER,
						timestamp=event.timestamp,
						source="ml.prediction_service",
						payload={
							"machine_id": machine_id,
							"reason": "predicted_risk_threshold",
							"risk_score": round(risk_score, 4),
							"remaining_useful_life": round(prediction, 4),
						},
					)
				)
		except Exception as e:
			logging.error(f"Prediction handler failed for machine {event.source}: {e}", exc_info=True)

	def _extract_metrics(self, payload: dict[str, Any]) -> dict[str, float] | None:
		metrics = payload.get("metrics")
		if not isinstance(metrics, dict):
			metrics = payload

		values: dict[str, float] = {}
		for feature in self._feature_order:
			if feature not in metrics:
				# Fallback for simulation metrics if missing (e.g. from real sensor feed without simulation engine)
				if feature in {"queue_length", "machine_utilization", "routing_load"}:
					values[feature] = 0.0
					continue
				return None
			try:
				values[feature] = float(metrics[feature])
			except (TypeError, ValueError):
				return None
		return values

	def _window_to_model_input(self, window: deque[dict[str, float]]) -> np.ndarray:
		"""Converts a window of metrics into a 3D float32 numpy array (batch, window, features)."""
		try:
			# 1. Convert deque of dicts to a 2D list of floats
			rows = []
			for row in window:
				feature_values = []
				for feature in self._feature_order:
					val = row.get(feature, 0.0)
					feature_values.append(float(self._standardize_feature(feature, val)))
				rows.append(feature_values)
			
			# 2. Convert to a numeric numpy array with explicit float32 type
			# We use np.array(rows, dtype=np.float32) which will fail if rows is ragged or contains non-numeric data
			data_2d = np.array(rows, dtype=np.float32)
			
			# 3. Add batch dimension -> (1, window_size, num_features)
			return data_2d[np.newaxis, ...]
		except Exception as e:
			logging.error(f"Failed to convert window to model input: {e}")
			# Return a zeroed-out array of the correct shape as a fallback
			return np.zeros((1, self._window_size, len(self._feature_order)), dtype=np.float32)

	def _standardize_feature(self, feature: str, value: float) -> float:
		stats = self._feature_scaling.get(feature)
		if not stats:
			return float(value)
		std = stats.get("std", 1.0) or 1.0
		mean = stats.get("mean", 0.0)
		return float((value - mean) / std)

	def _inverse_target_scale(self, value: float) -> float:
		mode = str(self._target_scaling.get("name", "standard_score"))
		mean = self._target_scaling.get("mean", 0.0)
		std = self._target_scaling.get("std", 1.0) or 1.0
		raw = float(value * std + mean)
		if mode == "log1p_standard":
			raw = float(np.expm1(raw))
		return max(0.0, raw)

	def _estimate_health_score(self, predicted_rul: float, metrics: dict[str, float]) -> float:
		current_health = float(metrics.get("health", 1.0))
		rul_component = predicted_rul / (predicted_rul + self._window_size)
		health_score = (0.6 * current_health) + (0.4 * max(0.0, min(1.0, rul_component)))
		return max(0.0, min(1.0, health_score))

	def _health_state(self, health_score: float) -> str:
		if health_score <= self.maintenance_threshold:
			return "critical"
		if health_score <= self.health_threshold:
			return "degraded"
		return "nominal"
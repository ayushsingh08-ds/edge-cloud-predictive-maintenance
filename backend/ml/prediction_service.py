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
	_model: keras.Model | None = field(default=None, init=False)
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
		start_time = time.perf_counter()
		prediction_scaled = float(self._model.predict(window_array, verbose=0).reshape(-1)[0])
		latency_ms = (time.perf_counter() - start_time) * 1000
		
		# Log latency for monitoring
		logging.info(f"Machine {machine_id} prediction latency: {latency_ms:.2f}ms")

		prediction = self._inverse_target_scale(prediction_scaled)
		health_score = self._estimate_health_score(prediction, metrics)
		risk_score = 1.0 - health_score

		self.event_bus.publish(
			Event(
				event_type=EventType.RUL_PREDICTION,
				timestamp=event.timestamp,
				source="ml.prediction_service",
				payload={
					"machine_id": machine_id,
					"remaining_useful_life": round(prediction, 4),
					"health_score": round(health_score, 4),
					"risk_score": round(risk_score, 4),
					"window_size": self._window_size,
					"latency_ms": round(latency_ms, 3),
				},
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
		rows = []
		for row in window:
			rows.append([
				self._standardize_feature(feature, row[feature])
				for feature in self._feature_order
			])
		return np.asarray([rows], dtype=np.float32)

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
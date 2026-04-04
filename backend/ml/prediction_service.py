from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
import json
from pathlib import Path
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
		model_path = self.model_path or project_root / "predictive_maintenance_cnn_lstm.keras"

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
			]

		if model_path.exists():
			try:
				self._model = keras.models.load_model(model_path)
			except Exception:
				# Keep the backend operational even if the model artifact is incompatible
				# with the current TensorFlow/Keras runtime in this environment.
				self._model = None

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
		prediction_scaled = float(self._model.predict(window_array, verbose=0).reshape(-1)[0])
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
		mean = self._target_scaling.get("mean", 0.0)
		std = self._target_scaling.get("std", 1.0) or 1.0
		return float(value * std + mean)

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
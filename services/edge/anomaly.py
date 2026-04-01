from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from sklearn.ensemble import IsolationForest

from .publisher import AlertPublisher
from .sensor_stream import SensorRecord


@dataclass
class RollingNormalizer:
    window_size: int = 30

    def __post_init__(self) -> None:
        self._windows: dict[int, deque[list[float]]] = defaultdict(
            lambda: deque(maxlen=self.window_size)
        )

    def normalize(self, record: SensorRecord) -> NDArray[np.float32]:
        features = [record.temperature, record.vibration, record.pressure]
        window = self._windows[record.machine_id]
        window.append(features)

        arr = np.asarray(window, dtype=float)
        means = arr.mean(axis=0)
        stds = arr.std(axis=0)
        stds = np.where(stds < 1e-6, 1.0, stds)

        normalized = (np.asarray(features) - means) / stds
        return normalized.astype(np.float32)


@dataclass
class EdgeAnomalyDetector:
    contamination: float = 0.05
    warmup_samples: int = 40
    sustained_threshold: int = 3

    def __post_init__(self) -> None:
        self.normalizer = RollingNormalizer(window_size=30)
        self.publisher = AlertPublisher()
        self._buffers: dict[int, list[NDArray[np.float32]]] = defaultdict(list)
        self._models: dict[int, IsolationForest] = {}
        self._consecutive_flags: dict[int, int] = defaultdict(int)

    def _fit_if_ready(self, machine_id: int) -> None:
        if machine_id in self._models:
            return

        buffer = self._buffers[machine_id]
        if len(buffer) < self.warmup_samples:
            return

        train_x = np.vstack(buffer)
        model = IsolationForest(
            n_estimators=200,
            contamination=self.contamination,
            random_state=42,
        )
        model.fit(train_x)
        self._models[machine_id] = model

    def process(
        self,
        record: SensorRecord,
        *,
        publish_alerts: bool = True,
    ) -> dict[str, object]:
        normalized: NDArray[np.float32] = self.normalizer.normalize(record)
        self._buffers[record.machine_id].append(normalized)

        self._fit_if_ready(record.machine_id)

        if record.machine_id not in self._models:
            return {
                "machine_id": record.machine_id,
                "timestamp": record.timestamp,
                "status": "warmup",
                "is_anomaly": False,
                "sustained_anomaly": False,
            }

        model = self._models[record.machine_id]
        prediction = int(model.predict(normalized.reshape(1, -1))[0])
        is_anomaly = prediction == -1

        if is_anomaly:
            self._consecutive_flags[record.machine_id] += 1
        else:
            self._consecutive_flags[record.machine_id] = 0

        sustained = self._consecutive_flags[record.machine_id] >= self.sustained_threshold
        result = {
            "machine_id": record.machine_id,
            "timestamp": record.timestamp,
            "status": "running",
            "is_anomaly": is_anomaly,
            "sustained_anomaly": sustained,
            "consecutive_anomalies": self._consecutive_flags[record.machine_id],
            "temperature": round(record.temperature, 4),
            "vibration": round(record.vibration, 4),
            "pressure": round(record.pressure, 4),
        }

        if sustained:
            self.publisher.publish(
                {
                    "machine_id": record.machine_id,
                    "timestamp": record.timestamp,
                    "severity": "high",
                    "reason": "sustained_anomaly_detected",
                    "observations": {
                        "temperature": result["temperature"],
                        "vibration": result["vibration"],
                        "pressure": result["pressure"],
                    },
                },
                event_type="anomaly.alert",
                routing_key="anomaly.alert",
                use_rabbitmq=publish_alerts,
            )

        return result

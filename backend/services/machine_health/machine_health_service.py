"""Machine Health Service: consumes anomaly/RUL events and publishes health updates."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone

from events import MachineHealthUpdated
from messaging.rabbitmq_client import RabbitMQClient
from services.machine_health import health_repository
from services.machine_registry import machine_repository


class MachineHealthService:
    """Compute and persist machine health from anomaly and RUL signals."""

    def __init__(
        self,
        max_rul_hours: float = 200.0,
        publisher: RabbitMQClient | None = None,
    ) -> None:
        self.max_rul_hours = max(1.0, max_rul_hours)
        self.client = publisher or RabbitMQClient()

        # Latest event values per machine, used to combine anomaly + RUL streams.
        self._latest_anomaly: dict[int, float] = {}
        self._latest_rul: dict[int, float] = {}
        self._latest_status: dict[int, str] = defaultdict(lambda: "healthy")

    @staticmethod
    def _safe_machine_id(event: dict) -> int:
        raw = event.get("machine_id") or event.get("sensor_id")
        if raw is None:
            raise ValueError("Event is missing machine_id/sensor_id")

        if isinstance(raw, int):
            return raw

        machine_text = str(raw)
        digits = "".join(ch for ch in machine_text if ch.isdigit())
        return int(digits) if digits else int(machine_text)

    @staticmethod
    def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
        return max(lower, min(upper, value))

    @staticmethod
    def _status_from_health(health_score: float) -> str:
        if health_score > 0.8:
            return "healthy"
        if health_score > 0.5:
            return "warning"
        return "critical"

    def process_anomaly_event(self, event: dict) -> dict | None:
        machine_id = self._safe_machine_id(event)
        anomaly_score = self._clamp(float(event.get("anomaly_score", 0.0)))
        self._latest_anomaly[machine_id] = anomaly_score

        return self.calculate_health(machine_id)

    def process_rul_event(self, event: dict) -> dict | None:
        machine_id = self._safe_machine_id(event)
        rul_hours = max(0.0, float(event.get("rul_hours", 0.0)))
        self._latest_rul[machine_id] = rul_hours

        return self.calculate_health(machine_id)

    def calculate_health(self, machine_id: int) -> dict | None:
        if machine_id not in self._latest_anomaly or machine_id not in self._latest_rul:
            return None

        anomaly_score = self._latest_anomaly[machine_id]
        rul_hours = self._latest_rul[machine_id]

        rul_component = self._clamp(rul_hours / self.max_rul_hours)
        health_score = self._clamp(0.4 * (1.0 - anomaly_score) + 0.6 * rul_component)

        latest_maintenance = health_repository.get_latest_maintenance_status(machine_id)
        latest_telemetry = health_repository.get_latest_telemetry(machine_id)

        # Slight health penalty if machine currently in active maintenance flow.
        if latest_maintenance and latest_maintenance.lower() in {"scheduled", "in_progress"}:
            health_score = self._clamp(health_score - 0.05)

        # Optional mild degradation from very high vibration if telemetry exists.
        if latest_telemetry and latest_telemetry.get("vibration", 0.0) > 0.8:
            health_score = self._clamp(health_score - 0.05)

        status = self._status_from_health(health_score)
        self._latest_status[machine_id] = status

        stored = health_repository.insert_machine_health(
            machine_id=machine_id,
            health_score=health_score,
            anomaly_score=anomaly_score,
            rul_hours=rul_hours,
        )

        if status == "critical":
            # Move machine into maintenance mode when health becomes critical.
            machine_repository.update_machine_status(machine_id, "maintenance")

        self.publish_machine_health(
            machine_id=machine_id,
            health_score=health_score,
            anomaly_score=anomaly_score,
            rul_hours=rul_hours,
            status=status,
        )

        return {
            **stored,
            "status": status,
        }

    def publish_machine_health(
        self,
        machine_id: int,
        health_score: float,
        anomaly_score: float,
        rul_hours: float,
        status: str,
    ) -> None:
        event = MachineHealthUpdated(
            machine_id=str(machine_id),
            health_score=round(health_score, 4),
            anomaly_score=round(anomaly_score, 4),
            rul_hours=round(rul_hours, 2),
            status=status,
            timestamp=datetime.now(timezone.utc),
        )
        self.client.publish("machine.health.updated", event.to_dict())

    def start(self) -> None:
        """Subscribe to anomaly and RUL topics and process health updates continuously."""
        print("[+] Machine Health Service listening for anomaly and RUL events...")

        result = self.client.channel.queue_declare(queue="", exclusive=True)
        queue_name = result.method.queue

        topics = [
            "anomaly.detected",
            "rul.predicted",
            # Backward-compatible existing topics in current project.
            "edge.anomaly",
            "cloud.rul",
        ]
        for topic in topics:
            self.client.channel.queue_bind(
                exchange="sensor_exchange",
                queue=queue_name,
                routing_key=topic,
            )

        def callback(ch, method, properties, body):
            try:
                payload = json.loads(body)
                routing_key = getattr(method, "routing_key", "")

                if routing_key in {"anomaly.detected", "edge.anomaly"}:
                    result = self.process_anomaly_event(payload)
                elif routing_key in {"rul.predicted", "cloud.rul"}:
                    result = self.process_rul_event(payload)
                else:
                    return

                if result is not None:
                    print(
                        "[HEALTH] "
                        f"machine={result['machine_id']} "
                        f"score={result['health_score']:.4f} "
                        f"status={result['status']}"
                    )
            except Exception as exc:
                print(f"[ERROR] Failed to process health event: {exc}")

        self.client.channel.basic_consume(
            queue=queue_name,
            on_message_callback=callback,
            auto_ack=True,
        )
        self.client.channel.start_consuming()

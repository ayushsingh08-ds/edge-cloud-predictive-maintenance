from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from events import Event, EventBus, EventType


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass(slots=True)
class MaintenanceRecord:
    timestamp: float
    record_type: str
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MachineMetrics:
    machine_id: str
    started_at: float = 0.0
    last_timestamp: float = 0.0
    state: str = "Idle"

    operating_time: float = 0.0
    busy_time: float = 0.0
    downtime: float = 0.0

    failures: int = 0
    last_failure_time: float | None = None
    mtbf_history: list[float] = field(default_factory=list)
    mtbf: float = 0.0

    production_count: int = 0
    good_count: int = 0
    scrap_count: int = 0
    cycle_time_history: list[float] = field(default_factory=list)
    active_job_start: float | None = None

    sensor_health_index: float = 1.0
    rul_hours: float | None = None
    machine_health: float = 1.0

    availability: float = 1.0
    performance: float = 1.0
    quality: float = 1.0
    oee: float = 1.0
    utilization: float = 0.0

    maintenance_required: bool = False
    maintenance_history: list[MaintenanceRecord] = field(default_factory=list)


@dataclass(slots=True)
class ManufacturingExecutionSystem:
    event_bus: EventBus
    health_threshold: float = 0.55
    rul_threshold_hours: float = 12.0
    machine_metrics: dict[str, MachineMetrics] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.event_bus.subscribe(EventType.SENSOR_DATA, self.handle_sensor_data)
        self.event_bus.subscribe(EventType.RUL_PREDICTION, self.handle_rul_prediction)
        self.event_bus.subscribe(EventType.JOB_START, self.handle_job_start)
        self.event_bus.subscribe(EventType.JOB_FINISH, self.handle_job_finish)
        self.event_bus.subscribe(EventType.MACHINE_FAILURE, self.handle_machine_failure)
        self.event_bus.subscribe(EventType.MACHINE_REPAIR, self.handle_machine_repair)

    def handle_sensor_data(self, event: Event) -> None:
        machine_id = str(event.payload.get("machine_id", ""))
        if not machine_id:
            return
        metrics = self._metrics_for(machine_id, event.timestamp)
        self._advance_time(metrics, event.timestamp)

        sensor = dict(event.payload.get("metrics", {}))
        metrics.sensor_health_index = self._sensor_health_index(sensor)

        self._refresh_kpis(metrics, event.timestamp)
        self._publish_health_update(metrics, event.timestamp, source="mes.sensor")
        self._trigger_maintenance_if_needed(metrics, event.timestamp, reason="low_health_sensor")

    def handle_rul_prediction(self, event: Event) -> None:
        machine_id = str(event.payload.get("machine_id", ""))
        if not machine_id:
            return
        metrics = self._metrics_for(machine_id, event.timestamp)
        self._advance_time(metrics, event.timestamp)

        remaining_useful_life = event.payload.get("remaining_useful_life")
        if remaining_useful_life is not None:
            metrics.rul_hours = float(remaining_useful_life)

        self._refresh_kpis(metrics, event.timestamp)
        self._publish_health_update(metrics, event.timestamp, source="mes.rul")
        self._trigger_maintenance_if_needed(metrics, event.timestamp, reason="low_health_rul")

    def handle_job_start(self, event: Event) -> None:
        machine_id = str(event.payload.get("machine_id", ""))
        if not machine_id:
            return
        metrics = self._metrics_for(machine_id, event.timestamp)
        self._advance_time(metrics, event.timestamp)
        metrics.state = "Busy"
        metrics.active_job_start = event.timestamp
        self._refresh_kpis(metrics, event.timestamp)

    def handle_job_finish(self, event: Event) -> None:
        machine_id = str(event.payload.get("machine_id", ""))
        if not machine_id:
            return
        metrics = self._metrics_for(machine_id, event.timestamp)
        self._advance_time(metrics, event.timestamp)
        metrics.state = "Idle"
        metrics.production_count += 1
        metrics.good_count += 1
        if metrics.active_job_start is not None and event.timestamp >= metrics.active_job_start:
            cycle_time = event.timestamp - metrics.active_job_start
            metrics.cycle_time_history.append(cycle_time)
        metrics.active_job_start = None
        self._refresh_kpis(metrics, event.timestamp)

    def handle_machine_failure(self, event: Event) -> None:
        machine_id = str(event.payload.get("machine_id", ""))
        if not machine_id:
            return
        metrics = self._metrics_for(machine_id, event.timestamp)
        self._advance_time(metrics, event.timestamp)
        metrics.state = "Failed"
        metrics.failures += 1
        if metrics.last_failure_time is not None and event.timestamp > metrics.last_failure_time:
            metrics.mtbf_history.append(event.timestamp - metrics.last_failure_time)
        metrics.last_failure_time = event.timestamp
        metrics.maintenance_history.append(
            MaintenanceRecord(
                timestamp=event.timestamp,
                record_type="failure",
                reason="machine_failure",
                metadata={"event_id": event.event_id},
            )
        )
        self._refresh_kpis(metrics, event.timestamp)

    def handle_machine_repair(self, event: Event) -> None:
        machine_id = str(event.payload.get("machine_id", ""))
        if not machine_id:
            return
        metrics = self._metrics_for(machine_id, event.timestamp)
        self._advance_time(metrics, event.timestamp)
        metrics.state = "Idle"
        metrics.maintenance_required = False
        metrics.maintenance_history.append(
            MaintenanceRecord(
                timestamp=event.timestamp,
                record_type="repair",
                reason="machine_repair",
                metadata={"event_id": event.event_id},
            )
        )
        self._refresh_kpis(metrics, event.timestamp)
        self._publish_health_update(metrics, event.timestamp, source="mes.repair")

    def _metrics_for(self, machine_id: str, timestamp: float) -> MachineMetrics:
        metrics = self.machine_metrics.get(machine_id)
        if metrics is None:
            metrics = MachineMetrics(machine_id=machine_id, started_at=timestamp, last_timestamp=timestamp)
            self.machine_metrics[machine_id] = metrics
        return metrics

    def _advance_time(self, metrics: MachineMetrics, timestamp: float) -> None:
        if timestamp <= metrics.last_timestamp:
            return
        delta = timestamp - metrics.last_timestamp
        metrics.operating_time += delta
        if metrics.state == "Busy":
            metrics.busy_time += delta
        if metrics.state in {"Failed", "Maintenance"}:
            metrics.downtime += delta
        metrics.last_timestamp = timestamp

    def _refresh_kpis(self, metrics: MachineMetrics, timestamp: float) -> None:
        elapsed = max(1e-6, timestamp - metrics.started_at)
        metrics.utilization = _clamp(metrics.busy_time / elapsed)

        run_time = max(1e-6, metrics.operating_time - metrics.downtime)
        metrics.availability = _clamp(run_time / max(1e-6, metrics.operating_time))

        if metrics.cycle_time_history and metrics.busy_time > 0:
            ideal_cycle_time = min(metrics.cycle_time_history)
            metrics.performance = _clamp((ideal_cycle_time * metrics.production_count) / max(1e-6, metrics.busy_time))
        else:
            metrics.performance = 1.0

        produced = max(1, metrics.production_count)
        metrics.quality = _clamp(metrics.good_count / produced)
        metrics.oee = _clamp(metrics.availability * metrics.performance * metrics.quality)

        metrics.mtbf = sum(metrics.mtbf_history) / len(metrics.mtbf_history) if metrics.mtbf_history else 0.0

        mtbf_score = _clamp(metrics.mtbf / 80.0) if metrics.mtbf > 0 else 0.5
        rul_score = 0.5 if metrics.rul_hours is None else _clamp(metrics.rul_hours / max(1e-6, self.rul_threshold_hours * 2.0))
        maintenance_penalty = 0.07 * len([m for m in metrics.maintenance_history if m.record_type == "failure"])

        metrics.machine_health = _clamp(
            0.35 * metrics.sensor_health_index
            + 0.25 * metrics.oee
            + 0.2 * mtbf_score
            + 0.2 * rul_score
            - maintenance_penalty
        )

    def _sensor_health_index(self, sensor: dict[str, Any]) -> float:
        temperature = float(sensor.get("temperature", 35.0))
        vibration = float(sensor.get("vibration", 0.3))
        pressure = float(sensor.get("pressure", 8.0))
        flow = float(sensor.get("flow", 120.0))
        humidity = float(sensor.get("humidity", 45.0))
        load = float(sensor.get("load", 50.0))
        speed = float(sensor.get("speed", 900.0))

        temp_score = _clamp(1.0 - max(0.0, temperature - 36.0) / 60.0)
        vibration_score = _clamp(1.0 - max(0.0, vibration - 0.2) / 1.8)
        pressure_score = _clamp(pressure / 10.0)
        flow_score = _clamp(flow / 220.0)
        humidity_score = _clamp(1.0 - abs(humidity - 50.0) / 50.0)
        load_score = _clamp(1.0 - max(0.0, load - 92.0) / 50.0)
        speed_score = _clamp(speed / 1500.0)

        return _clamp(
            0.24 * temp_score
            + 0.24 * vibration_score
            + 0.14 * pressure_score
            + 0.14 * flow_score
            + 0.08 * humidity_score
            + 0.08 * load_score
            + 0.08 * speed_score
        )

    def _publish_health_update(self, metrics: MachineMetrics, timestamp: float, source: str) -> None:
        self.event_bus.publish(
            Event(
                event_type=EventType.HEALTH_UPDATE,
                timestamp=timestamp,
                source=source,
                payload={
                    "machine_id": metrics.machine_id,
                    "health": round(metrics.machine_health, 4),
                    "sensor_health_index": round(metrics.sensor_health_index, 4),
                    "oee": round(metrics.oee, 4),
                    "availability": round(metrics.availability, 4),
                    "performance": round(metrics.performance, 4),
                    "quality": round(metrics.quality, 4),
                    "utilization": round(metrics.utilization, 4),
                    "downtime": round(metrics.downtime, 4),
                    "mtbf": round(metrics.mtbf, 4),
                    "rul_hours": None if metrics.rul_hours is None else round(metrics.rul_hours, 4),
                    "production_count": metrics.production_count,
                    "good_count": metrics.good_count,
                    "scrap_count": metrics.scrap_count,
                },
            )
        )

    def _trigger_maintenance_if_needed(self, metrics: MachineMetrics, timestamp: float, reason: str) -> None:
        low_health = metrics.machine_health < self.health_threshold
        low_rul = metrics.rul_hours is not None and metrics.rul_hours < self.rul_threshold_hours
        if not (low_health or low_rul):
            return
        if metrics.maintenance_required:
            return

        metrics.maintenance_required = True
        metrics.state = "Maintenance"
        metrics.maintenance_history.append(
            MaintenanceRecord(
                timestamp=timestamp,
                record_type="maintenance_trigger",
                reason=reason,
                metadata={
                    "health": metrics.machine_health,
                    "rul_hours": metrics.rul_hours,
                    "threshold": self.health_threshold,
                },
            )
        )

        self.event_bus.publish(
            Event(
                event_type=EventType.MAINTENANCE_TRIGGER,
                timestamp=timestamp,
                source="mes.core",
                payload={
                    "machine_id": metrics.machine_id,
                    "reason": reason,
                    "health": round(metrics.machine_health, 4),
                    "threshold": self.health_threshold,
                    "rul_hours": metrics.rul_hours,
                },
            )
        )

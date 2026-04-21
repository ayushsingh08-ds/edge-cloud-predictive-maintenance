from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from threading import RLock

import simpy

from events import Event, EventBus, EventType

from .job import Job


class MachineStatus(str, Enum):
    IDLE = "Idle"
    BUSY = "Busy"
    FAILED = "Failed"
    MAINTENANCE = "Maintenance"


@dataclass(slots=True)
class Machine:
    machine_id: str
    environment: simpy.Environment
    event_bus: EventBus | None = None
    status: MachineStatus = MachineStatus.IDLE
    current_job: Optional[Job] = None
    processing_time: float = 1.0
    health: float = 1.0
    wear: float = 0.0
    load_factor: float = 0.5
    operating_time: float = 0.0
    wear_rate_time: float = 0.0008
    wear_rate_usage: float = 0.003
    failure_probability: float = 0.0
    failure_rate: float = 0.0
    sensor_interval: float = 1.0
    maintenance_duration: float = 0.0
    predicted_health_score: float | None = None
    predicted_rul_hours: float | None = None
    utilization: float = 0.0
    safety_mode_threshold: float = 0.3
    safety_mode_multiplier: float = 1.25
    dynamic_metrics: dict[str, float] = field(default_factory=dict, init=False)
    completed_jobs: list[Job] = field(default_factory=list)
    _arrivals: list[float] = field(default_factory=list, repr=False)
    _completions: list[float] = field(default_factory=list, repr=False)
    _busy_start: float | None = field(default=None, init=False, repr=False)
    total_busy_time: float = field(default=0.0, init=False)
    _rng: random.Random = field(init=False, repr=False)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def __post_init__(self) -> None:
        seed = sum(ord(ch) for ch in self.machine_id)
        self._rng = random.Random(seed)
        self.wear = min(1.0, max(0.0, self.wear))
        self.load_factor = min(1.0, max(0.0, self.load_factor))
        if self.event_bus is not None:
            self.event_bus.subscribe(EventType.HEALTH_UPDATE, self._handle_health_update)
            self.event_bus.subscribe(EventType.RUL_PREDICTION, self._handle_rul_prediction)

    def is_available(self) -> bool:
        return self.status == MachineStatus.IDLE

    def processing_time_for_job(self, job: Job) -> float:
        base_time = float(job.processing_time_for_current_operation() if job.operation_count() > 0 else self.processing_time)
        health_score = self._effective_health_score()

        if health_score < self.safety_mode_threshold:
            return base_time * self.safety_mode_multiplier
        
        # Condition-Based Throttling (Slow Mode)
        # If health is low, we slow down the machine to preserve it
        # Below 50% health, time increases by up to 3x at 0% health
        if self.health < 0.5:
            multiplier = 1.0 + (0.5 - self.health) * 4.0 # 0.5 health -> 1.0x, 0.0 health -> 3.0x
            return base_time * multiplier
            
        return base_time

    def assign_job(self, job: Job) -> None:
        if not self.is_available():
            raise RuntimeError(f"Machine {self.machine_id} is not available")
        self.current_job = job
        self.status = MachineStatus.BUSY
        self._busy_start = self.environment.now
        self._arrivals.append(self.environment.now)
        # Prune old arrivals (> 60s)
        self._arrivals = [t for t in self._arrivals if t > self.environment.now - 60.0]
        job.mark_in_process(self.environment.now)
        if self.event_bus is not None:
            self.event_bus.publish(
                Event(
                    event_type=EventType.JOB_START,
                    timestamp=self.environment.now,
                    source=f"machine.{self.machine_id}",
                    payload={
                        "job_id": job.job_id,
                        "machine_id": self.machine_id,
                        "operation": job.current_operation(),
                    },
                )
            )

    def release_job(self) -> Optional[Job]:
        job = self.current_job
        self.current_job = None
        self.status = MachineStatus.IDLE
        if self._busy_start is not None:
            self.total_busy_time += self.environment.now - self._busy_start
            self._busy_start = None
        self._completions.append(self.environment.now)
        # Prune old completions (> 60s)
        self._completions = [t for t in self._completions if t > self.environment.now - 60.0]

        if job is not None:
            has_next_operation = job.advance_operation()
            if not has_next_operation:
                job.mark_completed(self.environment.now)
            else:
                job.mark_queued()
            self.completed_jobs.append(job)
            self.health = max(0.0, self.health - 0.005)
            if self.event_bus is not None:
                self.event_bus.publish(
                    Event(
                        event_type=EventType.JOB_FINISH,
                        timestamp=self.environment.now,
                        source=f"machine.{self.machine_id}",
                        payload={
                            "job_id": job.job_id,
                            "machine_id": self.machine_id,
                            "next_operation": job.current_operation(),
                        },
                    )
                )
        return job

    def process_job(self, job: Job, processing_time: float | None = None):
        self.assign_job(job)
        duration = processing_time if processing_time is not None else self.processing_time_for_job(job)
        yield self.environment.timeout(duration)
        self._increase_wear(duration, usage_multiplier=1.4)
        self.release_job()

    def should_fail_now(self) -> bool:
        if self.status != MachineStatus.IDLE:
            return False
        dynamic_failure_probability = min(1.0, self.failure_probability * (2.0 - self.health))
        return self._rng.random() < dynamic_failure_probability

    def sensor_payload(self) -> dict[str, float | str]:
        active_load = self.load_factor if self.status == MachineStatus.BUSY else self.load_factor * 0.35
        wear_effect = self.wear
        health = self.health

        temperature = 28.0 + 30.0 * active_load + 35.0 * wear_effect + self._rng.uniform(-1.2, 1.2)
        vibration = 0.12 + 0.55 * active_load + 0.95 * wear_effect + self._rng.uniform(-0.03, 0.03)
        pressure = 9.0 + 2.0 * active_load - 4.5 * wear_effect + self._rng.uniform(-0.25, 0.25)
        speed = 700.0 + 700.0 * active_load - 120.0 * wear_effect + self._rng.uniform(-10.0, 10.0)
        load = 15.0 + 85.0 * active_load + self._rng.uniform(-2.0, 2.0)
        flow = 120.0 + 110.0 * active_load - 70.0 * wear_effect + self._rng.uniform(-3.0, 3.0)
        humidity = 40.0 + 8.0 * active_load + 9.0 * wear_effect + self._rng.uniform(-1.0, 1.0)

        return {
            "temperature": round(temperature, 3),
            "vibration": round(vibration, 3),
            "pressure": round(max(0.1, pressure), 3),
            "speed": round(max(0.0, speed), 3),
            "load": round(max(0.0, load), 3),
            "flow": round(max(0.1, flow), 3),
            "humidity": round(max(0.0, humidity), 3),
            "wear": round(self.wear, 4),
            "health": round(health, 4),
            "operating_time": round(self.operating_time, 3),
            "status": self.status.value,
            "utilization": round(self.utilization, 4),
            "energy_kwh": round(2.5 * active_load + 0.5 * self.wear, 4),
            "carbon_impact": round((2.5 * active_load + 0.5 * self.wear) * 0.45, 4),
            "congestion_risk": round(self.calculate_congestion_risk(), 3),
            **self.dynamic_metrics
        }

    def _effective_health_score(self) -> float:
        if self.predicted_health_score is not None:
            return max(0.0, min(1.0, float(self.predicted_health_score)))
        return max(0.0, min(1.0, float(self.health)))

    def _handle_health_update(self, event: Event) -> None:
        machine_id = str(event.payload.get("machine_id", ""))
        if machine_id != self.machine_id:
            return
        if event.source != "ml.prediction_service":
            return
        try:
            health_score = float(event.payload.get("health", event.payload.get("health_score", self.health)))
        except (TypeError, ValueError):
            return
        with self._lock:
            self.predicted_health_score = max(0.0, min(1.0, health_score))

    def _handle_rul_prediction(self, event: Event) -> None:
        machine_id = str(event.payload.get("machine_id", ""))
        if machine_id != self.machine_id:
            return
        if event.source != "ml.prediction_service":
            return
        try:
            rul_hours = float(event.payload.get("remaining_useful_life", 0.0))
        except (TypeError, ValueError):
            return
        with self._lock:
            self.predicted_rul_hours = max(0.0, rul_hours)

    def calculate_congestion_risk(self, window: float = 60.0) -> float:
        """
        Predicts the risk of this machine becoming a bottleneck.
        Growth Rate = ArrivalRate / CompletionRate
        """
        now = self.environment.now
        recent_arrivals = [t for t in self._arrivals if t > now - window]
        recent_completions = [t for t in self._completions if t > now - window]

        arrival_rate = len(recent_arrivals) / (window / 60.0) if window > 0 else 0
        completion_rate = len(recent_completions) / (window / 60.0) if window > 0 else 0

        # If we have arrivals but no completions yet (stalled), risk is high
        if arrival_rate > 0 and completion_rate == 0:
            return 0.8 if len(recent_arrivals) > 2 else 0.4

        if completion_rate == 0:
            return 0.0

        growth_rate = arrival_rate / completion_rate

        # Risk scales with growth rate
        # 1.0 (stable) -> 0.4 risk
        # 1.5 (growing) -> 0.8 risk
        # > 2.0 (critical) -> 1.0 risk
        if growth_rate <= 1.0:
            return growth_rate * 0.4
        else:
            return min(1.0, 0.4 + (growth_rate - 1.0) * 0.8)

    def start_sensor_stream(self):
        return self.environment.process(self._sensor_loop())

    def _sensor_loop(self):
        while True:
            yield self.environment.timeout(self.sensor_interval)
            self.operating_time += self.sensor_interval
            if self.status == MachineStatus.BUSY:
                self._increase_wear(self.sensor_interval, usage_multiplier=1.0)
            else:
                self._increase_wear(self.sensor_interval, usage_multiplier=0.35)
            if self.event_bus is None:
                continue
            metrics = self.sensor_payload()
            self.event_bus.publish(
                Event(
                    event_type=EventType.SENSOR_DATA,
                    timestamp=self.environment.now,
                    source=f"machine.{self.machine_id}",
                    payload={"machine_id": self.machine_id, "metrics": metrics},
                )
            )
            
            # Bottleneck Early Warning System (5-10m Lookahead)
            # If the growth rate is consistently high, we alert the operator early
            if metrics.get("congestion_risk", 0.0) > 0.65:
                self.event_bus.publish(
                    Event(
                        event_type=EventType.MAINTENANCE_TRIGGER, # We reuse this or add BOTTLENECK_ALERT
                        timestamp=self.environment.now,
                        source=f"machine.{self.machine_id}",
                        payload={
                            "machine_id": self.machine_id, 
                            "severity": "high",
                            "message": f"PREDICTIVE ALERT: Machine {self.machine_id} showing high bottleneck risk ({round(metrics.get('congestion_risk', 0.0) * 100)}%). Flow diverted."
                        },
                    )
                )

    def fail(self) -> None:
        self.status = MachineStatus.FAILED
        self.health = max(0.0, self.health - 0.1)
        self.wear = min(1.0, self.wear + 0.02)
        if self.event_bus is not None:
            self.event_bus.publish(
                Event(
                    event_type=EventType.MACHINE_FAILURE,
                    timestamp=self.environment.now,
                    source=f"machine.{self.machine_id}",
                    payload={"machine_id": self.machine_id, "status": self.status.value},
                )
            )

    def repair(self) -> None:
        self.status = MachineStatus.IDLE
        self.health = min(1.0, self.health + 0.2)
        self.wear = max(0.0, self.wear - 0.05)
        if self.event_bus is not None:
            self.event_bus.publish(
                Event(
                    event_type=EventType.MACHINE_REPAIR,
                    timestamp=self.environment.now,
                    source=f"machine.{self.machine_id}",
                    payload={"machine_id": self.machine_id, "status": self.status.value},
                )
            )

    def start_maintenance(self) -> simpy.events.Event:
        self.status = MachineStatus.MAINTENANCE
        if self.event_bus is not None:
            self.event_bus.publish(
                Event(
                    event_type=EventType.MAINTENANCE_STATE,
                    timestamp=self.environment.now,
                    source=f"machine.{self.machine_id}",
                    payload={"machine_id": self.machine_id, "status": self.status.value, "state": "maintenance"},
                )
            )
        return self.environment.timeout(self.maintenance_duration)

    def _increase_wear(self, elapsed_time: float, usage_multiplier: float) -> None:
        wear_gain = elapsed_time * (self.wear_rate_time + self.wear_rate_usage * self.load_factor * usage_multiplier)
        self.wear = min(1.0, self.wear + wear_gain)
        self.health = max(0.0, 1.0 - self.wear)

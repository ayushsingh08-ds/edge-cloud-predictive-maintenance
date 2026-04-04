from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

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
    completed_jobs: list[Job] = field(default_factory=list)
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        seed = sum(ord(ch) for ch in self.machine_id)
        self._rng = random.Random(seed)
        self.wear = min(1.0, max(0.0, self.wear))
        self.load_factor = min(1.0, max(0.0, self.load_factor))

    def is_available(self) -> bool:
        return self.status == MachineStatus.IDLE

    def processing_time_for_job(self, job: Job) -> float:
        return float(job.processing_time_for_current_operation() if job.operation_count() > 0 else self.processing_time)

    def assign_job(self, job: Job) -> None:
        if not self.is_available():
            raise RuntimeError(f"Machine {self.machine_id} is not available")
        self.current_job = job
        self.status = MachineStatus.BUSY
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
        }

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
            self.event_bus.publish(
                Event(
                    event_type=EventType.HEALTH_UPDATE,
                    timestamp=self.environment.now,
                    source=f"machine.{self.machine_id}",
                    payload={"machine_id": self.machine_id, "health": self.health},
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
                    event_type=EventType.MAINTENANCE_TRIGGER,
                    timestamp=self.environment.now,
                    source=f"machine.{self.machine_id}",
                    payload={"machine_id": self.machine_id, "status": self.status.value},
                )
            )
        return self.environment.timeout(self.maintenance_duration)

    def _increase_wear(self, elapsed_time: float, usage_multiplier: float) -> None:
        wear_gain = elapsed_time * (self.wear_rate_time + self.wear_rate_usage * self.load_factor * usage_multiplier)
        self.wear = min(1.0, self.wear + wear_gain)
        self.health = max(0.0, 1.0 - self.wear)

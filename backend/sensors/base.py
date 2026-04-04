from __future__ import annotations

from dataclasses import dataclass, field

import simpy

from events import Event, EventBus, EventType


@dataclass(slots=True)
class SensorReading:
    sensor_id: str
    machine_id: str
    timestamp: float
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class Sensor:
    sensor_id: str
    machine_id: str
    environment: simpy.Environment
    event_bus: EventBus
    sample_interval: float = 1.0

    def start(self):
        return self.environment.process(self._sampling_loop())

    def _sampling_loop(self):
        while True:
            yield self.environment.timeout(self.sample_interval)
            reading = SensorReading(
                sensor_id=self.sensor_id,
                machine_id=self.machine_id,
                timestamp=self.environment.now,
                metrics={"temperature": 0.0, "vibration": 0.0},
            )
            self.event_bus.publish(
                Event(
                    event_type=EventType.SENSOR_DATA,
                    timestamp=self.environment.now,
                    source=f"sensor.{self.sensor_id}",
                    payload={
                        "sensor_id": reading.sensor_id,
                        "machine_id": reading.machine_id,
                        "metrics": reading.metrics,
                    },
                )
            )

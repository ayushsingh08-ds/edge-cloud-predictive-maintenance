from __future__ import annotations

from dataclasses import dataclass
from random import Random


@dataclass(slots=True)
class SensorRecord:
    timestamp: float
    machine_id: int
    temperature: float
    vibration: float
    pressure: float


def generate_sensor_stream(
    *,
    duration_seconds: int,
    sample_period_seconds: float,
    num_machines: int,
    seed: int = 42,
    anomaly_probability: float = 0.04,
) -> list[SensorRecord]:
    rng = Random(seed)
    records: list[SensorRecord] = []
    t = 0.0

    while t < duration_seconds:
        for machine_id in range(num_machines):
            is_anomaly = rng.random() < anomaly_probability

            temperature = rng.normalvariate(68.0, 2.5)
            vibration = rng.normalvariate(0.40, 0.06)
            pressure = rng.normalvariate(100.0, 4.0)

            if is_anomaly:
                temperature += rng.uniform(10.0, 18.0)
                vibration += rng.uniform(0.25, 0.55)
                pressure += rng.uniform(15.0, 35.0)

            records.append(
                SensorRecord(
                    timestamp=t,
                    machine_id=machine_id,
                    temperature=temperature,
                    vibration=vibration,
                    pressure=pressure,
                )
            )
        t += sample_period_seconds

    return records

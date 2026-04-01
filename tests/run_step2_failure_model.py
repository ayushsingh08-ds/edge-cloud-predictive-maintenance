from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.simulation.engine import FactoryConfig, FactorySimulation


def main() -> None:
    config = FactoryConfig(
        num_machines=3,
        arrival_rate_per_hour=8.0,
        mean_processing_time_hours=0.35,
        due_date_factor=3.0,
        enable_failures=True,
        weibull_shape=1.7,
        weibull_scale_hours=6.0,
        mean_repair_time_hours=0.8,
        repair_crews=1,
        preventive_maintenance_interval_hours=2.8,
        preventive_maintenance_duration_hours=0.5,
        random_seed=7,
    )

    simulation = FactorySimulation(config)
    summary = simulation.run(until_hours=20.0)

    print("STEP 2 - Failure and Repair summary")
    for key, value in summary.items():
        print(f"{key}: {value}")

    failure_events = [e for e in simulation.event_log if e["event"] == "machine_failure"]
    repair_events = [e for e in simulation.event_log if e["event"] == "machine_repaired"]
    pm_events = [
        e
        for e in simulation.event_log
        if e["event"] in {"preventive_maintenance_started", "preventive_maintenance_completed"}
    ]

    print("\nFailure events:", len(failure_events))
    print("Repair events:", len(repair_events))
    print("Preventive maintenance events:", len(pm_events))


if __name__ == "__main__":
    main()

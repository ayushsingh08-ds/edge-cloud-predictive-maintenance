from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.simulation.engine import FactoryConfig, FactorySimulation
from services.simulation.scheduling import SchedulingPolicy


def run_policy(policy: SchedulingPolicy) -> dict[str, float | int | str]:
    sim = FactorySimulation(
        FactoryConfig(
            num_machines=4,
            arrival_rate_per_hour=8.0,
            mean_processing_time_hours=0.34,
            due_date_factor=3.0,
            scheduling_policy=policy,
            enable_failures=True,
            weibull_shape=1.8,
            weibull_scale_hours=7.0,
            mean_repair_time_hours=0.7,
            repair_crews=1,
            preventive_maintenance_interval_hours=3.2,
            preventive_maintenance_duration_hours=0.5,
            random_seed=13,
        )
    )
    return sim.run(until_hours=20.0)


def main() -> None:
    baseline = run_policy(SchedulingPolicy.QUEUE_BASED)
    health = run_policy(SchedulingPolicy.HEALTH_AWARE)

    print("STEP 7 - Health-Aware Scheduling")
    print("baseline_policy:", baseline["policy"])
    print("baseline_tardiness:", baseline["avg_tardiness_hours"])
    print("baseline_downtime:", baseline["downtime_hours"])

    print("health_policy:", health["policy"])
    print("health_tardiness:", health["avg_tardiness_hours"])
    print("health_downtime:", health["downtime_hours"])


if __name__ == "__main__":
    main()

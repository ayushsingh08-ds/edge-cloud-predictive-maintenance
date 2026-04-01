from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.simulation.engine import FactoryConfig, FactorySimulation
from services.simulation.scheduling import SchedulingPolicy


def run_for_policy(policy: SchedulingPolicy) -> dict[str, float | int | str]:
    sim = FactorySimulation(
        FactoryConfig(
            num_machines=3,
            arrival_rate_per_hour=7.2,
            mean_processing_time_hours=0.34,
            due_date_factor=3.0,
            scheduling_policy=policy,
            enable_failures=True,
            weibull_shape=1.7,
            weibull_scale_hours=7.0,
            mean_repair_time_hours=0.8,
            repair_crews=1,
            preventive_maintenance_interval_hours=3.0,
            preventive_maintenance_duration_hours=0.5,
            random_seed=7,
        )
    )
    return sim.run(until_hours=20.0)


def main() -> None:
    print("STEP 3 - Scheduling Baselines")
    for policy in [
        SchedulingPolicy.RANDOM,
        SchedulingPolicy.SPT,
        SchedulingPolicy.QUEUE_BASED,
    ]:
        summary = run_for_policy(policy)
        print("\nPolicy:", summary["policy"])
        print("throughput_jobs_per_hour:", summary["throughput_jobs_per_hour"])
        print("avg_tardiness_hours:", summary["avg_tardiness_hours"])
        print("avg_queue_length:", summary["avg_queue_length"])
        print("utilization:", summary["utilization"])


if __name__ == "__main__":
    main()

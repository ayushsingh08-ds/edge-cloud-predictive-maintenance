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
            num_machines=3,
            arrival_rate_per_hour=7.2,
            mean_processing_time_hours=0.34,
            due_date_factor=3.0,
            scheduling_policy=policy,
            enable_failures=False,
            random_seed=11,
        )
    )
    return sim.run(until_hours=10.0)


def test_step3_all_baselines_run() -> None:
    for policy in [
        SchedulingPolicy.RANDOM,
        SchedulingPolicy.SPT,
        SchedulingPolicy.QUEUE_BASED,
    ]:
        summary = run_policy(policy)
        assert summary["jobs_generated"] > 0
        assert summary["jobs_completed"] >= 0
        assert summary["policy"] == policy.value

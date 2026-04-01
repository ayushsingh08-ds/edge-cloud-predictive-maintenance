from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.simulation.engine import FactoryConfig, FactorySimulation
from services.simulation.scheduling import SchedulingPolicy


def test_step7_health_policy_runs() -> None:
    sim = FactorySimulation(
        FactoryConfig(
            num_machines=3,
            arrival_rate_per_hour=7.0,
            mean_processing_time_hours=0.32,
            due_date_factor=3.0,
            scheduling_policy=SchedulingPolicy.HEALTH_AWARE,
            enable_failures=True,
            random_seed=22,
        )
    )

    summary = sim.run(until_hours=8.0)

    assert summary["policy"] == SchedulingPolicy.HEALTH_AWARE.value
    assert summary["jobs_generated"] > 0
    assert summary["events_logged"] > 0

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.simulation.engine import FactoryConfig, FactorySimulation


def test_step1_simulation_runs() -> None:
    sim = FactorySimulation(
        FactoryConfig(
            num_machines=2,
            arrival_rate_per_hour=5.0,
            mean_processing_time_hours=0.4,
            due_date_factor=3.0,
            random_seed=1,
        )
    )

    summary = sim.run(until_hours=8.0)

    assert summary["jobs_generated"] > 0
    assert summary["jobs_completed"] >= 0
    assert 0.0 <= summary["utilization"] <= 1.0
    assert summary["events_logged"] > 0

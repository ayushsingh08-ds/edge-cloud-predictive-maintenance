from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.simulation.engine import FactoryConfig, FactorySimulation


def test_step2_failures_and_repairs_trigger() -> None:
    sim = FactorySimulation(
        FactoryConfig(
            num_machines=2,
            arrival_rate_per_hour=6.5,
            mean_processing_time_hours=0.35,
            due_date_factor=3.0,
            enable_failures=True,
            weibull_shape=1.5,
            weibull_scale_hours=4.5,
            mean_repair_time_hours=0.6,
            repair_crews=1,
            preventive_maintenance_interval_hours=2.0,
            preventive_maintenance_duration_hours=0.4,
            random_seed=21,
        )
    )

    summary = sim.run(until_hours=14.0)

    assert summary["jobs_generated"] > 0
    assert summary["jobs_completed"] >= 0
    assert summary["failures"] > 0
    assert summary["downtime_hours"] > 0

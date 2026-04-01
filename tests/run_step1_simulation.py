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
        arrival_rate_per_hour=7.0,
        mean_processing_time_hours=0.30,
        due_date_factor=3.0,
        random_seed=42,
    )

    simulation = FactorySimulation(config)
    summary = simulation.run(until_hours=16.0)

    print("STEP 1 - Simulation Engine summary")
    for key, value in summary.items():
        print(f"{key}: {value}")

    print("\nFirst 10 events:")
    for event in simulation.event_log[:10]:
        print(event)


if __name__ == "__main__":
    main()

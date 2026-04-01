from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.simulation.engine import FactoryConfig, FactorySimulation
from services.simulation.observability import SimulationReporter
from services.simulation.scheduling import SchedulingPolicy


def main() -> None:
    sim = FactorySimulation(
        FactoryConfig(
            num_machines=4,
            arrival_rate_per_hour=8.0,
            mean_processing_time_hours=0.32,
            due_date_factor=3.2,
            scheduling_policy=SchedulingPolicy.QUEUE_BASED,
            enable_failures=True,
            weibull_shape=1.7,
            weibull_scale_hours=7.0,
            mean_repair_time_hours=0.8,
            repair_crews=1,
            preventive_maintenance_interval_hours=3.0,
            preventive_maintenance_duration_hours=0.5,
            random_seed=9,
        )
    )
    sim.run(until_hours=24.0)

    reporter = SimulationReporter(simulation=sim, output_dir=ROOT_DIR / "logs")
    metrics_path = reporter.write_metrics_json()
    jsonl_path = reporter.write_events_jsonl()
    csv_path = reporter.write_events_csv()

    metrics = reporter.build_metrics()
    print("STEP 4 - Simulation Metrics and Logging")
    print("makespan_hours:", metrics["makespan_hours"])
    print("utilization:", metrics["utilization"])
    print("downtime_hours:", metrics["downtime_hours"])
    print("avg_tardiness_hours:", metrics["avg_tardiness_hours"])
    print("avg_queue_length:", metrics["avg_queue_length"])
    print("throughput_jobs_per_hour:", metrics["throughput_jobs_per_hour"])
    print("events_logged:", metrics["events_logged"])
    print("metrics_file:", metrics_path)
    print("events_jsonl_file:", jsonl_path)
    print("events_csv_file:", csv_path)


if __name__ == "__main__":
    main()

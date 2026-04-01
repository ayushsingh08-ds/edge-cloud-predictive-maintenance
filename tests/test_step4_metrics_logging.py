from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.simulation.engine import FactoryConfig, FactorySimulation
from services.simulation.observability import SimulationReporter


def test_step4_metrics_and_files() -> None:
    sim = FactorySimulation(FactoryConfig(num_machines=2, random_seed=123))
    sim.run(until_hours=6.0)

    reporter = SimulationReporter(sim, output_dir=ROOT_DIR / "logs")
    metrics_file = reporter.write_metrics_json("test_metrics.json")
    events_file = reporter.write_events_jsonl("test_events.jsonl")

    assert metrics_file.exists()
    assert events_file.exists()

    payload = json.loads(metrics_file.read_text(encoding="utf-8"))
    assert "throughput_jobs_per_hour" in payload
    assert "machine_level" in payload

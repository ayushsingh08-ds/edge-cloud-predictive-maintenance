from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .engine import FactorySimulation
from .routing_analytics import analyze_routing


class SimulationReporter:
    def __init__(self, simulation: FactorySimulation, output_dir: str | Path = "logs") -> None:
        self.simulation = simulation
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build_metrics(self) -> dict[str, Any]:
        summary = self.simulation.summary()
        summary["operation_audit"] = self.build_operation_audit()
        summary["routing_analytics"] = self.build_routing_analytics()
        summary["machine_level"] = [
            {
                "machine_id": machine.machine_id,
                "processed_jobs": machine.processed_jobs,
                "busy_time": round(machine.busy_time, 4),
                "downtime": round(machine.downtime, 4),
                "failures": machine.failure_count,
                "preventive_maintenance": machine.preventive_maintenance_count,
            }
            for machine in self.simulation.machines
        ]
        return summary

    def operation_events(self) -> list[dict[str, Any]]:
        tracked_events = {
            "operation_started",
            "operation_routed",
            "operation_interrupted",
            "operation_completed",
            "job_rerouted",
        }
        return [
            event
            for event in self.simulation.event_log
            if str(event.get("event")) in tracked_events
        ]

    def build_operation_audit(self) -> dict[str, Any]:
        operation_events = self.operation_events()
        counts: dict[str, int] = {}
        for event in operation_events:
            key = str(event.get("event", "unknown"))
            counts[key] = counts.get(key, 0) + 1

        return {
            "total_operation_events": len(operation_events),
            "event_counts": counts,
            "timeline": operation_events,
        }

    def build_routing_analytics(self) -> dict[str, Any]:
        serialized_jobs: list[dict[str, Any]] = []
        for job in self.simulation.jobs:
            serialized_jobs.append(
                {
                    "job_id": job.job_id,
                    "operations": [
                        {
                            "op_id": operation.op_id,
                            "reroute_count": operation.reroute_count,
                            "processing_time": operation.processing_time,
                            "candidate_machines": operation.candidate_machines,
                        }
                        for operation in job.operations
                    ],
                }
            )
        return analyze_routing(serialized_jobs, self.operation_events())

    def write_events_jsonl(self, file_name: str = "simulation_events.jsonl") -> Path:
        output_path = self.output_dir / file_name
        with output_path.open("w", encoding="utf-8") as handle:
            for event in self.simulation.event_log:
                handle.write(json.dumps(event) + "\n")
        return output_path

    def write_events_csv(self, file_name: str = "simulation_events.csv") -> Path:
        output_path = self.output_dir / file_name
        if not self.simulation.event_log:
            output_path.write_text("", encoding="utf-8")
            return output_path

        keys = sorted({key for event in self.simulation.event_log for key in event.keys()})
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=keys)
            writer.writeheader()
            for event in self.simulation.event_log:
                writer.writerow(event)
        return output_path

    def write_metrics_json(self, file_name: str = "simulation_metrics.json") -> Path:
        output_path = self.output_dir / file_name
        output_path.write_text(
            json.dumps(self.build_metrics(), indent=2),
            encoding="utf-8",
        )
        return output_path

    def write_routing_analytics_json(self, file_name: str = "routing_analytics.json") -> Path:
        output_path = self.output_dir / file_name
        output_path.write_text(
            json.dumps(self.build_routing_analytics(), indent=2),
            encoding="utf-8",
        )
        return output_path

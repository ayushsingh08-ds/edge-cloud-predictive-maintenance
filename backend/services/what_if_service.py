from __future__ import annotations

from typing import Any

import simpy

from events import EventBus
from simulation.engine import FactorySimulationEngine

class WhatIfService:
    def __init__(self, main_engine: FactorySimulationEngine):
        self.main_engine = main_engine

    def run_scenario(self, scenario: dict[str, Any], lookahead_time: float = 3600.0) -> dict[str, Any]:
        """Branch simulation across policy candidates and return the best recommendation."""
        state = self.main_engine.capture_state()

        policy_matrix: list[tuple[str, str]] = [
            ("Balanced", "round_robin"),
            ("Shortest Queue", "least_loaded"),
            ("PdM-Priority", "weighted_cost"),
        ]

        branches: list[dict[str, Any]] = []
        for label, policy in policy_matrix:
            branch = self._run_branch(
                state=state,
                scenario=scenario,
                lookahead_time=lookahead_time,
                policy_label=label,
                policy_name=policy,
            )
            branches.append(branch)

        best_branch = max(branches, key=lambda item: item["score"])
        return {
            "start_time": float(state.get("now", 0.0)),
            "end_time": float(state.get("now", 0.0)) + float(lookahead_time),
            "scenario": scenario.get("name", "Unknown Scenario"),
            "projected_throughput": best_branch["projected_throughput"],
            "predicted_bottlenecks": best_branch["predicted_bottlenecks"],
            "recommended_policy_label": best_branch["policy_label"],
            "recommended_policy": best_branch["policy"],
            "policy_branches": branches,
            "recommendation": "Apply the best branch policy to reduce bottleneck risk.",
        }

    def _run_branch(
        self,
        *,
        state: dict[str, Any],
        scenario: dict[str, Any],
        lookahead_time: float,
        policy_label: str,
        policy_name: str,
    ) -> dict[str, Any]:
        env = simpy.Environment()
        bus = EventBus(env)
        clone = FactorySimulationEngine.from_layout_json(
            self.main_engine.layout_graph.to_json(),
            environment=env,
            event_bus=bus,
        )

        # Synchronize machine state before applying branch policy/scenario.
        for machine_id, props in state.get("machines", {}).items():
            machine = clone._machines.get(machine_id)
            if machine is None:
                continue
            machine.health = float(props.get("health", machine.health))
            machine.wear = float(props.get("wear", machine.wear))

        clone._routing_engine.set_policy(policy_name)
        clone.apply_scenario(scenario)

        start_time = float(env.now)
        clone.run(until=start_time + float(lookahead_time))

        throughput = len(clone.completed_jobs)
        bottlenecks: list[str] = []
        for machine_id, machine in clone._machines.items():
            if machine.calculate_congestion_risk() > 0.8:
                bottlenecks.append(machine_id)

        score = float(throughput) - (len(bottlenecks) * 5.0)
        return {
            "policy_label": policy_label,
            "policy": policy_name,
            "start_time": start_time,
            "end_time": float(env.now),
            "projected_throughput": throughput,
            "predicted_bottlenecks": bottlenecks,
            "score": round(score, 4),
        }

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
from threading import RLock
import numpy as np
import math
import logging

from events import Event, EventBus, EventType


@dataclass(slots=True)
class SQASolver:
    """
    Simulated Quantum Annealing (SQA) solver for QUBO problems.
    Uses Trotter slices to simulate quantum tunneling effects.
    """
    n_trotter: int = 8
    n_sweeps: int = 100
    
    def solve(self, Q: np.ndarray) -> np.ndarray:
        """
        Samples the QUBO Q-matrix using SQA.
        Q is an (N, N) matrix representing the Hamiltonian.
        """
        N = Q.shape[0]
        # Initial state: random spins for each Trotter slice
        # Using {0, 1} formulation for QUBO
        state = np.random.randint(0, 2, size=(self.n_trotter, N)).astype(np.float32)
        
        # Annealing schedules
        beta = 1.0  # Inverse classical temperature
        gamma_start = 2.0
        gamma_end = 0.01
        
        for sweep in range(self.n_sweeps):
            # Linearly decrease transverse field (gamma)
            gamma = gamma_start + (gamma_end - gamma_start) * (sweep / self.n_sweeps)
            # Quantum coupling strength
            j_perp = -0.5 * beta * math.log(math.tanh(gamma / self.n_trotter))
            
            for m in range(self.n_trotter):
                for i in range(N):
                    # Classical energy contribution
                    # dE = (1 - 2*state[m,i]) * (Q[i,i] + sum(Q[i,j]*state[m,j] for j!=i))
                    # Simplified for QUBO where x_i is {0, 1}
                    current_val = state[m, i]
                    other_val = 1 - current_val
                    
                    # Energy change if we flip state[m,i]
                    # Hamiltonian: H = x^T Q x
                    # We only care about the diff
                    e_fixed = Q[i, i] + np.dot(Q[i, :], state[m, :]) + np.dot(state[m, :], Q[:, i]) - 2 * Q[i, i] * current_val
                    delta_e_classical = (other_val - current_val) * e_fixed
                    
                    # Quantum energy contribution from adjacent Trotter slices
                    prev_m = (m - 1) % self.n_trotter
                    next_m = (m + 1) % self.n_trotter
                    delta_e_quantum = -j_perp * (other_val - current_val) * (state[prev_m, i] + state[next_m, i])
                    
                    # Metropolis criterion
                    if delta_e_classical + delta_e_quantum < 0 or np.random.rand() < math.exp(-(delta_e_classical + delta_e_quantum) * beta):
                        state[m, i] = other_val
                        
        # Return the slice with the lowest energy
        energies = [np.dot(state[m], np.dot(Q, state[m])) for m in range(self.n_trotter)]
        return state[np.argmin(energies)]


@dataclass(slots=True)
class RoutingEngine:
    event_bus: EventBus
    routing_policy: str = "weighted_cost"
    decisions: list[Event] = field(default_factory=list)
    _routing_results: dict[str, str] = field(default_factory=dict)
    _round_robin_index: dict[str, int] = field(default_factory=dict)
    _machine_provider: Callable[[str], dict[str, Any]] | None = None
    _queue_provider: Callable[[str], int] | None = None
    _node_type_provider: Callable[[str], str] | None = None
    _green_score_provider: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None = None
    _health_overrides: dict[str, float] = field(default_factory=dict)
    _pressure_overrides: dict[str, float] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock, init=False)

    def __post_init__(self) -> None:
        self.event_bus.subscribe(EventType.ROUTING_REQUEST, self.handle_routing_request)
        self.event_bus.subscribe(EventType.HEALTH_UPDATE, self.handle_health_update)
        self.event_bus.subscribe(EventType.HIGH_PRESSURE, self.handle_high_pressure)
        self.event_bus.subscribe(EventType.LOW_PRESSURE, self.handle_low_pressure)

    def handle_health_update(self, event: Event) -> None:
        machine_id = str(event.payload.get("machine_id", ""))
        if not machine_id:
            return
        health = event.payload.get("health")
        if health is None:
            return
        try:
            self._health_overrides[machine_id] = max(0.0, min(1.0, float(health)))
        except (TypeError, ValueError):
            return

    def handle_high_pressure(self, event: Event) -> None:
        node_id = str(event.payload.get("node_id", ""))
        if not node_id:
            return
        try:
            pressure = float(event.payload.get("pressure", 1.0))
        except (TypeError, ValueError):
            pressure = 1.0
        with self._lock:
            self._pressure_overrides[node_id] = max(0.0, min(1.0, pressure))

    def handle_low_pressure(self, event: Event) -> None:
        node_id = str(event.payload.get("node_id", ""))
        if not node_id:
            return
        try:
            pressure = float(event.payload.get("pressure", 0.0))
        except (TypeError, ValueError):
            pressure = 0.0
        with self._lock:
            if pressure <= 0.5:
                self._pressure_overrides.pop(node_id, None)
            else:
                self._pressure_overrides[node_id] = max(0.0, min(1.0, pressure))

    def configure_context(
        self,
        *,
        machine_provider: Callable[[str], dict[str, Any]],
        queue_provider: Callable[[str], int],
        node_type_provider: Callable[[str], str],
        green_score_provider: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None = None,
    ) -> None:
        self._machine_provider = machine_provider
        self._queue_provider = queue_provider
        self._node_type_provider = node_type_provider
        self._green_score_provider = green_score_provider

    def handle_routing_request(self, event: Event) -> None:
        request_id = str(event.payload.get("request_id", ""))
        # For QUBO solver state tracking
        solver_state = "Heuristic"
        if self.routing_policy == "qubo_sqa":
            solver_state = "Quantum Active"

        selected_to = self._select_target(event)
        if request_id and selected_to:
            self._routing_results[request_id] = selected_to

        decision = Event(
            event_type=EventType.ROUTING_DECISION,
            timestamp=event.timestamp,
            source="routing.engine",
            payload={
                "request_id": request_id,
                "job_id": event.payload.get("job_id"),
                "divider_id": event.payload.get("divider_id"),
                "to": selected_to,
                "policy": self.routing_policy,
                "solver_state": solver_state,
            },
        )
        self.decisions.append(decision)
        self.event_bus.publish(decision)

    def set_policy(self, policy: str) -> None:
        normalized = str(policy).strip().lower().replace("-", "_").replace(" ", "_")
        alias_map = {
            "pdm_priority": "pdm_rul",
            "shortest_queue": "least_loaded",
            "balanced": "round_robin",
        }
        normalized = alias_map.get(normalized, normalized)
        if normalized not in {"weighted_cost", "least_loaded", "random", "lowest_transport_time", "round_robin", "pdm_rul", "qubo_sqa"}:
            raise ValueError(
                "unsupported routing policy. use one of: weighted_cost, least_loaded, random, lowest_transport_time, round_robin, pdm_rul, qubo_sqa"
            )
        self.routing_policy = normalized
        if normalized == "qubo_sqa":
            logging.info("Routing Engine: QUBO/SQA Optimization Policy Activated.")

    def policy_info(self) -> dict[str, Any]:
        return {
            "active_policy": self.routing_policy,
            "supported_policies": ["weighted_cost", "least_loaded", "random", "lowest_transport_time", "round_robin", "pdm_rul", "qubo_sqa"],
        }

    def pending_count(self) -> int:
        return len(self._routing_results)

    def pop_decision(self, request_id: str) -> str | None:
        return self._routing_results.pop(request_id, None)

    def _select_target(self, event: Event) -> str | None:
        candidates = list(event.payload.get("candidates", []))
        if not candidates:
            return None

        machine_candidates: list[dict[str, Any]] = []
        buffer_candidates: list[dict[str, Any]] = []
        other_candidates: list[dict[str, Any]] = []

        for candidate in candidates:
            to_node = str(candidate.get("to_node", ""))
            node_type = self._node_type(to_node)
            item = {
                "to_node": to_node,
                "transport_time": float(candidate.get("transport_time", 0.0) or 0.0),
                "node_type": node_type,
            }
            if node_type == "Machine":
                machine_candidates.append(item)
            elif node_type == "Buffer":
                buffer_candidates.append(item)
            else:
                other_candidates.append(item)

        eligible_machines = [item for item in machine_candidates if self._machine_eligible(event, item)]
        eligible_buffers = [item for item in buffer_candidates if self._branch_pressure(item["to_node"]) < 0.5]

        if not eligible_machines:
            if eligible_buffers:
                return min(eligible_buffers, key=self._buffer_score)["to_node"]
            if other_candidates:
                return min(other_candidates, key=lambda item: item["transport_time"])["to_node"]
            return None

        best_machine = self._select_machine_by_policy(event, eligible_machines)
        return best_machine["to_node"]

    def _select_machine_by_policy(self, event: Event, eligible_machines: list[dict[str, Any]]) -> dict[str, Any]:
        if self.routing_policy == "random":
            import random

            return random.choice(eligible_machines)

        if self.routing_policy == "lowest_transport_time":
            return min(eligible_machines, key=lambda item: float(item.get("transport_time", 0.0)))

        if self.routing_policy == "qubo_sqa":
            return self._qubo_sqa_select(event, eligible_machines)

        return min(eligible_machines, key=lambda item: self._machine_score(event, item))

    def _qubo_sqa_select(self, event: Event, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Uses QUBO + SQA to select the optimal machine.
        Constructs a Hamiltonian where constraints are exponentially penalized.
        """
        N = len(candidates)
        if N == 1:
            return candidates[0]
            
        # 1. Build the Q matrix (Hamiltonian)
        # H = sum(c_i * x_i) + lambda * (sum(x_i) - 1)^2
        # Expanding the constraint: lambda * (sum(x_i^2) + sum(x_i*x_j) - 2*sum(x_i) + 1)
        # Since x_i is binary, x_i^2 = x_i.
        # H = sum((c_i - lambda) * x_i) + lambda * sum(x_i * x_j) + constant
        
        Q = np.zeros((N, N))
        lam = 50.0 # Penalty strength for the "Exactly One" constraint
        
        # 1.1 Get Green Scores from MES (Epsilon-Constraint)
        scored_candidates = candidates
        if self._green_score_provider:
            scored_candidates = self._green_score_provider(candidates)
            
        for i in range(N):
            machine_id = candidates[i]["to_node"]
            state = self._machine_state(machine_id)
            queue = float(self._queue_length(machine_id))
            transport = float(candidates[i].get("transport_time", 0.0))
            
            # --- Exponential Penalization Framework ---
            # 1. Health/RUL Penalty
            rul = float(state.get("predicted_rul", 100.0))
            health_penalty = 20.0 * math.exp(-0.1 * (rul - 30.0)) if rul < 50 else 0.0
            
            # 2. Capacity penalty (exponential)
            capacity_penalty = 5.0 * math.exp(0.5 * (queue - 10.0)) if queue > 5 else 0.0
            
            # 3. Sustainability Penalty (from MES Green Scores)
            green_score = scored_candidates[i].get("green_score", 1.0)
            # Penalty increases as green score decreases
            sustainability_penalty = 15.0 * (1.0 - green_score)
            
            # Linear cost coefficients (Diagonal terms)
            Q[i, i] = (queue * 1.0) + (transport * 0.5) + health_penalty + capacity_penalty + sustainability_penalty - (2 * lam)
            
            for j in range(i + 1, N):
                # Quadratic interaction terms (Off-diagonal)
                Q[i, j] = Q[j, i] = lam
        
        # 2. Solve using Simulated Quantum Annealing
        solver = SQASolver(n_trotter=8, n_sweeps=50)
        solution = solver.solve(Q)
        
        # 3. Interpret solution
        # If solver fails to find exactly one (e.g. all 0), fallback to heuristic
        if np.sum(solution) != 1:
            logging.warning(f"SQA Solver failed to converge to single selection (sum={np.sum(solution)}). Falling back to heuristic.")
            return min(candidates, key=lambda item: self._machine_score(event, item))
            
        selected_idx = np.argmax(solution)
        return candidates[selected_idx]

    def _machine_eligible(self, event: Event, item: dict[str, Any]) -> bool:
        if self._branch_pressure(item["to_node"]) >= 0.5:
            return False
        machine_state = self._machine_state(item["to_node"])
        if not machine_state.get("available", False):
            return False
        if float(machine_state.get("health", 0.0)) < float(event.payload.get("minimum_health", 0.4)):
            return False

        operation = event.payload.get("operation")
        capabilities = set(str(cap) for cap in machine_state.get("capabilities", []))
        if operation and capabilities and str(operation) not in capabilities:
            return False
        return True

    def _machine_score(self, event: Event, item: dict[str, Any]) -> float:
        machine_state = self._machine_state(item["to_node"])
        queue_length = self._queue_length(item["to_node"])
        
        # Policy: ML-Informed RUL Routing
        if self.routing_policy == "pdm_rul":
            # score = queue_length + (100 - predicted_RUL)
            predicted_rul = machine_state.get("predicted_rul")
            if predicted_rul is None:
                # Fallback: Assume healthy machine (RUL 100) if no prediction available
                predicted_rul = 100.0
            
            # Using the formula requested: lower is better
            return float(queue_length) + (100.0 - float(predicted_rul))

        # Default Policy: Weighted Cost (Heuristic + Health)
        health = float(machine_state.get("predicted_health", machine_state.get("health", 1.0)))
        queue_component = queue_length * 0.4
        health_component = (1.0 - health) * 0.6
        pressure_penalty = self._branch_pressure(item["to_node"]) * 2.0
        transport_time = float(item.get("transport_time", 0.0)) * 0.05
        return queue_component + health_component + pressure_penalty + transport_time

    def _buffer_score(self, item: dict[str, Any]) -> float:
        queue_length = self._queue_length(item["to_node"])
        transport_time = float(item.get("transport_time", 0.0))
        return queue_length * 1.2 + transport_time

    def _branch_pressure(self, node_id: str) -> float:
        return max(0.0, min(1.0, float(self._pressure_overrides.get(node_id, 0.0))))

    def _machine_state(self, machine_id: str) -> dict[str, Any]:
        if self._machine_provider is None:
            base = {
                "available": False,
                "health": 0.0,
                "predicted_health": 0.0,
                "predicted_rul": None,
                "processing_time": 1.0,
                "capabilities": [],
            }
        else:
            base = dict(self._machine_provider(machine_id))
        if machine_id in self._health_overrides:
            base["health"] = self._health_overrides[machine_id]
        base.setdefault("predicted_health", base.get("health", 0.0))
        return base

    def _queue_length(self, node_id: str) -> int:
        if self._queue_provider is None:
            return 0
        return self._queue_provider(node_id)

    def _node_type(self, node_id: str) -> str:
        if self._node_type_provider is None:
            return "Unknown"
        return self._node_type_provider(node_id)

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from events import Event, EventBus, EventType


@dataclass(slots=True)
class RoutingEngine:
    event_bus: EventBus
    routing_policy: str = "least_loaded"
    decisions: list[Event] = field(default_factory=list)
    _routing_results: dict[str, str] = field(default_factory=dict)
    _machine_provider: Callable[[str], dict[str, Any]] | None = None
    _queue_provider: Callable[[str], int] | None = None
    _node_type_provider: Callable[[str], str] | None = None
    _health_overrides: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.event_bus.subscribe(EventType.ROUTING_REQUEST, self.handle_routing_request)
        self.event_bus.subscribe(EventType.HEALTH_UPDATE, self.handle_health_update)

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

    def configure_context(
        self,
        *,
        machine_provider: Callable[[str], dict[str, Any]],
        queue_provider: Callable[[str], int],
        node_type_provider: Callable[[str], str],
    ) -> None:
        self._machine_provider = machine_provider
        self._queue_provider = queue_provider
        self._node_type_provider = node_type_provider

    def handle_routing_request(self, event: Event) -> None:
        request_id = str(event.payload.get("request_id", ""))
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
            },
        )
        self.decisions.append(decision)
        self.event_bus.publish(decision)

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

        if not eligible_machines:
            if buffer_candidates:
                return min(buffer_candidates, key=self._buffer_score)["to_node"]
            if other_candidates:
                return min(other_candidates, key=lambda item: item["transport_time"])["to_node"]
            return None

        best_machine = min(eligible_machines, key=lambda item: self._machine_score(event, item))
        return best_machine["to_node"]

    def _machine_eligible(self, event: Event, item: dict[str, Any]) -> bool:
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
        processing_time = float(machine_state.get("processing_time", 1.0))
        health = float(machine_state.get("health", 0.0))
        transport_time = float(item.get("transport_time", 0.0))

        due_date = event.payload.get("due_date")
        priority = int(event.payload.get("priority", 0) or 0)
        now = float(event.timestamp)
        completion_estimate = now + queue_length * processing_time + processing_time + transport_time

        tardiness_penalty = 0.0
        if due_date is not None:
            tardiness_penalty = max(0.0, completion_estimate - float(due_date)) * 8.0

        return (
            queue_length * 3.0
            + processing_time * 1.6
            + transport_time * 1.2
            + (1.0 - health) * 10.0
            + tardiness_penalty
            - priority * 1.5
        )

    def _buffer_score(self, item: dict[str, Any]) -> float:
        queue_length = self._queue_length(item["to_node"])
        transport_time = float(item.get("transport_time", 0.0))
        return queue_length * 1.2 + transport_time

    def _machine_state(self, machine_id: str) -> dict[str, Any]:
        if self._machine_provider is None:
            base = {"available": False, "health": 0.0, "processing_time": 1.0, "capabilities": []}
        else:
            base = dict(self._machine_provider(machine_id))
        if machine_id in self._health_overrides:
            base["health"] = self._health_overrides[machine_id]
        return base

    def _queue_length(self, node_id: str) -> int:
        if self._queue_provider is None:
            return 0
        return self._queue_provider(node_id)

    def _node_type(self, node_id: str) -> str:
        if self._node_type_provider is None:
            return "Unknown"
        return self._node_type_provider(node_id)

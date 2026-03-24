"""In-memory digital twin state manager."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone


class StateManager:
    """Own in-memory twin state and provide update methods for event handlers."""

    def __init__(self) -> None:
        self.state = {
            "machines": {},
            "products": {},
            "queues": {},
            "maintenance": {},
            "production_metrics": {
                "throughput": 0,
                "active_machines": 0,
                "completed_products": 0,
                "average_processing_time": 0.0,
            },
        }

    def update_machine_state(
        self,
        machine_id: int,
        status: str,
        health: float | None = None,
        current_product: str | None = None,
        queue_length: int | None = None,
    ) -> None:
        key = str(machine_id)
        machine = self.state["machines"].setdefault(
            key,
            {
                "machine_id": machine_id,
                "status": "unknown",
                "health": None,
                "current_product": None,
                "queue_length": 0,
            },
        )
        machine["status"] = status
        if health is not None:
            machine["health"] = float(health)
        if current_product is not None:
            machine["current_product"] = current_product
        if queue_length is not None:
            machine["queue_length"] = int(queue_length)

    def update_product_position(
        self,
        product_id: str,
        current_location: int | str,
        status: str,
        route: list[int] | list[str] | None = None,
    ) -> None:
        key = str(product_id)
        product = self.state["products"].setdefault(
            key,
            {
                "product_id": str(product_id),
                "current_location": None,
                "status": "created",
                "route": [],
            },
        )
        product["current_location"] = current_location
        product["status"] = status
        if route is not None:
            product["route"] = list(route)

    def update_queue(
        self,
        machine_id: int,
        queue_length: int,
        products_in_queue: list[str] | None = None,
    ) -> None:
        key = str(machine_id)
        self.state["queues"][key] = {
            "machine_id": machine_id,
            "queue_length": max(0, int(queue_length)),
            "products_in_queue": products_in_queue or [],
        }
        self.update_machine_state(machine_id=machine_id, status=self.state["machines"].get(key, {}).get("status", "unknown"), queue_length=max(0, int(queue_length)))

    def update_health(self, machine_id: int, health: float) -> None:
        current_status = self.state["machines"].get(str(machine_id), {}).get("status", "unknown")
        self.update_machine_state(machine_id=machine_id, status=current_status, health=float(health))

    def update_maintenance(
        self,
        machine_id: int,
        maintenance_status: str,
        scheduled_date: str | None = None,
    ) -> None:
        key = str(machine_id)
        self.state["maintenance"][key] = {
            "machine_id": machine_id,
            "maintenance_status": maintenance_status,
            "scheduled_date": scheduled_date,
        }
        if maintenance_status in {"scheduled", "in_progress"}:
            self.update_machine_state(machine_id=machine_id, status="maintenance")

    def update_metrics(self, metrics: dict) -> None:
        self.state["production_metrics"].update(metrics)

    def recompute_metrics(self) -> None:
        machines = self.state["machines"]
        products = self.state["products"]
        active_machines = sum(1 for entry in machines.values() if entry.get("status") == "running")
        completed_products = sum(1 for entry in products.values() if entry.get("status") == "completed")
        self.state["production_metrics"]["active_machines"] = active_machines
        self.state["production_metrics"]["completed_products"] = completed_products
        self.state["production_metrics"]["throughput"] = completed_products

    def build_twin_state(self) -> dict:
        snapshot = deepcopy(self.state)
        snapshot["timestamp"] = datetime.now(timezone.utc).isoformat()
        return snapshot

    def publish_twin_state(self, publisher) -> dict:
        payload = self.build_twin_state()
        payload["event_name"] = "twin.state.updated"
        publisher.publish("twin.state.updated", payload)
        return payload

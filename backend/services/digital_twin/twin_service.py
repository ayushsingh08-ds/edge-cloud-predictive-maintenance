"""Digital Twin state service for real-time virtual factory representation."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from messaging.rabbitmq_client import RabbitMQClient
from services.digital_twin import twin_repository
from services.digital_twin.state_manager import StateManager


class DigitalTwinService:
    """Subscribe to cross-service events and maintain the full twin state."""

    def __init__(self, publisher: RabbitMQClient | None = None) -> None:
        self.client = publisher or RabbitMQClient()
        self.state_manager = StateManager()

        persisted = twin_repository.get_full_twin_state()
        self.state_manager.state["machines"] = persisted.get("machines", {})
        self.state_manager.state["products"] = persisted.get("products", {})
        self.state_manager.state["queues"] = persisted.get("queues", {})
        self.state_manager.state["maintenance"] = persisted.get("maintenance", {})
        self.state_manager.state["production_metrics"].update(
            persisted.get("production_metrics", {})
        )

    @staticmethod
    def _safe_int(value) -> int:
        if value is None:
            raise ValueError("Expected integer-like value")
        if isinstance(value, int):
            return value
        text = str(value)
        digits = "".join(ch for ch in text if ch.isdigit())
        return int(digits) if digits else int(text)

    @staticmethod
    def _to_iso(value) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc).isoformat()
            return value.isoformat()
        return str(value)

    def _persist_current_state(self) -> dict:
        return twin_repository.store_twin_snapshot(self.state_manager.state)

    def _publish_current_state(self) -> dict:
        self.state_manager.recompute_metrics()
        return self.state_manager.publish_twin_state(self.client)

    def _handle_machine_registered(self, payload: dict) -> None:
        machine_id = self._safe_int(payload.get("machine_id"))
        self.state_manager.update_machine_state(machine_id=machine_id, status="running")
        twin_repository.update_machine_state(machine_id=machine_id, status="running")

    def _handle_machine_status_changed(self, payload: dict) -> None:
        machine_id = self._safe_int(payload.get("machine_id"))
        new_status = str(payload.get("new_status", "unknown"))
        self.state_manager.update_machine_state(machine_id=machine_id, status=new_status)
        twin_repository.update_machine_state(machine_id=machine_id, status=new_status)

    def _handle_machine_health_updated(self, payload: dict) -> None:
        machine_id = self._safe_int(payload.get("machine_id"))
        health = float(payload.get("health_score", 0.0))
        self.state_manager.update_health(machine_id=machine_id, health=health)
        twin_repository.update_machine_health(machine_id=machine_id, health=health)

    def _handle_maintenance_scheduled(self, payload: dict) -> None:
        machine_id = self._safe_int(payload.get("machine_id"))
        scheduled_date = self._to_iso(payload.get("scheduled_date"))
        self.state_manager.update_maintenance(
            machine_id=machine_id,
            maintenance_status="scheduled",
            scheduled_date=scheduled_date,
        )
        twin_repository.update_maintenance_state(
            machine_id=machine_id,
            maintenance_status="scheduled",
            scheduled_date=scheduled_date,
        )

    def _handle_maintenance_completed(self, payload: dict) -> None:
        machine_id = self._safe_int(payload.get("machine_id"))
        self.state_manager.update_maintenance(
            machine_id=machine_id,
            maintenance_status="completed",
            scheduled_date=self._to_iso(payload.get("scheduled_date")),
        )
        self.state_manager.update_machine_state(machine_id=machine_id, status="running")
        twin_repository.update_maintenance_state(
            machine_id=machine_id,
            maintenance_status="completed",
            scheduled_date=self._to_iso(payload.get("scheduled_date")),
        )
        twin_repository.update_machine_state(machine_id=machine_id, status="running")

    def _handle_product_created(self, payload: dict) -> None:
        product_id = str(payload.get("product_id"))
        location = payload.get("start_node", payload.get("current_node", payload.get("machine_id")))

        self.state_manager.update_product_position(
            product_id=product_id,
            current_location=location,
            status="created",
            route=[],
        )
        twin_repository.update_product_position(
            product_id=product_id,
            current_location=location,
            status="created",
            route=[],
        )

    def _handle_product_moved(self, payload: dict) -> None:
        product_id = str(payload.get("product_id"))
        to_node = payload.get("to_node", payload.get("machine_id"))

        current_route = self.state_manager.state["products"].get(product_id, {}).get("route", [])
        if to_node is not None:
            current_route = [*current_route, to_node]

        self.state_manager.update_product_position(
            product_id=product_id,
            current_location=to_node,
            status="in_progress",
            route=current_route,
        )
        twin_repository.update_product_position(
            product_id=product_id,
            current_location=to_node,
            status="in_progress",
            route=current_route,
        )

    def _handle_product_completed(self, payload: dict) -> None:
        product_id = str(payload.get("product_id"))
        end_node = payload.get("end_node", payload.get("machine_id"))
        current_route = self.state_manager.state["products"].get(product_id, {}).get("route", [])
        if end_node is not None and (not current_route or current_route[-1] != end_node):
            current_route = [*current_route, end_node]

        self.state_manager.update_product_position(
            product_id=product_id,
            current_location=end_node,
            status="completed",
            route=current_route,
        )
        twin_repository.update_product_position(
            product_id=product_id,
            current_location=end_node,
            status="completed",
            route=current_route,
        )

    def _handle_machine_queue_updated(self, payload: dict) -> None:
        machine_id = self._safe_int(payload.get("machine_id"))
        queue_length = int(payload.get("queue_length", 0))
        products_in_queue = payload.get("products_in_queue") or []

        self.state_manager.update_queue(
            machine_id=machine_id,
            queue_length=queue_length,
            products_in_queue=products_in_queue,
        )
        twin_repository.update_queue_state(
            machine_id=machine_id,
            queue_length=queue_length,
            products_in_queue=products_in_queue,
        )

    def _handle_routing_decision(self, payload: dict) -> None:
        product_id = str(payload.get("product_id"))
        route = payload.get("route") or []

        if not product_id:
            return

        existing = self.state_manager.state["products"].get(product_id)
        if existing is None:
            self.state_manager.update_product_position(
                product_id=product_id,
                current_location=payload.get("current_node"),
                status="in_progress",
                route=route,
            )
        else:
            self.state_manager.update_product_position(
                product_id=product_id,
                current_location=existing.get("current_location"),
                status=existing.get("status", "in_progress"),
                route=route,
            )

        twin_repository.update_product_position(
            product_id=product_id,
            current_location=self.state_manager.state["products"][product_id].get("current_location"),
            status=self.state_manager.state["products"][product_id].get("status", "in_progress"),
            route=self.state_manager.state["products"][product_id].get("route", []),
        )

    def process_event(self, routing_key: str, payload: dict) -> dict:
        handlers = {
            "machine.registered": self._handle_machine_registered,
            "machine.status.changed": self._handle_machine_status_changed,
            "machine.health.updated": self._handle_machine_health_updated,
            "maintenance.scheduled": self._handle_maintenance_scheduled,
            "maintenance.completed": self._handle_maintenance_completed,
            "product.created": self._handle_product_created,
            "product.moved": self._handle_product_moved,
            "product.completed": self._handle_product_completed,
            "machine.queue.updated": self._handle_machine_queue_updated,
            "routing.decision": self._handle_routing_decision,
        }

        handler = handlers.get(routing_key)
        if handler is not None:
            handler(payload)

        self.state_manager.recompute_metrics()
        persisted = self._persist_current_state()
        _ = persisted  # persisted snapshot maintained for DB traceability
        return self._publish_current_state()

    def get_twin_state_snapshot(self) -> dict:
        self.state_manager.recompute_metrics()
        return self.state_manager.build_twin_state()

    def start(self) -> None:
        """Subscribe to relevant topics and update digital twin continuously."""
        print("[+] Digital Twin Service listening for factory events...")

        result = self.client.channel.queue_declare(queue="", exclusive=True)
        queue_name = result.method.queue

        topics = [
            "machine.registered",
            "machine.status.changed",
            "machine.health.updated",
            "maintenance.scheduled",
            "maintenance.completed",
            "product.created",
            "product.moved",
            "product.completed",
            "machine.queue.updated",
            "routing.decision",
        ]

        for topic in topics:
            self.client.channel.queue_bind(
                exchange="sensor_exchange",
                queue=queue_name,
                routing_key=topic,
            )

        def callback(ch, method, properties, body):
            try:
                payload = json.loads(body)
                routing_key = getattr(method, "routing_key", "")
                self.process_event(routing_key, payload)
            except Exception as exc:
                print(f"[ERROR] Digital Twin event handling failed: {exc}")

        self.client.channel.basic_consume(
            queue=queue_name,
            on_message_callback=callback,
            auto_ack=True,
        )
        self.client.channel.start_consuming()

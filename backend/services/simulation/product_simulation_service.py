"""Product flow simulation service for factory production movement."""

from __future__ import annotations

from datetime import datetime, timezone

from messaging.rabbitmq_client import RabbitMQClient
from services.routing_engine.routing_repository import get_machine_id_for_node
from services.routing_engine.routing_service import RoutingEngineService
from services.simulation.machine_processor import MachineProcessor
from services.simulation.queue_manager import QueueManager
from services.simulation import simulation_repository


class ProductSimulationService:
    """Main orchestrator for product creation, movement, processing, and completion."""

    def __init__(
        self,
        publisher: RabbitMQClient | None = None,
        routing_engine: RoutingEngineService | None = None,
        speed_factor: float = 0.0,
    ) -> None:
        self.client = publisher or RabbitMQClient()
        self.routing_engine = routing_engine or RoutingEngineService(publisher=self.client)
        self.queue_manager = QueueManager()
        self.machine_processor = MachineProcessor(
            routing_engine=self.routing_engine,
            speed_factor=speed_factor,
        )

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_product(self, product_id: str, start_node: int) -> dict:
        product = simulation_repository.create_product(product_id, start_node)
        simulation_repository.store_product_history(product_id, start_node)

        self.publish_product_events(
            topic="product.created",
            payload={
                "event_name": "product.created",
                "product_id": product_id,
                "start_node": start_node,
                "current_node": start_node,
                "timestamp": self._now_iso(),
            },
        )
        return product

    def move_product(self, product_id: str, to_node: int) -> dict:
        product = simulation_repository.get_product(product_id)
        if product is None:
            raise ValueError(f"Product {product_id} not found")

        from_node = int(product["current_node_id"])
        updated = simulation_repository.update_product_location(product_id, to_node)
        if updated is None:
            raise ValueError(f"Product {product_id} not found")

        simulation_repository.update_product_status(product_id, "in_progress")
        simulation_repository.store_product_history(product_id, to_node)

        self.publish_product_events(
            topic="product.moved",
            payload={
                "event_name": "product.moved",
                "product_id": product_id,
                "from_node": from_node,
                "to_node": to_node,
                "timestamp": self._now_iso(),
            },
        )

        return updated

    def update_queue(self, machine_id: int, queue_length: int) -> dict:
        queue_state = simulation_repository.update_queue(machine_id, queue_length)
        self.publish_product_events(
            topic="machine.queue.updated",
            payload={
                "event_name": "machine.queue.updated",
                "machine_id": machine_id,
                "queue_length": queue_state["queue_length"],
                "timestamp": self._now_iso(),
            },
        )
        return queue_state

    def process_product(self, machine_id: int, product_id: str, processing_time: float = 1.0) -> dict:
        queue_length = self.queue_manager.add_to_queue(machine_id, product_id)
        self.update_queue(machine_id, queue_length)

        current = self.queue_manager.remove_from_queue(machine_id)
        if current is None:
            raise RuntimeError(f"Queue removal failed for machine {machine_id}")

        self.update_queue(machine_id, self.queue_manager.get_queue_length(machine_id))
        self.machine_processor.process_product(machine_id, product_id, processing_time)

        next_node = self.machine_processor.send_product_to_next_node(product_id)
        if next_node is None:
            completed = self.complete_product(product_id)
            return {
                "product_id": product_id,
                "status": completed["status"],
                "next_node": None,
            }

        self.move_product(product_id, next_node)
        return {
            "product_id": product_id,
            "status": "in_progress",
            "next_node": next_node,
        }

    def complete_product(self, product_id: str) -> dict:
        product = simulation_repository.get_product(product_id)
        if product is None:
            raise ValueError(f"Product {product_id} not found")

        updated = simulation_repository.update_product_status(product_id, "completed")
        if updated is None:
            raise ValueError(f"Product {product_id} not found")

        end_node = product.get("current_node_id")
        self.publish_product_events(
            topic="product.completed",
            payload={
                "event_name": "product.completed",
                "product_id": product_id,
                "end_node": end_node,
                "timestamp": self._now_iso(),
            },
        )
        return updated

    def publish_product_events(self, topic: str, payload: dict) -> None:
        self.client.publish(topic, payload)

    def get_product_history(self, product_id: str) -> list[dict]:
        return simulation_repository.get_product_history(product_id)

    def run_step(self, product_id: str, processing_time: float = 1.0) -> dict:
        """Run one simulation step for a product at its current machine node."""
        product = simulation_repository.get_product(product_id)
        if product is None:
            raise ValueError(f"Product {product_id} not found")

        current_node = product.get("current_node_id")
        if current_node is None:
            raise ValueError(f"Product {product_id} has no current node")

        machine_id = get_machine_id_for_node(int(current_node))
        if machine_id is None:
            next_node = self.machine_processor.send_product_to_next_node(product_id)
            if next_node is None:
                completed = self.complete_product(product_id)
                return {
                    "product_id": product_id,
                    "status": completed["status"],
                    "next_node": None,
                }

            self.move_product(product_id, next_node)
            return {
                "product_id": product_id,
                "status": "in_progress",
                "next_node": next_node,
            }

        return self.process_product(machine_id, product_id, processing_time)

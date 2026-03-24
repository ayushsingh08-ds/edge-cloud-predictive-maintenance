"""Machine processing simulation helpers."""

from __future__ import annotations

import time

from services.routing_engine.routing_service import RoutingEngineService
from services.simulation import simulation_repository


class MachineProcessor:
    """Simulate machine processing and determine next node via routing engine."""

    def __init__(self, routing_engine: RoutingEngineService, speed_factor: float = 1.0) -> None:
        self.routing_engine = routing_engine
        self.speed_factor = max(0.0, speed_factor)

    def process_product(self, machine_id: int, product_id: str, processing_time: float) -> None:
        self.simulate_processing_delay(processing_time)

    def simulate_processing_delay(self, processing_time: float = 1.0) -> None:
        if self.speed_factor == 0.0:
            return
        delay = max(0.0, processing_time) * self.speed_factor
        time.sleep(delay)

    def send_product_to_next_node(self, product_id: str) -> int | None:
        product = simulation_repository.get_product(product_id)
        if product is None:
            raise ValueError(f"Product {product_id} not found")

        current_node = int(product["current_node_id"])
        next_choice = self.routing_engine.decide_next_machine(
            product_id=product_id,
            current_node=current_node,
        )
        if next_choice is None:
            return None

        return int(next_choice["node_id"])

"""Integration-style test for Product Flow Simulation service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import delete

from database.db_session import SessionLocal
from database.init_db import init_db
from database.models.machine import Machine
from database.models.machine_queue import MachineQueue
from database.models.product_history import ProductHistory
from database.models.production_edge import ProductionEdge
from database.models.production_node import ProductionNode
from database.models.route import Route
from database.models.sim_product import SimProduct
from services.production_graph.graph_service import ProductionGraphService
from services.routing_engine.routing_service import RoutingEngineService
from services.simulation.product_simulation_service import ProductSimulationService
from services.simulation import simulation_repository


@dataclass
class PublishedEvent:
    topic: str
    payload: dict


class TestPublisher:
    """Captures published events for deterministic verification."""

    def __init__(self) -> None:
        self.events: list[PublishedEvent] = []

    def publish(self, topic: str, message: dict) -> None:
        self.events.append(PublishedEvent(topic=topic, payload=message))


def print_header(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_product_simulation_test() -> None:
    print_header("Product Simulation Test Started")

    print("[1/15] Initializing database schema...")
    init_db()

    db = SessionLocal()
    publisher = TestPublisher()

    routing_engine = RoutingEngineService(
        max_queue_length=5,
        health_threshold=0.5,
        publisher=publisher,
    )
    simulation_service = ProductSimulationService(
        publisher=publisher,
        routing_engine=routing_engine,
        speed_factor=0.0,
    )
    graph_service = ProductionGraphService()

    try:
        print("[2/15] Resetting simulation and graph tables for deterministic run...")
        db.execute(delete(ProductHistory))
        db.execute(delete(SimProduct))
        db.execute(delete(MachineQueue))
        db.execute(delete(Route))
        db.execute(delete(ProductionEdge))
        db.execute(delete(ProductionNode))
        db.commit()

        print("[3/15] Creating production nodes: Machine A, Conveyor, Machine B, Machine C...")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

        machine_a = Machine(
            name=f"Machine A - Sim Test {stamp}",
            type="CNC",
            location="Line 1 - A",
            status="running",
        )
        machine_b = Machine(
            name=f"Machine B - Sim Test {stamp}",
            type="Assembly",
            location="Line 1 - B",
            status="running",
        )
        machine_c = Machine(
            name=f"Machine C - Sim Test {stamp}",
            type="Final",
            location="Line 1 - C",
            status="running",
        )
        db.add_all([machine_a, machine_b, machine_c])
        db.commit()
        db.refresh(machine_a)
        db.refresh(machine_b)
        db.refresh(machine_c)

        node_a = graph_service.add_machine_node(machine_a.id, "Machine A")
        node_conveyor = graph_service.add_conveyor_node("Conveyor")
        node_b = graph_service.add_machine_node(machine_b.id, "Machine B")
        node_c = graph_service.add_machine_node(machine_c.id, "Machine C")

        print("[4/15] Connecting nodes...")
        graph_service.connect_nodes(node_a["id"], node_conveyor["id"])
        graph_service.connect_nodes(node_conveyor["id"], node_b["id"])
        graph_service.connect_nodes(node_b["id"], node_c["id"])

        print("[5/15] Creating product at Machine A...")
        product_id = "P001"
        simulation_service.create_product(product_id, node_a["id"])
        print("Product Created: P001 at Machine A")

        print("[6/15] Adding product to Machine A queue...")
        q_a_add = simulation_service.queue_manager.add_to_queue(machine_a.id, product_id)
        simulation_service.update_queue(machine_a.id, q_a_add)
        print(f"Queue Updated: Machine A Queue = {q_a_add}")

        print("[7/15] Simulating processing at Machine A...")
        popped_a = simulation_service.queue_manager.remove_from_queue(machine_a.id)
        _ensure(popped_a == product_id, "Machine A queue did not return expected product")
        simulation_service.update_queue(
            machine_a.id,
            simulation_service.queue_manager.get_queue_length(machine_a.id),
        )
        simulation_service.machine_processor.process_product(machine_a.id, product_id, 0.0)
        print("Processing Product at Machine A")

        print("[8/15] Moving product to Conveyor...")
        next_from_a = simulation_service.machine_processor.send_product_to_next_node(product_id)
        _ensure(next_from_a == node_conveyor["id"], "Expected next node Conveyor from Machine A")
        simulation_service.move_product(product_id, next_from_a)
        print("Product Moved: Machine A -> Conveyor")

        print("[9/15] Moving product to Machine B...")
        next_from_conveyor = simulation_service.machine_processor.send_product_to_next_node(product_id)
        _ensure(next_from_conveyor == node_b["id"], "Expected next node Machine B from Conveyor")
        simulation_service.move_product(product_id, next_from_conveyor)
        print("Product Moved: Conveyor -> Machine B")

        print("[10/15] Adding product to Machine B queue...")
        q_b_add = simulation_service.queue_manager.add_to_queue(machine_b.id, product_id)
        simulation_service.update_queue(machine_b.id, q_b_add)
        print(f"Queue Updated: Machine B Queue = {q_b_add}")

        print("[11/15] Simulating processing at Machine B...")
        popped_b = simulation_service.queue_manager.remove_from_queue(machine_b.id)
        _ensure(popped_b == product_id, "Machine B queue did not return expected product")
        simulation_service.update_queue(
            machine_b.id,
            simulation_service.queue_manager.get_queue_length(machine_b.id),
        )
        simulation_service.machine_processor.process_product(machine_b.id, product_id, 0.0)
        print("Processing Product at Machine B")

        print("[12/15] Moving product to Machine C...")
        next_from_b = simulation_service.machine_processor.send_product_to_next_node(product_id)
        _ensure(next_from_b == node_c["id"], "Expected next node Machine C from Machine B")
        simulation_service.move_product(product_id, next_from_b)
        print("Product Moved: Machine B -> Machine C")

        print("[13/15] Marking product as completed...")
        completed = simulation_service.complete_product(product_id)
        _ensure(completed["status"] == "completed", "Product status should be completed")
        print("Product Completed: P001")

        print("[14/15] Printing product movement history, queue updates, and status...")
        history = simulation_service.get_product_history(product_id)
        product = simulation_repository.get_product(product_id)
        _ensure(product is not None, "Product should exist")

        node_name_by_id = {
            node_a["id"]: "Machine A",
            node_conveyor["id"]: "Conveyor",
            node_b["id"]: "Machine B",
            node_c["id"]: "Machine C",
        }

        path_names = [node_name_by_id.get(item["node_id"], str(item["node_id"])) for item in history]

        print("\nProduct History:")
        print(" -> ".join(path_names))

        print("\nQueue Updates:")
        queue_events = [event for event in publisher.events if event.topic == "machine.queue.updated"]
        for event in queue_events:
            payload = event.payload
            print(
                f"machine_id={payload.get('machine_id')} "
                f"queue_length={payload.get('queue_length')}"
            )

        print("\nProduct Status:")
        print(
            f"product_id={product['product_id']} "
            f"current_node_id={product['current_node_id']} status={product['status']}"
        )

        print("[15/15] Printing all published events and verifying goals...")
        print("\nPublished Events:")
        for event in publisher.events:
            print(f"{event.topic} -> {event.payload}")

        topics = [event.topic for event in publisher.events]
        _ensure("product.created" in topics, "product.created event missing")
        _ensure(topics.count("product.moved") >= 3, "Expected at least 3 product.moved events")
        _ensure("product.completed" in topics, "product.completed event missing")
        _ensure(
            topics.count("machine.queue.updated") >= 4,
            "Expected queue update events for add/remove on both machines",
        )

        expected_path = ["Machine A", "Conveyor", "Machine B", "Machine C"]
        _ensure(path_names == expected_path, f"Unexpected product path: {path_names}")
        _ensure(product["status"] == "completed", "Product status should be completed")

        print("\nProduct Flow Simulation Test Completed Successfully.")

    except Exception as exc:
        db.rollback()
        print_header("TEST FAILED")
        print(f"Error: {exc}")
        raise
    finally:
        db.close()
        print("\nDatabase session closed.")


if __name__ == "__main__":
    run_product_simulation_test()

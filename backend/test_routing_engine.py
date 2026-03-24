"""Integration-style test for Routing Engine service.

This test verifies routing decisions using production graph topology,
machine health, maintenance status, and queue/load proxy values.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import delete

from database.db_session import SessionLocal
from database.init_db import init_db
from database.models.machine import Machine
from database.models.machine_health import MachineHealth
from database.models.maintenance_task import MaintenanceTask
from database.models.production_edge import ProductionEdge
from database.models.production_node import ProductionNode
from database.models.route import Route
from services.production_graph.graph_service import ProductionGraphService
from services.routing_engine.routing_service import RoutingEngineService


@dataclass
class PublishedEvent:
    topic: str
    payload: dict


class TestPublisher:
    """Simple publisher stub to capture routing events."""

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


def _topic_count(publisher: TestPublisher, topic: str) -> int:
    return sum(1 for event in publisher.events if event.topic == topic)


def run_routing_engine_test() -> None:
    print_header("Routing Engine Test Started")

    print("[1/11] Initializing database schema...")
    init_db()

    db = SessionLocal()
    graph_service = ProductionGraphService()
    publisher = TestPublisher()
    routing_service = RoutingEngineService(
        max_queue_length=5,
        health_threshold=0.5,
        publisher=publisher,
    )

    try:
        print("[2/11] Resetting graph-specific tables for deterministic setup...")
        db.execute(delete(Route))
        db.execute(delete(ProductionEdge))
        db.execute(delete(ProductionNode))
        db.commit()

        print("[3/11] Creating machines and production nodes...")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

        machine_a = Machine(
            name=f"Machine A - Routing Test {stamp}",
            type="CNC",
            location="Line 1 - A",
            status="running",
        )
        machine_b = Machine(
            name=f"Machine B - Routing Test {stamp}",
            type="Assembly",
            location="Line 1 - B",
            status="running",
        )
        machine_c = Machine(
            name=f"Machine C - Routing Test {stamp}",
            type="Inspection",
            location="Line 1 - C",
            status="maintenance",
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

        print("Factory Graph Created")

        print("[4/11] Connecting nodes...")
        graph_service.connect_nodes(node_a["id"], node_conveyor["id"])
        graph_service.connect_nodes(node_conveyor["id"], node_b["id"])
        graph_service.connect_nodes(node_conveyor["id"], node_c["id"])

        print("[5/11] Loading machine health...")
        db.add_all(
            [
                MachineHealth(
                    machine_id=machine_b.id,
                    health_score=0.9,
                    anomaly_score=0.1,
                    rul_hours=120.0,
                ),
                MachineHealth(
                    machine_id=machine_c.id,
                    health_score=0.4,
                    anomaly_score=0.6,
                    rul_hours=20.0,
                ),
            ]
        )
        db.commit()
        print("Machine Health Loaded")

        print("[6/11] Loading maintenance and queue proxy data...")
        # Queue/load proxy in current repository implementation uses open maintenance tasks.
        queue_tasks = [
            MaintenanceTask(
                machine_id=machine_b.id,
                task_type="queue_proxy",
                priority="low",
                status="scheduled",
            ),
            MaintenanceTask(
                machine_id=machine_b.id,
                task_type="queue_proxy",
                priority="low",
                status="scheduled",
            ),
            MaintenanceTask(
                machine_id=machine_b.id,
                task_type="queue_proxy",
                priority="low",
                status="scheduled",
            ),
            MaintenanceTask(
                machine_id=machine_c.id,
                task_type="maintenance",
                priority="high",
                status="scheduled",
            ),
        ]
        db.add_all(queue_tasks)
        db.commit()

        print("Maintenance Status Loaded")
        print("Queue Load Loaded")

        print("[7/11] Creating product at Machine A and deciding next machine...")
        product_id = f"P-ROUTE-{stamp}"
        print("Product Created at Machine A")

        # Step through topology: A -> Conveyor, then choose between B and C.
        next_from_a = routing_service.decide_next_machine(product_id, node_a["id"])
        _ensure(next_from_a is not None, "Expected next node from Machine A")
        _ensure(next_from_a["node_id"] == node_conveyor["id"], "Expected Conveyor as next hop")

        decision = routing_service.decide_next_machine(product_id, node_conveyor["id"])
        _ensure(decision is not None, "Expected routing decision from Conveyor")

        print("[8/11] Assigning route for product...")
        assigned_route = routing_service.assign_route(
            product_id=product_id,
            start_node=node_a["id"],
            end_node=node_b["id"],
        )

        id_to_name = {
            node_a["id"]: "Machine A",
            node_conveyor["id"]: "Conveyor",
            node_b["id"]: "Machine B",
            node_c["id"]: "Machine C",
        }

        route_names = [id_to_name.get(node_id, str(node_id)) for node_id in assigned_route]

        _ensure(decision["node_id"] == node_b["id"], "Routing should choose Machine B")
        _ensure(
            assigned_route == [node_a["id"], node_conveyor["id"], node_b["id"]],
            f"Unexpected route: {assigned_route}",
        )

        print("[9/11] Printing routing decision...")
        print("Routing Decision:")
        print(f"Next Machine: {id_to_name.get(decision['node_id'], decision['node_id'])}")
        print(f"Route: {' -> '.join(route_names)}")

        print("[10/11] Printing explanation of decision...")
        print("Reason:")
        print("Machine C unavailable (maintenance)")
        print("Machine C unavailable (health below threshold)")
        print("Machine B healthy and available")
        print("Machine B queue is moderate (3)")

        print("[11/11] Verifying routing events and integration goals...")
        _ensure(_topic_count(publisher, "routing.decision") >= 1, "routing.decision not published")
        _ensure(
            _topic_count(publisher, "product.route.assigned") >= 1,
            "product.route.assigned not published",
        )

        print("routing.decision Event Published")
        print("product.route.assigned Event Published")

        print("\nRouting Engine Test Completed Successfully.")

    except Exception as exc:
        db.rollback()
        print_header("TEST FAILED")
        print(f"Error: {exc}")
        raise
    finally:
        db.close()
        print("\nDatabase session closed.")


if __name__ == "__main__":
    run_routing_engine_test()

"""Integration-style test for Digital Twin State Service."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete

from database.db_session import SessionLocal
from database.init_db import init_db
from database.models.twin_snapshot import TwinSnapshot
from services.digital_twin.twin_service import DigitalTwinService
from services.digital_twin import twin_repository


@dataclass
class PublishedEvent:
    topic: str
    payload: dict


class TestPublisher:
    """Captures published events for deterministic assertions."""

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


def run_digital_twin_test() -> None:
    print_header("Digital Twin Test Started")

    print("[1/10] Initializing DB schema and resetting twin snapshots...")
    init_db()
    db = SessionLocal()
    try:
        db.execute(delete(TwinSnapshot))
        db.commit()
    finally:
        db.close()

    publisher = TestPublisher()
    twin_service = DigitalTwinService(publisher=publisher)

    try:
        print("[2/10] Registering two machines...")
        twin_service.process_event(
            "machine.registered",
            {
                "machine_id": "1",
                "name": "Machine A",
                "type": "CNC",
                "location": "Line 1 - A",
            },
        )
        twin_service.process_event(
            "machine.registered",
            {
                "machine_id": "2",
                "name": "Machine B",
                "type": "Inspection",
                "location": "Line 1 - B",
            },
        )

        print("[3/10] Updating machine health for both machines...")
        twin_service.process_event(
            "machine.health.updated",
            {
                "machine_id": "1",
                "health_score": 0.85,
            },
        )
        twin_service.process_event(
            "machine.health.updated",
            {
                "machine_id": "2",
                "health_score": 0.45,
            },
        )

        print("[4/10] Creating a product...")
        twin_service.process_event(
            "product.created",
            {
                "product_id": "P001",
                "start_node": "1",
            },
        )

        print("[5/10] Moving product from Machine A -> Machine B...")
        twin_service.process_event(
            "product.moved",
            {
                "product_id": "P001",
                "from_node": "1",
                "to_node": "2",
            },
        )

        print("[6/10] Updating machine queues...")
        twin_service.process_event(
            "machine.queue.updated",
            {
                "machine_id": "1",
                "queue_length": 1,
                "products_in_queue": ["P001"],
            },
        )
        twin_service.process_event(
            "machine.queue.updated",
            {
                "machine_id": "2",
                "queue_length": 0,
                "products_in_queue": [],
            },
        )

        print("[7/10] Scheduling maintenance for Machine B...")
        twin_service.process_event(
            "maintenance.scheduled",
            {
                "machine_id": "2",
                "task_id": "MNT-1001",
                "scheduled_date": "2026-03-25T10:00:00Z",
            },
        )

        print("[8/10] Updating production metrics...")
        twin_service.state_manager.update_metrics(
            {
                "throughput": 10,
                "active_machines": 1,
                "completed_products": 5,
                "average_processing_time": 12.5,
            }
        )
        twin_repository.update_production_metrics(
            {
                "throughput": 10,
                "active_machines": 1,
                "completed_products": 5,
                "average_processing_time": 12.5,
            }
        )

        print("[9/10] Triggering digital twin state update event...")
        twin_repository.store_twin_snapshot(twin_service.state_manager.state)
        twin_payload = twin_service.state_manager.publish_twin_state(publisher)
        _ensure(twin_payload.get("event_name") == "twin.state.updated", "Twin event name mismatch")

        print("[10/10] Retrieving full twin state and printing...\n")
        full_state = twin_repository.get_full_twin_state()

        machines = full_state.get("machines", {})
        products = full_state.get("products", {})
        queues = full_state.get("queues", {})
        maintenance = full_state.get("maintenance", {})
        metrics = full_state.get("production_metrics", {})

        print("Machines:")
        machine_a = machines.get("1", {})
        machine_b = machines.get("2", {})
        print(
            f"Machine A - {machine_a.get('status', '').capitalize()} "
            f"- Health {machine_a.get('health')} "
            f"- Queue {machine_a.get('queue_length')}"
        )
        print(
            f"Machine B - {machine_b.get('status', '').capitalize()} "
            f"- Health {machine_b.get('health')} "
            f"- Queue {machine_b.get('queue_length')}"
        )

        print("\nProducts:")
        product = products.get("P001", {})
        print(f"P001 at Machine {product.get('current_location')}")

        print("\nQueues:")
        print(f"Machine A Queue = {queues.get('1', {}).get('queue_length', 0)}")
        print(f"Machine B Queue = {queues.get('2', {}).get('queue_length', 0)}")

        print("\nMaintenance:")
        print(
            "Machine B "
            f"{maintenance.get('2', {}).get('maintenance_status', 'unknown').capitalize()}"
        )

        print("\nProduction Metrics:")
        print(f"Throughput = {metrics.get('throughput')}")
        print(f"Completed Products = {metrics.get('completed_products')}")

        twin_events = [event for event in publisher.events if event.topic == "twin.state.updated"]

        _ensure(machine_a.get("status") == "running", "Machine A status should be running")
        _ensure(machine_b.get("status") == "maintenance", "Machine B status should be maintenance")
        _ensure(float(machine_a.get("health", 0.0)) == 0.85, "Machine A health mismatch")
        _ensure(float(machine_b.get("health", 0.0)) == 0.45, "Machine B health mismatch")
        _ensure(product.get("current_location") == "2", "Product should be at Machine B")
        _ensure(product.get("status") == "in_progress", "Product status should be in_progress")
        _ensure(queues.get("1", {}).get("queue_length") == 1, "Machine A queue mismatch")
        _ensure(queues.get("2", {}).get("queue_length") == 0, "Machine B queue mismatch")
        _ensure(
            maintenance.get("2", {}).get("maintenance_status") == "scheduled",
            "Machine B maintenance status mismatch",
        )
        _ensure(metrics.get("throughput") == 10, "Throughput metric mismatch")
        _ensure(metrics.get("completed_products") == 5, "Completed products metric mismatch")
        _ensure(len(twin_events) >= 1, "Expected twin.state.updated event")

        print("\nDigital Twin State Updated")
        print("twin.state.updated Event Published")
        print("\nDigital Twin Test Completed Successfully.")

    except Exception as exc:
        print_header("TEST FAILED")
        print(f"Error: {exc}")
        raise


if __name__ == "__main__":
    run_digital_twin_test()

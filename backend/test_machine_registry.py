"""Integration-style test for Machine Registry service.

This script validates machine registration, status updates, connections,
database persistence, and event creation within the Smart Factory backend.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from database.db_session import SessionLocal
from database.init_db import init_db
from database.models.machine import Machine
from database.models.machine_connection import MachineConnection
from services.machine_registry.machine_service import MachineRegistryService


@dataclass
class PublishedEvent:
    topic: str
    payload: dict


class TestPublisher:
    """Minimal publisher stub to capture events published by the service."""

    def __init__(self) -> None:
        self.events: list[PublishedEvent] = []

    def publish(self, topic: str, message: dict) -> None:
        self.events.append(PublishedEvent(topic=topic, payload=message))


def print_header(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def run_machine_registry_test() -> None:
    print_header("MACHINE REGISTRY SERVICE INTEGRATION TEST")

    print("[1/8] Initializing database schema and opening session...")
    init_db()
    db = SessionLocal()

    publisher = TestPublisher()
    service = MachineRegistryService(publisher=publisher)

    created_machine_ids: list[int] = []

    try:
        print("[2/8] Registering machines...")
        cnc_machine = service.register_machine(
            name="CNC Machine 1",
            type="CNC",
            location="Line A - Station 1",
        )
        drill_machine = service.register_machine(
            name="Drill Machine 1",
            type="Drill",
            location="Line A - Station 2",
        )
        created_machine_ids.extend([cnc_machine["id"], drill_machine["id"]])

        print(f"Machine Registered: {cnc_machine['name']}")
        print(f"Machine Registered: {drill_machine['name']}")

        print("[3/8] Preparing and changing machine status (stopped -> running)...")
        # Ensure requested transition by setting an initial stopped status first.
        machine_record = db.scalar(select(Machine).where(Machine.id == cnc_machine["id"]))
        if machine_record is None:
            raise RuntimeError("Failed to load CNC machine after registration")

        machine_record.status = "stopped"
        db.commit()

        updated_machine = service.change_machine_status(cnc_machine["id"], "running")
        print(
            "Machine Status Updated: "
            f"{updated_machine['name']} -> {updated_machine['status']}"
        )

        print("[4/8] Connecting machines...")
        connection = service.connect_machines(cnc_machine["id"], drill_machine["id"])
        print(f"Machines Connected: {cnc_machine['name']} -> {drill_machine['name']}")

        print("[5/8] Retrieving all machines from database...")
        all_machines = db.scalars(
            select(Machine).where(Machine.id.in_(created_machine_ids)).order_by(Machine.id.asc())
        ).all()

        print("\nAll Machines:")
        print(f"{'ID':<4}{'Name':<18}{'Status':<12}{'Type':<10}{'Location'}")
        for machine in all_machines:
            print(
                f"{machine.id:<4}{machine.name:<18}{machine.status:<12}"
                f"{machine.type:<10}{machine.location}"
            )

        print("[6/8] Retrieving machine connections...")
        connections = db.scalars(
            select(MachineConnection).where(
                MachineConnection.from_machine_id == cnc_machine["id"]
            )
        ).all()

        print("\nConnections:")
        for item in connections:
            from_machine = db.scalar(
                select(Machine).where(Machine.id == item.from_machine_id)
            )
            to_machine = db.scalar(select(Machine).where(Machine.id == item.to_machine_id))
            from_name = from_machine.name if from_machine else str(item.from_machine_id)
            to_name = to_machine.name if to_machine else str(item.to_machine_id)
            print(f"{from_name} -> {to_name}")

        print("[7/8] Verifying published events...")
        published_topics = [event.topic for event in publisher.events]

        required_topics = {
            "machine.registered": 2,
            "machine.status.changed": 1,
            "machine.connected": 1,
        }

        for topic, expected_count in required_topics.items():
            actual_count = published_topics.count(topic)
            if actual_count < expected_count:
                raise AssertionError(
                    f"Expected at least {expected_count} '{topic}' events, got {actual_count}"
                )

        print("Events Published:")
        for event in publisher.events:
            print(f"- {event.topic} | event_name={event.payload.get('event_name')}")

        print("[8/8] Final verification summary...")
        db_records_exist = len(all_machines) == 2 and len(connections) >= 1
        events_published = all(
            published_topics.count(topic) >= expected
            for topic, expected in required_topics.items()
        )

        print(f"Machines created: {'YES' if len(all_machines) == 2 else 'NO'}")
        print(
            "Status updated: "
            f"{'YES' if updated_machine['status'] == 'running' else 'NO'}"
        )
        print(f"Machines connected: {'YES' if connection.get('id') else 'NO'}")
        print(f"Database records exist: {'YES' if db_records_exist else 'NO'}")
        print(f"Events published: {'YES' if events_published else 'NO'}")

        print("\nMachine Registry Service Test Completed Successfully.")

    except Exception as exc:
        db.rollback()
        print_header("TEST FAILED")
        print(f"Error: {exc}")
        raise
    finally:
        db.close()
        print("\nDatabase session closed.")


if __name__ == "__main__":
    run_machine_registry_test()

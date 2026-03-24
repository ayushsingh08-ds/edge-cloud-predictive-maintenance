"""Integration-style test for Machine Health Service.

Validates anomaly + RUL ingestion, health score calculation,
database persistence, and machine.health.updated publishing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import desc, select

from database.db_session import SessionLocal
from database.init_db import init_db
from database.models.machine import Machine
from database.models.machine_health import MachineHealth
from services.machine_health.machine_health_service import MachineHealthService


@dataclass
class PublishedEvent:
    topic: str
    payload: dict


class TestPublisher:
    """Captures outbound events for deterministic test verification."""

    def __init__(self) -> None:
        self.events: list[PublishedEvent] = []

    def publish(self, topic: str, message: dict) -> None:
        self.events.append(PublishedEvent(topic=topic, payload=message))


def print_header(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def run_machine_health_test() -> None:
    print_header("Machine Health Test Started")

    print("[1/10] Initializing database schema and session...")
    init_db()
    db = SessionLocal()

    publisher = TestPublisher()
    service = MachineHealthService(max_rul_hours=200.0, publisher=publisher)

    try:
        print("[2/10] Creating test machine in database...")
        machine = Machine(
            name=f"CNC Machine 1 - Test {datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            type="CNC",
            location="Line A - Station 1",
            status="running",
        )
        db.add(machine)
        db.commit()
        db.refresh(machine)
        print(f"Machine Created: {machine.name} (id={machine.id})")

        print("[3/10] Simulating anomaly event...")
        anomaly_event = {
            "machine_id": machine.id,
            "anomaly_score": 0.2,
        }
        service.process_anomaly_event(anomaly_event)
        print("Anomaly Event Received: 0.2")

        print("[4/10] Simulating RUL prediction event...")
        rul_event = {
            "machine_id": machine.id,
            "rul_hours": 120,
        }
        result = service.process_rul_event(rul_event)
        print("RUL Event Received: 120")

        if result is None:
            raise RuntimeError("Health calculation did not execute after anomaly + RUL events")

        print("[5/10] Verifying calculated health score...")
        expected_health = 0.4 * (1 - 0.2) + 0.6 * (120 / 200)
        actual_health = float(result["health_score"])
        print(f"Health Calculated: {actual_health:.2f}")

        if abs(actual_health - expected_health) > 1e-6:
            raise AssertionError(
                f"Health score mismatch. expected={expected_health:.6f}, got={actual_health:.6f}"
            )

        status = str(result["status"]).capitalize()
        print(f"Health Status: {status}")

        print("[6/10] Querying machine_health table...")
        latest_health = db.scalar(
            select(MachineHealth)
            .where(MachineHealth.machine_id == machine.id)
            .order_by(desc(MachineHealth.last_updated))
            .limit(1)
        )
        if latest_health is None:
            raise RuntimeError("No machine health record found in database")

        print("Health Stored in Database")
        print("Machine Health Record Retrieved")
        print(
            "Stored Record: "
            f"machine_id={latest_health.machine_id}, "
            f"health_score={latest_health.health_score:.4f}, "
            f"anomaly_score={latest_health.anomaly_score:.4f}, "
            f"rul_hours={latest_health.rul_hours:.2f}, "
            f"last_updated={latest_health.last_updated}"
        )

        print("[7/10] Verifying machine.health.updated event publishing...")
        topics = [event.topic for event in publisher.events]
        health_events = [event for event in publisher.events if event.topic == "machine.health.updated"]

        if not health_events:
            raise AssertionError("Expected machine.health.updated event was not published")

        latest_event = health_events[-1].payload
        if str(latest_event.get("machine_id")) != str(machine.id):
            raise AssertionError("Published event machine_id does not match test machine")

        print("machine.health.updated Event Published")

        print("[8/10] Pipeline integration summary...")
        print("Create Machine -> Anomaly Event -> RUL Event -> Calculate Health -> Store in DB -> Publish Event")

        print("[9/10] Final checks...")
        print(f"Database storage works: {'YES' if latest_health is not None else 'NO'}")
        print(f"Event publishing works: {'YES' if 'machine.health.updated' in topics else 'NO'}")
        print(f"Health calculation works: {'YES' if abs(actual_health - expected_health) <= 1e-6 else 'NO'}")

        print("[10/10] Completed")
        print("Machine Health Service Test Completed Successfully")

    except Exception as exc:
        db.rollback()
        print_header("TEST FAILED")
        print(f"Error: {exc}")
        raise
    finally:
        db.close()
        print("\nDatabase session closed.")


if __name__ == "__main__":
    run_machine_health_test()

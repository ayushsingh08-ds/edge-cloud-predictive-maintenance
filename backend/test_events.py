"""Smoke test for Smart Factory event definitions.

Creates all key event types, validates payload shape, serializes to JSON,
and simulates publishing without RabbitMQ.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from events.alert_events import AlertCreated
from events.machine_events import MachineHealthUpdated
from events.maintenance_events import MaintenanceScheduled
from events.product_events import ProductMoved
from events.routing_events import RoutingDecision
from events.telemetry_events import TelemetryCleaned
from events.twin_events import TwinStateUpdated


def mock_publish(topic: str, payload: dict) -> None:
    """Simulate publish call to a message broker."""
    print(f"[MOCK PUBLISH] topic={topic}")
    print(json.dumps(payload, indent=2))


def validate_event_payload(event, required_fields: list[str]) -> None:
    payload = event.to_dict()

    if "event_name" not in payload:
        raise AssertionError(f"Missing event_name in {event.__class__.__name__}")
    if "timestamp" not in payload:
        raise AssertionError(f"Missing timestamp in {event.__class__.__name__}")

    for field_name in required_fields:
        if field_name not in payload:
            raise AssertionError(
                f"Missing required field '{field_name}' in {event.__class__.__name__}"
            )

    try:
        json_payload = json.dumps(payload)
    except TypeError as exc:
        raise AssertionError(
            f"Payload is not JSON serializable for {event.__class__.__name__}: {exc}"
        ) from exc

    print(f"\nEvent: {payload['event_name']}")
    print("JSON Payload:")
    print(json.dumps(payload, indent=2))

    # Simulated event publishing API requested by user.
    mock_publish(event.event, payload)

    # Keep variable used to make serialization step explicit in test flow.
    if not json_payload:
        raise AssertionError("Unexpected empty JSON payload")


def run_event_tests() -> None:
    now = datetime.now(timezone.utc)

    # Smart Factory event flow:
    # Telemetry -> Machine Health -> Maintenance -> Routing -> Product -> Twin -> Alert
    events_with_schema = [
        (
            TelemetryCleaned(
                machine_id="M-1001",
                temperature=71.8,
                vibration=0.22,
                pressure=30.5,
                rpm=1445.0,
                timestamp=now,
            ),
            ["machine_id", "temperature", "vibration", "pressure", "rpm"],
        ),
        (
            MachineHealthUpdated(
                machine_id="M-1001",
                health_score=90.7,
                anomaly_score=0.09,
                rul_hours=136.0,
                timestamp=now + timedelta(seconds=5),
            ),
            ["machine_id", "health_score", "anomaly_score", "rul_hours"],
        ),
        (
            MaintenanceScheduled(
                machine_id="M-1001",
                task_id="TASK-4501",
                maintenance_type="bearing_inspection",
                priority="high",
                scheduled_date=now + timedelta(days=1),
                completed_date=None,
                timestamp=now + timedelta(seconds=10),
            ),
            ["machine_id", "task_id", "maintenance_type", "priority", "scheduled_date"],
        ),
        (
            RoutingDecision(
                product_id="P-9001",
                from_machine="M-1001",
                to_machine="M-1003",
                route=["M-1001", "BUFFER-A", "M-1003"],
                timestamp=now + timedelta(seconds=15),
            ),
            ["product_id", "from_machine", "to_machine", "route"],
        ),
        (
            ProductMoved(
                product_id="P-9001",
                machine_id="M-1003",
                location="Line-2-Station-3",
                status="in_progress",
                timestamp=now + timedelta(seconds=20),
            ),
            ["product_id", "machine_id", "location", "status"],
        ),
        (
            TwinStateUpdated(
                machine_states={"M-1001": "running", "M-1003": "running"},
                product_positions={"P-9001": "Line-2-Station-3"},
                queues={"Line-2": ["P-9002", "P-9003"]},
                timestamp=now + timedelta(seconds=25),
            ),
            ["machine_states", "product_positions", "queues"],
        ),
        (
            AlertCreated(
                machine_id="M-1001",
                alert_type="maintenance_warning",
                message="RUL below threshold for planned downtime window.",
                severity="warning",
                timestamp=now + timedelta(seconds=30),
            ),
            ["machine_id", "alert_type", "message", "severity"],
        ),
    ]

    print("=" * 72)
    print("SMART FACTORY EVENT DEFINITIONS TEST")
    print("=" * 72)

    for event_obj, required_fields in events_with_schema:
        validate_event_payload(event_obj, required_fields)

    print("\nAll event definitions working correctly.")


if __name__ == "__main__":
    run_event_tests()

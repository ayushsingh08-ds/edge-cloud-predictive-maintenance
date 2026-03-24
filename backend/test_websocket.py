"""Integration-style test for Smart Factory WebSocket event streaming."""

from __future__ import annotations

import asyncio
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from api.app import app
from api.websocket.ws_server import listener, manager


def print_header(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _publish_simulated_event(event_name: str, data: dict) -> None:
    """Simulate event-bus publication by scheduling a websocket broadcast."""
    loop = listener._loop
    if loop is None:
        raise RuntimeError("WebSocket listener loop is not initialized")

    payload = {
        "event": event_name,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    future = asyncio.run_coroutine_threadsafe(manager.broadcast(payload), loop)
    future.result(timeout=5)


def _receive_until_event(websocket, expected_event: str, max_reads: int = 10) -> dict:
    for _ in range(max_reads):
        message = websocket.receive_json()
        event = message.get("event")
        if event == expected_event:
            return message
    raise AssertionError(f"Did not receive expected event: {expected_event}")


def run_websocket_test() -> None:
    print_header("WebSocket Test Started")

    expected_events = [
        (
            "machine.health.updated",
            {
                "machine_id": 1,
                "health_score": 0.82,
                "status": "healthy",
            },
        ),
        (
            "product.moved",
            {
                "product_id": "P001",
                "from_node": 1,
                "to_node": 2,
            },
        ),
        (
            "maintenance.scheduled",
            {
                "machine_id": 2,
                "task_id": "MNT-1001",
                "scheduled_date": "2026-03-24T10:00:00Z",
            },
        ),
        (
            "alert.created",
            {
                "machine_id": 2,
                "severity": "warning",
                "message": "Temperature threshold exceeded",
            },
        ),
        (
            "twin.state.updated",
            {
                "machines": {"1": {"status": "running"}},
                "products": {"P001": {"current_location": 2}},
                "queues": {"1": {"queue_length": 1}},
                "maintenance": {"2": {"maintenance_status": "scheduled"}},
                "production_metrics": {"throughput": 10},
            },
        ),
    ]

    received_messages: list[dict] = []

    with TestClient(app) as client:
        print("WebSocket Server Started")

        with client.websocket_connect("/ws/events") as websocket:
            print("Client Connected")

            # Consume initial welcome event (ws.connected) if present.
            initial = websocket.receive_json()
            if initial.get("event") not in {"ws.connected", "heartbeat"}:
                received_messages.append(initial)

            for event_name, payload in expected_events:
                print(f"Event Published: {event_name}")
                _publish_simulated_event(event_name, payload)

                try:
                    message = _receive_until_event(websocket, event_name)
                except FutureTimeoutError as exc:
                    raise AssertionError(f"Timed out waiting for event {event_name}") from exc

                received_messages.append(message)
                print("Event Received by Client")
                print(message)

            _ensure(len(received_messages) >= len(expected_events), "Not all events were received")

            for event_name, _ in expected_events:
                matched = [msg for msg in received_messages if msg.get("event") == event_name]
                _ensure(matched, f"Missing received event: {event_name}")

            print("Client Disconnected")

    print("WebSocket Test Completed Successfully")


if __name__ == "__main__":
    run_websocket_test()

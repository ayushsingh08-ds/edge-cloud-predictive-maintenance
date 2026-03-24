"""Machine lifecycle and health event definitions."""

from __future__ import annotations

from dataclasses import dataclass

from events.base_event import BaseEvent


@dataclass
class MachineRegistered(BaseEvent):
    event_name = "machine.registered"

    machine_id: str
    name: str
    type: str
    location: str


@dataclass
class MachineStatusChanged(BaseEvent):
    event_name = "machine.status.changed"

    machine_id: str
    previous_status: str
    new_status: str


@dataclass
class MachineStateChanged(BaseEvent):
    """Backward-compatible alias for older state-change consumers."""

    event_name = "machine.state.changed"

    machine_id: str
    previous_state: str
    new_state: str


@dataclass
class MachineConnected(BaseEvent):
    event_name = "machine.connected"

    from_machine_id: str
    to_machine_id: str


@dataclass
class MachineHealthUpdated(BaseEvent):
    event_name = "machine.health.updated"

    machine_id: str
    health_score: float
    anomaly_score: float
    rul_hours: float
    status: str = "healthy"


def publish_machine_health_updated(client, topic: str = "machine.health.updated") -> None:
    """Example helper to publish a MachineHealthUpdated event."""
    event = MachineHealthUpdated(
        machine_id="M-1001",
        health_score=91.2,
        anomaly_score=0.08,
        rul_hours=140.0,
        status="healthy",
    )
    client.publish(topic, event.to_dict())

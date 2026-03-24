"""Alert event definitions."""

from __future__ import annotations

from dataclasses import dataclass

from events.base_event import BaseEvent


@dataclass
class AlertCreated(BaseEvent):
    event_name = "alert.created"

    machine_id: str
    alert_type: str
    message: str
    severity: str

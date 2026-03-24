"""Maintenance workflow event definitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from events.base_event import BaseEvent


@dataclass
class MaintenanceRequired(BaseEvent):
    event_name = "maintenance.required"

    machine_id: str
    task_id: str
    maintenance_type: str
    priority: str
    scheduled_date: datetime | None = None
    completed_date: datetime | None = None


@dataclass
class MaintenanceScheduled(BaseEvent):
    event_name = "maintenance.scheduled"

    machine_id: str
    task_id: str
    maintenance_type: str
    priority: str
    scheduled_date: datetime | None = None
    completed_date: datetime | None = None


@dataclass
class MaintenanceCompleted(BaseEvent):
    event_name = "maintenance.completed"

    machine_id: str
    task_id: str
    maintenance_type: str
    priority: str
    scheduled_date: datetime | None = None
    completed_date: datetime | None = None

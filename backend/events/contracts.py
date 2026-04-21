from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable
from uuid import uuid4


class EventType(str, Enum):
    JOB_ARRIVAL = "JOB_ARRIVAL"
    JOB_START = "JOB_START"
    JOB_FINISH = "JOB_FINISH"
    SENSOR_DATA = "SENSOR_DATA"
    MACHINE_FAILURE = "MACHINE_FAILURE"
    MACHINE_REPAIR = "MACHINE_REPAIR"
    RUL_PREDICTION = "RUL_PREDICTION"
    HEALTH_UPDATE = "HEALTH_UPDATE"
    HIGH_PRESSURE = "HIGH_PRESSURE"
    LOW_PRESSURE = "LOW_PRESSURE"
    ROUTING_REQUEST = "ROUTING_REQUEST"
    ROUTING_DECISION = "ROUTING_DECISION"
    MAINTENANCE_TRIGGER = "MAINTENANCE_TRIGGER"
    MAINTENANCE_STATE = "MAINTENANCE_STATE"
    LAYOUT_CHANGED = "LAYOUT_CHANGED"
    QUEUE_UPDATE = "QUEUE_UPDATE"
    METRIC_UPDATE = "METRIC_UPDATE"
    JOB_TRANSFER = "JOB_TRANSFER"
    JOB_COMPLETED = "JOB_COMPLETED"


@dataclass(slots=True)
class Event:
    event_type: EventType
    timestamp: float
    source: str
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid4()))


EventHandler = Callable[[Event], None]

"""Digital twin synchronization event definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from events.base_event import BaseEvent


@dataclass
class TwinStateUpdated(BaseEvent):
    event_name = "twin.state.updated"

    machine_states: dict[str, Any]
    product_positions: dict[str, Any]
    queues: dict[str, Any]

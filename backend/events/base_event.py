"""Base event types and serialization helpers for RabbitMQ messages."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any, ClassVar


@dataclass(kw_only=True)
class BaseEvent:
    """Base event class with standard metadata and serialization."""

    event_name: ClassVar[str] = "base.event"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def event(self) -> str:
        """Compatibility alias used by publishers expecting `event` key."""
        return self.event_name

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, list):
            return [BaseEvent._serialize_value(item) for item in value]
        if isinstance(value, dict):
            return {key: BaseEvent._serialize_value(item) for key, item in value.items()}
        return value

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["event_name"] = self.event_name
        return {key: self._serialize_value(value) for key, value in payload.items()}

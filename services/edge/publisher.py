from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from config.config import get_settings


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class EventPublisher:
    exchange_name: str = "predictive_maintenance.events"
    routing_key: str = "event.generic"
    queue_name: str | None = None
    default_payload: dict[str, Any] = field(default_factory=dict)

    def publish(
        self,
        payload: dict[str, object],
        *,
        event_type: str | None = None,
        routing_key: str | None = None,
        use_rabbitmq: bool | None = None,
    ) -> bool:
        settings = get_settings()
        if use_rabbitmq is None:
            use_rabbitmq = settings.use_rabbitmq

        envelope: dict[str, Any] = {
            "event_type": event_type or self.routing_key,
            "routing_key": routing_key or self.routing_key,
            "timestamp": _now_iso(),
            "payload": {**self.default_payload, **payload},
        }

        if not use_rabbitmq:
            print(f"[EVENT-MOCK] {self.routing_key}: {json.dumps(envelope, default=str)}")
            return True

        connection = None
        try:
            from database.rabbitmq import get_rabbitmq_connection

            connection = get_rabbitmq_connection()
            channel = connection.channel()
            channel.exchange_declare(exchange=self.exchange_name, exchange_type="topic", durable=True)

            if self.queue_name:
                channel.queue_declare(queue=self.queue_name, durable=True)
                channel.queue_bind(
                    queue=self.queue_name,
                    exchange=self.exchange_name,
                    routing_key=routing_key or self.routing_key,
                )

            channel.basic_publish(
                exchange=self.exchange_name,
                routing_key=routing_key or self.routing_key,
                body=json.dumps(envelope, default=str).encode("utf-8"),
            )
            return True
        except Exception as exc:
            print(f"[EVENT-ERROR] Failed to publish event: {exc}")
            return False
        finally:
            if connection and connection.is_open:
                connection.close()


@dataclass(slots=True)
class AlertPublisher(EventPublisher):
    routing_key: str = "anomaly.alert"
    queue_name: str | None = "anomaly.alert"

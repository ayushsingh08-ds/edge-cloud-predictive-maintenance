from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(slots=True)
class AlertPublisher:
    topic_name: str = "anomaly.alert"

    def publish(self, payload: dict[str, object], *, use_rabbitmq: bool = False) -> bool:
        if not use_rabbitmq:
            print(f"[ALERT-MOCK] {self.topic_name}: {json.dumps(payload)}")
            return True

        connection = None
        try:
            from database.rabbitmq import get_rabbitmq_connection

            connection = get_rabbitmq_connection()
            channel = connection.channel()
            channel.exchange_declare(exchange="", exchange_type="direct", durable=True)
            channel.queue_declare(queue=self.topic_name, durable=True)
            channel.basic_publish(
                exchange="",
                routing_key=self.topic_name,
                body=json.dumps(payload).encode("utf-8"),
            )
            return True
        except Exception as exc:
            print(f"[ALERT-ERROR] Failed to publish alert: {exc}")
            return False
        finally:
            if connection and connection.is_open:
                connection.close()

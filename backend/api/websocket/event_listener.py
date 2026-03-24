"""RabbitMQ event listener that forwards events to websocket clients."""

from __future__ import annotations

import asyncio
import json
import threading
from datetime import datetime, timezone

import pika

from config.env import RABBITMQ_HOST, RABBITMQ_PASS, RABBITMQ_PORT, RABBITMQ_USER
from api.websocket.connection_manager import ConnectionManager


class RabbitMQEventListener:
    """Subscribe to RabbitMQ topics and broadcast events to websocket clients."""

    def __init__(
        self,
        manager: ConnectionManager,
        topics: list[str] | None = None,
    ) -> None:
        self.manager = manager
        self.topics = topics or [
            "machine.health.updated",
            "machine.status.changed",
            "product.created",
            "product.moved",
            "product.completed",
            "maintenance.scheduled",
            "maintenance.completed",
            "alert.created",
            "twin.state.updated",
            "production.metrics.updated",
        ]

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._connection = None
        self._channel = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        if self.is_running:
            return

        self._loop = loop
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._consume_events, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        try:
            if self._channel is not None and self._channel.is_open:
                self._channel.stop_consuming()
        except Exception:
            pass

        try:
            if self._connection is not None and self._connection.is_open:
                self._connection.close()
        except Exception:
            pass

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _consume_events(self) -> None:
        try:
            host = RABBITMQ_HOST or "localhost"
            user = RABBITMQ_USER or "admin"
            password = RABBITMQ_PASS or "admin123"
            port = int(RABBITMQ_PORT) if RABBITMQ_PORT else 5672

            credentials = pika.PlainCredentials(user, password)
            parameters = pika.ConnectionParameters(host=host, port=port, credentials=credentials)

            self._connection = pika.BlockingConnection(parameters)
            self._channel = self._connection.channel()
            self._channel.exchange_declare(
                exchange="sensor_exchange",
                exchange_type="topic",
                durable=True,
            )

            result = self._channel.queue_declare(queue="", exclusive=True)
            queue_name = result.method.queue

            for topic in self.topics:
                self._channel.queue_bind(
                    exchange="sensor_exchange",
                    queue=queue_name,
                    routing_key=topic,
                )

            def callback(ch, method, properties, body):
                if self._stop_event.is_set():
                    return

                try:
                    payload = json.loads(body)
                except Exception:
                    payload = {"raw": body.decode("utf-8", errors="replace")}

                event_name = getattr(method, "routing_key", "") or payload.get("event_name") or payload.get("event")
                outbound = {
                    "event": event_name,
                    "data": payload,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                if self._loop is not None and not self._loop.is_closed():
                    future = asyncio.run_coroutine_threadsafe(
                        self.manager.broadcast(outbound),
                        self._loop,
                    )
                    try:
                        future.result(timeout=5)
                    except Exception:
                        pass

            self._channel.basic_consume(
                queue=queue_name,
                on_message_callback=callback,
                auto_ack=True,
            )
            self._channel.start_consuming()

        except Exception as exc:
            print(f"[ERROR] WebSocket event listener failed: {exc}")
        finally:
            try:
                if self._connection is not None and self._connection.is_open:
                    self._connection.close()
            except Exception:
                pass

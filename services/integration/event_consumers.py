from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from database.rabbitmq import get_rabbitmq_connection


logger = logging.getLogger(__name__)


EventHandler = Callable[[dict[str, Any]], None]


@dataclass
class _ConsumerConfig:
    name: str
    queue_name: str
    binding_keys: list[str]
    handler: EventHandler
    prefetch_count: int = 20


class _ConsumerWorker:
    def __init__(self, config: _ConsumerConfig) -> None:
        self.config = config
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name=f"consumer-{config.name}", daemon=True)
        self._connection: Any = None
        self._channel: Any = None
        self._processed_count = 0
        self._error_count = 0

    @property
    def processed_count(self) -> int:
        return self._processed_count

    @property
    def error_count(self) -> int:
        return self._error_count

    @property
    def is_running(self) -> bool:
        return self._thread.is_alive()

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._close()
        self._thread.join(timeout=3)

    def _close(self) -> None:
        try:
            if self._channel and self._channel.is_open:
                self._channel.close()
        except Exception:
            pass
        try:
            if self._connection and self._connection.is_open:
                self._connection.close()
        except Exception:
            pass
        self._channel = None
        self._connection = None

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._connection = get_rabbitmq_connection()
                self._channel = self._connection.channel()
                self._channel.exchange_declare(
                    exchange="predictive_maintenance.events",
                    exchange_type="topic",
                    durable=True,
                )
                self._channel.queue_declare(queue=self.config.queue_name, durable=True)
                self._channel.basic_qos(prefetch_count=self.config.prefetch_count)
                for routing_key in self.config.binding_keys:
                    self._channel.queue_bind(
                        exchange="predictive_maintenance.events",
                        queue=self.config.queue_name,
                        routing_key=routing_key,
                    )

                for method_frame, _properties, body in self._channel.consume(
                    queue=self.config.queue_name,
                    inactivity_timeout=1,
                    auto_ack=False,
                ):
                    if self._stop.is_set():
                        break
                    if method_frame is None:
                        continue

                    delivery_tag = method_frame.delivery_tag
                    try:
                        payload = json.loads(body.decode("utf-8"))
                        self.config.handler(payload)
                        self._channel.basic_ack(delivery_tag=delivery_tag)
                        self._processed_count += 1
                    except Exception as exc:
                        self._error_count += 1
                        logger.exception("%s consumer failed to process message: %s", self.config.name, exc)
                        self._channel.basic_nack(delivery_tag=delivery_tag, requeue=False)

                if self._channel and self._channel.is_open:
                    self._channel.cancel()
            except Exception as exc:
                self._error_count += 1
                logger.warning("%s consumer reconnecting after error: %s", self.config.name, exc)
                time.sleep(2)
            finally:
                self._close()


class RabbitMQEventConsumers:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._workers: dict[str, _ConsumerWorker] = {}
        self._job_projection: dict[int, dict[str, Any]] = {}
        self._machine_projection: dict[int, dict[str, Any]] = {}

    def start(self) -> None:
        with self._lock:
            if self._workers:
                return

            job_worker = _ConsumerWorker(
                _ConsumerConfig(
                    name="job_status",
                    queue_name="predictive_maintenance.job_status",
                    binding_keys=[
                        "simulation.operation_routed",
                        "simulation.operation_started",
                        "simulation.operation_interrupted",
                        "simulation.operation_completed",
                        "simulation.job_rerouted",
                    ],
                    handler=self._handle_job_event,
                )
            )
            machine_worker = _ConsumerWorker(
                _ConsumerConfig(
                    name="machine_state",
                    queue_name="predictive_maintenance.machine_state",
                    binding_keys=[
                        "simulation.machine_failed",
                        "simulation.machine_repaired",
                        "simulation.operation_started",
                        "simulation.operation_completed",
                    ],
                    handler=self._handle_machine_event,
                )
            )

            self._workers = {
                "job_status": job_worker,
                "machine_state": machine_worker,
            }
            for worker in self._workers.values():
                worker.start()

            logger.info("RabbitMQ event consumers started")

    def stop(self) -> None:
        with self._lock:
            workers = self._workers
            self._workers = {}

        for worker in workers.values():
            worker.stop()

        if workers:
            logger.info("RabbitMQ event consumers stopped")

    def status(self) -> dict[str, Any]:
        with self._lock:
            worker_status: dict[str, dict[str, int | bool]] = {
                name: {
                    "running": worker.is_running,
                    "processed_count": worker.processed_count,
                    "error_count": worker.error_count,
                }
                for name, worker in self._workers.items()
            }
        return {
            "workers": worker_status,
            "job_projection_size": len(self._job_projection),
            "machine_projection_size": len(self._machine_projection),
        }

    def _handle_job_event(self, message: dict[str, Any]) -> None:
        payload = message.get("payload", {})
        job_id = payload.get("job_id")
        if not isinstance(job_id, int):
            return

        self._job_projection[job_id] = {
            "event_type": message.get("event_type"),
            "routing_key": message.get("routing_key"),
            "timestamp": message.get("timestamp"),
            "simulation_id": payload.get("simulation_id"),
            "operation": payload.get("operation"),
            "machine_id": payload.get("machine_id"),
        }

    def _handle_machine_event(self, message: dict[str, Any]) -> None:
        payload = message.get("payload", {})
        machine_id = payload.get("machine_id")
        if not isinstance(machine_id, int):
            return

        self._machine_projection[machine_id] = {
            "event_type": message.get("event_type"),
            "routing_key": message.get("routing_key"),
            "timestamp": message.get("timestamp"),
            "simulation_id": payload.get("simulation_id"),
            "job_id": payload.get("job_id"),
            "queue_size": payload.get("queue_size"),
        }

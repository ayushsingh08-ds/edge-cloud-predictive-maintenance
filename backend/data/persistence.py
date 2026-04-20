from __future__ import annotations

import logging
import queue
from datetime import datetime, timedelta
from typing import Any, List, Optional
from queue import Queue, Empty
from threading import Thread

from events import Event, EventBus, EventType
from .db import db
from .models import (
    Telemetry, MachineHealth, RoutingLog, MachineFailure,
    MaintenanceLog, QueueHistory, ThroughputHistory
)

logger = logging.getLogger(__name__)


class PersistenceService:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._write_queue: Queue[Event] = Queue()
        self._worker_thread = Thread(target=self._persistence_worker, daemon=True)
        self._is_running = False
        self._bind_events()

    def _bind_events(self) -> None:
        # Map EventTypes to dedicated handlers
        subscriptions = {
            EventType.SENSOR_DATA: self.queue_event,
            EventType.HEALTH_UPDATE: self.queue_event,
            EventType.ROUTING_DECISION: self.queue_event,
            EventType.MACHINE_FAILURE: self.queue_event,
            EventType.MAINTENANCE_TRIGGER: self.queue_event,
            # METRIC_UPDATE and QUEUE_UPDATE are not in the current EventType enum
        }
        for event_type, handler in subscriptions.items():
            self.event_bus.subscribe(event_type, handler)

    def start(self) -> None:
        if not self._is_running:
            self._is_running = True
            self._worker_thread.start()
            logger.info("Persistence Service started.")

    def queue_event(self, event: Event) -> None:
        """Add event to background write queue."""
        self._write_queue.put(event)

    def _persistence_worker(self) -> None:
        """Background thread to write events to database in batches."""
        logger.info("Persistence worker thread started.")
        while self._is_running:
            try:
                # Wait for an event with a timeout to allow periodic shutdown checks
                event = self._write_queue.get(timeout=2.0)
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Error retrieving from persistence queue: {e}")
                continue

            # Implement basic retry for DB operations
            max_retries = 3
            backoff = 1.0
            
            for attempt in range(max_retries):
                try:
                    self._save_event(event)
                    self._write_queue.task_done()
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Persistence attempt {attempt + 1} failed: {e}. Retrying in {backoff}s...")
                        import time
                        time.sleep(backoff)
                        backoff *= 2
                    else:
                        logger.error(f"Critical: Failed to persist event {event.event_type} after {max_retries} attempts. Data may be lost. Error: {e}")
                        self._write_queue.task_done() # Mark as done to prevent queue blockage, even if failed

    def _save_event(self, event: Event) -> None:
        with db.session() as session:
            ts = datetime.fromtimestamp(event.timestamp) if isinstance(event.timestamp, (int, float)) else datetime.utcnow()
            
            if event.event_type == EventType.SENSOR_DATA:
                metrics = event.payload.get("metrics", event.payload)
                session.add(Telemetry(
                    timestamp=ts,
                    machine_id=str(event.payload.get("machine_id", event.source)),
                    metrics=metrics,
                    temperature=metrics.get("temperature"),
                    vibration=metrics.get("vibration"),
                    load=metrics.get("load")
                ))
            
            elif event.event_type == EventType.HEALTH_UPDATE:
                session.add(MachineHealth(
                    timestamp=ts,
                    machine_id=str(event.payload.get("machine_id", "")),
                    health_score=float(event.payload.get("health", 0.0)),
                    risk_score=float(event.payload.get("risk_score", 0.0)),
                    remaining_useful_life=float(event.payload.get("remaining_useful_life", 0.0))
                ))
            
            elif event.event_type == EventType.ROUTING_DECISION:
                session.add(RoutingLog(
                    timestamp=ts,
                    request_id=str(event.payload.get("request_id", "")),
                    divider_id=str(event.payload.get("divider_id", "")),
                    to_node=str(event.payload.get("to", "")),
                    policy=str(event.payload.get("policy", ""))
                ))
            
            elif event.event_type == EventType.MACHINE_FAILURE:
                session.add(MachineFailure(
                    timestamp=ts,
                    machine_id=str(event.payload.get("machine_id", event.source)),
                    failure_type="CRITICAL_FAILURE",
                    details=event.payload
                ))
            
            elif event.event_type == EventType.MAINTENANCE_TRIGGER:
                session.add(MaintenanceLog(
                    timestamp=ts,
                    machine_id=str(event.payload.get("machine_id", "")),
                    action="SCHEDULED_MAINTENANCE",
                    reason=str(event.payload.get("reason", ""))
                ))
            
            elif event.event_type == EventType.QUEUE_UPDATE:
                session.add(QueueHistory(
                    timestamp=ts,
                    node_id=str(event.payload.get("node_id", "")),
                    queue_length=int(event.payload.get("length", 0))
                ))
            
            elif event.event_type == EventType.METRIC_UPDATE:
                if "throughput_hr" in event.payload:
                    session.add(ThroughputHistory(
                        timestamp=ts,
                        machine_id=str(event.payload.get("machine_id", "system")),
                        throughput_hr=float(event.payload.get("throughput_hr", 0.0)),
                        completed_jobs=int(event.payload.get("completed_jobs", 0))
                    ))
            
            session.commit()

    def get_history(self, hours: int = 1) -> dict[str, Any]:
        """Fetch history for playback."""
        since = datetime.utcnow() - timedelta(hours=hours)
        history = {}
        with db.session() as session:
            # We return a structured dictionary or list of events
            telemetry = session.query(Telemetry).filter(Telemetry.timestamp >= since).limit(1000).all()
            failures = session.query(MachineFailure).filter(MachineFailure.timestamp >= since).all()
            health = session.query(MachineHealth).filter(MachineHealth.timestamp >= since).all()
            
            # Simplified summary for brevity
            history["telemetry"] = [{"ts": t.timestamp.isoformat(), "mid": t.machine_id, "metrics": t.metrics} for t in telemetry]
            history["failures"] = [{"ts": f.timestamp.isoformat(), "mid": f.machine_id, "type": f.failure_type} for f in failures]
            history["health"] = [{"ts": h.timestamp.isoformat(), "mid": h.machine_id, "score": h.health_score} for h in health]
            
        return history

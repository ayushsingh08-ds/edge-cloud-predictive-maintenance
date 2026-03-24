"""Maintenance Scheduler Service.

Converts machine health predictions into maintenance tasks, tracks task
lifecycle, and publishes maintenance workflow events.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from events import MaintenanceCompleted, MaintenanceRequired, MaintenanceScheduled
from messaging.rabbitmq_client import RabbitMQClient
from services.machine_registry import machine_repository
from services.maintenance_scheduler import maintenance_repository


class MaintenanceSchedulerService:
    """Main business logic for predictive and preventive maintenance scheduling."""

    def __init__(
        self,
        preventive_interval_days: int = 30,
        publisher: RabbitMQClient | None = None,
    ) -> None:
        self.preventive_interval_days = preventive_interval_days
        self.client = publisher or RabbitMQClient()

    @staticmethod
    def _safe_machine_id(event: dict) -> int:
        raw = event.get("machine_id")
        if raw is None:
            raise ValueError("machine_id missing in machine health event")

        if isinstance(raw, int):
            return raw

        text = str(raw)
        digits = "".join(ch for ch in text if ch.isdigit())
        return int(digits) if digits else int(text)

    def process_machine_health_event(self, event: dict) -> dict | None:
        machine_id = self._safe_machine_id(event)
        health_score = float(event.get("health_score", 1.0))
        rul_hours = float(event.get("rul_hours", 10_000.0))

        required_info = self.check_maintenance_required(
            machine_id=machine_id,
            health_score=health_score,
            rul_hours=rul_hours,
        )
        if required_info is None:
            return None

        existing = maintenance_repository.get_open_maintenance_task(machine_id)
        if existing is not None:
            return {
                **existing,
                "downtime_hours": maintenance_repository.get_machine_downtime_hours(machine_id),
            }

        task = self.schedule_maintenance(
            machine_id=machine_id,
            priority=required_info["priority"],
            task_type=required_info["task_type"],
        )

        self.publish_maintenance_required_event(
            machine_id=machine_id,
            task_id=task["id"],
            task_type=task["task_type"],
            priority=task["priority"],
            scheduled_date=task["scheduled_date"],
        )
        self.publish_maintenance_scheduled_event(
            machine_id=machine_id,
            task_id=task["id"],
            task_type=task["task_type"],
            priority=task["priority"],
            scheduled_date=task["scheduled_date"],
        )

        machine_repository.update_machine_status(machine_id, "maintenance")
        return {
            **task,
            "downtime_hours": maintenance_repository.get_machine_downtime_hours(machine_id),
        }

    def check_maintenance_required(
        self,
        machine_id: int,
        health_score: float,
        rul_hours: float,
    ) -> dict | None:
        machine = machine_repository.get_machine(machine_id)
        if machine is None:
            raise ValueError(f"Machine {machine_id} not found")

        if health_score < 0.5:
            return {
                "priority": "high",
                "task_type": "predictive_maintenance",
                "reason": "critical_health",
            }

        if rul_hours < 48.0:
            return {
                "priority": "high",
                "task_type": "predictive_maintenance",
                "reason": "low_rul",
            }

        history = maintenance_repository.get_maintenance_history(machine_id)
        latest_completed = next(
            (item for item in history if item.get("status") == "completed"),
            None,
        )
        if latest_completed is None:
            return {
                "priority": "medium",
                "task_type": "preventive_maintenance",
                "reason": "no_history",
            }

        completed_date = latest_completed.get("completed_date")
        if completed_date is None:
            return None

        if isinstance(completed_date, str):
            completed_date = datetime.fromisoformat(completed_date)

        age = datetime.now(timezone.utc) - completed_date
        if age.days >= self.preventive_interval_days:
            return {
                "priority": "medium",
                "task_type": "preventive_maintenance",
                "reason": "interval_reached",
            }

        return None

    def schedule_maintenance(
        self,
        machine_id: int,
        priority: str,
        task_type: str = "predictive_maintenance",
    ) -> dict:
        now = datetime.now(timezone.utc)
        priority_lc = priority.lower()

        if priority_lc == "high":
            scheduled_date = now + timedelta(hours=12)
        elif priority_lc == "medium":
            scheduled_date = now + timedelta(hours=48)
        else:
            scheduled_date = now + timedelta(days=7)

        return maintenance_repository.create_maintenance_task(
            machine_id=machine_id,
            task_type=task_type,
            priority=priority_lc,
            scheduled_date=scheduled_date,
        )

    def complete_maintenance(self, task_id: int) -> dict:
        task = maintenance_repository.complete_maintenance_task(task_id)
        if task is None:
            raise ValueError(f"Maintenance task {task_id} not found")

        self.publish_maintenance_completed_event(
            machine_id=task["machine_id"],
            task_id=task["id"],
            task_type=task["task_type"],
            priority=task["priority"],
            scheduled_date=task["scheduled_date"],
            completed_date=task["completed_date"],
        )

        machine_repository.update_machine_status(task["machine_id"], "running")
        return {
            **task,
            "downtime_hours": maintenance_repository.get_machine_downtime_hours(task["machine_id"]),
        }

    def publish_maintenance_required_event(
        self,
        machine_id: int,
        task_id: int,
        task_type: str,
        priority: str,
        scheduled_date: datetime,
    ) -> None:
        event = MaintenanceRequired(
            machine_id=str(machine_id),
            task_id=str(task_id),
            maintenance_type=task_type,
            priority=priority,
            scheduled_date=scheduled_date,
            completed_date=None,
        )
        self.client.publish("maintenance.required", event.to_dict())

    def publish_maintenance_scheduled_event(
        self,
        machine_id: int,
        task_id: int,
        task_type: str,
        priority: str,
        scheduled_date: datetime,
    ) -> None:
        event = MaintenanceScheduled(
            machine_id=str(machine_id),
            task_id=str(task_id),
            maintenance_type=task_type,
            priority=priority,
            scheduled_date=scheduled_date,
            completed_date=None,
        )
        self.client.publish("maintenance.scheduled", event.to_dict())

    def publish_maintenance_completed_event(
        self,
        machine_id: int,
        task_id: int,
        task_type: str,
        priority: str,
        scheduled_date: datetime | None,
        completed_date: datetime | None,
    ) -> None:
        event = MaintenanceCompleted(
            machine_id=str(machine_id),
            task_id=str(task_id),
            maintenance_type=task_type,
            priority=priority,
            scheduled_date=scheduled_date,
            completed_date=completed_date,
        )
        self.client.publish("maintenance.completed", event.to_dict())

    def start(self) -> None:
        """Subscribe to machine health updates and schedule tasks as needed."""
        print("[+] Maintenance Scheduler listening for machine.health.updated events...")

        result = self.client.channel.queue_declare(queue="", exclusive=True)
        queue_name = result.method.queue

        self.client.channel.queue_bind(
            exchange="sensor_exchange",
            queue=queue_name,
            routing_key="machine.health.updated",
        )

        def callback(ch, method, properties, body):
            try:
                payload = json.loads(body)
                task = self.process_machine_health_event(payload)
                if task:
                    print(
                        "[MAINTENANCE] "
                        f"task_id={task['id']} machine={task['machine_id']} "
                        f"priority={task['priority']} status={task['status']}"
                    )
            except Exception as exc:
                print(f"[ERROR] Failed to process maintenance event: {exc}")

        self.client.channel.basic_consume(
            queue=queue_name,
            on_message_callback=callback,
            auto_ack=True,
        )
        self.client.channel.start_consuming()

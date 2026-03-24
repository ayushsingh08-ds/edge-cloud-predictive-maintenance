"""Repository layer for maintenance task persistence and history."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import desc, select

from database.db_session import SessionLocal
from database.models.maintenance_task import MaintenanceTask


def _task_to_dict(task: MaintenanceTask) -> dict:
    return {
        "id": task.id,
        "machine_id": task.machine_id,
        "task_type": task.task_type,
        "priority": task.priority,
        "status": task.status,
        "scheduled_date": task.scheduled_date,
        "completed_date": task.completed_date,
    }


def create_maintenance_task(
    machine_id: int,
    task_type: str,
    priority: str,
    scheduled_date: datetime,
) -> dict:
    db = SessionLocal()
    try:
        task = MaintenanceTask(
            machine_id=machine_id,
            task_type=task_type,
            priority=priority,
            status="scheduled",
            scheduled_date=scheduled_date,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return _task_to_dict(task)
    finally:
        db.close()


def get_maintenance_task(task_id: int) -> dict | None:
    db = SessionLocal()
    try:
        task = db.scalar(select(MaintenanceTask).where(MaintenanceTask.id == task_id))
        if task is None:
            return None
        return _task_to_dict(task)
    finally:
        db.close()


def get_machine_maintenance_tasks(machine_id: int) -> list[dict]:
    db = SessionLocal()
    try:
        tasks = db.scalars(
            select(MaintenanceTask)
            .where(MaintenanceTask.machine_id == machine_id)
            .order_by(MaintenanceTask.scheduled_date.desc())
        ).all()
        return [_task_to_dict(task) for task in tasks]
    finally:
        db.close()


def update_task_status(task_id: int, status: str) -> dict | None:
    db = SessionLocal()
    try:
        task = db.scalar(select(MaintenanceTask).where(MaintenanceTask.id == task_id))
        if task is None:
            return None

        task.status = status
        db.commit()
        db.refresh(task)
        return _task_to_dict(task)
    finally:
        db.close()


def complete_maintenance_task(task_id: int) -> dict | None:
    db = SessionLocal()
    try:
        task = db.scalar(select(MaintenanceTask).where(MaintenanceTask.id == task_id))
        if task is None:
            return None

        task.status = "completed"
        task.completed_date = datetime.now(timezone.utc)
        db.commit()
        db.refresh(task)
        return _task_to_dict(task)
    finally:
        db.close()


def get_all_maintenance_tasks() -> list[dict]:
    db = SessionLocal()
    try:
        tasks = db.scalars(
            select(MaintenanceTask).order_by(MaintenanceTask.scheduled_date.desc())
        ).all()
        return [_task_to_dict(task) for task in tasks]
    finally:
        db.close()


def get_maintenance_history(machine_id: int) -> list[dict]:
    db = SessionLocal()
    try:
        tasks = db.scalars(
            select(MaintenanceTask)
            .where(MaintenanceTask.machine_id == machine_id)
            .order_by(desc(MaintenanceTask.completed_date), desc(MaintenanceTask.scheduled_date))
        ).all()
        return [_task_to_dict(task) for task in tasks]
    finally:
        db.close()


def get_open_maintenance_task(machine_id: int) -> dict | None:
    db = SessionLocal()
    try:
        task = db.scalar(
            select(MaintenanceTask)
            .where(MaintenanceTask.machine_id == machine_id)
            .where(MaintenanceTask.status.in_(["scheduled", "in_progress"]))
            .order_by(MaintenanceTask.scheduled_date.asc())
            .limit(1)
        )
        if task is None:
            return None
        return _task_to_dict(task)
    finally:
        db.close()


def get_machine_downtime_hours(machine_id: int) -> float:
    """Return cumulative downtime in hours for completed maintenance tasks."""
    history = get_maintenance_history(machine_id)
    total_hours = 0.0

    for task in history:
        scheduled_date = task.get("scheduled_date")
        completed_date = task.get("completed_date")
        status = task.get("status")

        if status != "completed" or scheduled_date is None or completed_date is None:
            continue

        if isinstance(scheduled_date, str):
            scheduled_date = datetime.fromisoformat(scheduled_date)
        if isinstance(completed_date, str):
            completed_date = datetime.fromisoformat(completed_date)

        hours = (completed_date - scheduled_date).total_seconds() / 3600.0
        if hours > 0:
            total_hours += hours

    return round(total_hours, 2)

"""Maintenance endpoints for scheduling and lifecycle updates."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas.dependencies import get_db
from database.models.maintenance_task import MaintenanceTask


router = APIRouter(prefix="/maintenance", tags=["maintenance"])


@router.get("")
def list_maintenance_tasks(db: Session = Depends(get_db)) -> list[dict]:
    tasks = db.scalars(select(MaintenanceTask).order_by(MaintenanceTask.id.desc())).all()
    return [
        {
            "id": task.id,
            "machine_id": task.machine_id,
            "task_type": task.task_type,
            "priority": task.priority,
            "status": task.status,
            "scheduled_date": task.scheduled_date,
            "completed_date": task.completed_date,
        }
        for task in tasks
    ]


@router.post("/schedule")
def schedule_maintenance(payload: dict, db: Session = Depends(get_db)) -> dict:
    required = ["machine_id", "task_type", "priority"]
    missing = [field for field in required if field not in payload]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required fields: {missing}")

    scheduled_raw = payload.get("scheduled_date")
    scheduled_date = None
    if scheduled_raw:
        try:
            scheduled_date = datetime.fromisoformat(str(scheduled_raw).replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid scheduled_date format") from exc

    task = MaintenanceTask(
        machine_id=int(payload["machine_id"]),
        task_type=str(payload["task_type"]),
        priority=str(payload["priority"]),
        status="scheduled",
        scheduled_date=scheduled_date,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    return {
        "id": task.id,
        "machine_id": task.machine_id,
        "task_type": task.task_type,
        "priority": task.priority,
        "status": task.status,
        "scheduled_date": task.scheduled_date,
        "completed_date": task.completed_date,
    }


@router.post("/{task_id}/complete")
def complete_maintenance(task_id: int, db: Session = Depends(get_db)) -> dict:
    task = db.scalar(select(MaintenanceTask).where(MaintenanceTask.id == task_id))
    if task is None:
        raise HTTPException(status_code=404, detail=f"Maintenance task {task_id} not found")

    task.status = "completed"
    task.completed_date = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)

    return {
        "id": task.id,
        "machine_id": task.machine_id,
        "task_type": task.task_type,
        "priority": task.priority,
        "status": task.status,
        "scheduled_date": task.scheduled_date,
        "completed_date": task.completed_date,
    }

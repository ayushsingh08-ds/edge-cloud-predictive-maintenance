"""Repository helpers for common predictive maintenance database operations."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, joinedload

from database.models.alert import Alert
from database.models.machine import Machine
from database.models.machine_health import MachineHealth
from database.models.maintenance_task import MaintenanceTask
from database.models.rul_prediction import RULPrediction
from database.models.telemetry import Telemetry


def insert_telemetry(
    db: Session,
    machine_id: int,
    temperature: float,
    vibration: float,
    pressure: float,
    rpm: float,
    timestamp: datetime | None = None,
) -> Telemetry:
    record = Telemetry(
        machine_id=machine_id,
        temperature=temperature,
        vibration=vibration,
        pressure=pressure,
        rpm=rpm,
        timestamp=timestamp or datetime.utcnow(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def insert_rul_prediction(
    db: Session,
    machine_id: int,
    rul_hours: float,
    confidence: float,
    timestamp: datetime | None = None,
) -> RULPrediction:
    prediction = RULPrediction(
        machine_id=machine_id,
        rul_hours=rul_hours,
        confidence=confidence,
        timestamp=timestamp or datetime.utcnow(),
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    return prediction


def update_machine_health(
    db: Session,
    machine_id: int,
    health_score: float,
    anomaly_score: float,
    rul_hours: float | None,
    last_updated: datetime | None = None,
) -> MachineHealth:
    existing = db.scalar(
        select(MachineHealth)
        .where(MachineHealth.machine_id == machine_id)
        .order_by(desc(MachineHealth.last_updated))
        .limit(1)
    )

    if existing is None:
        existing = MachineHealth(machine_id=machine_id)
        db.add(existing)

    existing.health_score = health_score
    existing.anomaly_score = anomaly_score
    existing.rul_hours = rul_hours
    existing.last_updated = last_updated or datetime.utcnow()

    db.commit()
    db.refresh(existing)
    return existing


def create_maintenance_task(
    db: Session,
    machine_id: int,
    task_type: str,
    priority: str,
    status: str,
    scheduled_date: datetime | None = None,
    completed_date: datetime | None = None,
) -> MaintenanceTask:
    task = MaintenanceTask(
        machine_id=machine_id,
        task_type=task_type,
        priority=priority,
        status=status,
        scheduled_date=scheduled_date,
        completed_date=completed_date,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def create_alert(
    db: Session,
    machine_id: int,
    alert_type: str,
    message: str,
    severity: str,
    timestamp: datetime | None = None,
) -> Alert:
    alert = Alert(
        machine_id=machine_id,
        alert_type=alert_type,
        message=message,
        severity=severity,
        timestamp=timestamp or datetime.utcnow(),
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def get_machine_with_data(db: Session, machine_id: int) -> Machine | None:
    return db.scalar(
        select(Machine)
        .where(Machine.id == machine_id)
        .options(
            joinedload(Machine.health_records),
            joinedload(Machine.telemetry_records),
            joinedload(Machine.rul_predictions),
            joinedload(Machine.maintenance_tasks),
            joinedload(Machine.alerts),
        )
    )


def list_machine_telemetry(db: Session, machine_id: int, limit: int = 100) -> list[Telemetry]:
    rows = db.scalars(
        select(Telemetry)
        .where(Telemetry.machine_id == machine_id)
        .order_by(desc(Telemetry.timestamp))
        .limit(limit)
    )
    return list(rows)

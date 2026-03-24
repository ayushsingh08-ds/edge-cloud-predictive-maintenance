"""Repository layer for machine health persistence and lookups."""

from __future__ import annotations

from sqlalchemy import desc, select

from database.db_session import SessionLocal
from database.models.machine_health import MachineHealth
from database.models.maintenance_task import MaintenanceTask
from database.models.telemetry import Telemetry


def _health_to_dict(health: MachineHealth) -> dict:
    return {
        "id": health.id,
        "machine_id": health.machine_id,
        "health_score": health.health_score,
        "anomaly_score": health.anomaly_score,
        "rul_hours": health.rul_hours,
        "last_updated": health.last_updated,
    }


def insert_machine_health(
    machine_id: int,
    health_score: float,
    anomaly_score: float,
    rul_hours: float | None,
) -> dict:
    db = SessionLocal()
    try:
        record = MachineHealth(
            machine_id=machine_id,
            health_score=health_score,
            anomaly_score=anomaly_score,
            rul_hours=rul_hours,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return _health_to_dict(record)
    finally:
        db.close()


def get_latest_health(machine_id: int) -> dict | None:
    db = SessionLocal()
    try:
        record = db.scalar(
            select(MachineHealth)
            .where(MachineHealth.machine_id == machine_id)
            .order_by(desc(MachineHealth.last_updated))
            .limit(1)
        )
        if record is None:
            return None
        return _health_to_dict(record)
    finally:
        db.close()


def get_all_machine_health() -> list[dict]:
    db = SessionLocal()
    try:
        records = db.scalars(
            select(MachineHealth).order_by(MachineHealth.last_updated.desc())
        ).all()
        return [_health_to_dict(item) for item in records]
    finally:
        db.close()


def update_machine_health(machine_id: int, health_score: float) -> dict | None:
    db = SessionLocal()
    try:
        record = db.scalar(
            select(MachineHealth)
            .where(MachineHealth.machine_id == machine_id)
            .order_by(desc(MachineHealth.last_updated))
            .limit(1)
        )
        if record is None:
            return None

        record.health_score = health_score
        db.commit()
        db.refresh(record)
        return _health_to_dict(record)
    finally:
        db.close()


def get_latest_telemetry(machine_id: int) -> dict | None:
    db = SessionLocal()
    try:
        record = db.scalar(
            select(Telemetry)
            .where(Telemetry.machine_id == machine_id)
            .order_by(desc(Telemetry.timestamp))
            .limit(1)
        )
        if record is None:
            return None

        return {
            "machine_id": record.machine_id,
            "temperature": record.temperature,
            "vibration": record.vibration,
            "pressure": record.pressure,
            "rpm": record.rpm,
            "timestamp": record.timestamp,
        }
    finally:
        db.close()


def get_latest_maintenance_status(machine_id: int) -> str | None:
    db = SessionLocal()
    try:
        record = db.scalar(
            select(MaintenanceTask)
            .where(MaintenanceTask.machine_id == machine_id)
            .order_by(desc(MaintenanceTask.scheduled_date))
            .limit(1)
        )
        if record is None:
            return None
        return record.status
    finally:
        db.close()

"""Machine-related API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from api.schemas.dependencies import get_db
from database.models.machine import Machine
from database.models.machine_health import MachineHealth
from database.models.telemetry import Telemetry


router = APIRouter(prefix="/machines", tags=["machines"])


@router.get("")
def list_machines(db: Session = Depends(get_db)) -> list[dict]:
    machines = db.scalars(select(Machine).order_by(Machine.id.asc())).all()
    output: list[dict] = []

    for machine in machines:
        health_row = db.scalar(
            select(MachineHealth)
            .where(MachineHealth.machine_id == machine.id)
            .order_by(desc(MachineHealth.last_updated))
            .limit(1)
        )

        output.append(
            {
                "id": machine.id,
                "name": machine.name,
                "type": machine.type,
                "location": machine.location,
                "status": machine.status,
                "health": None if health_row is None else health_row.health_score,
            }
        )

    return output


@router.get("/{machine_id}")
def get_machine(machine_id: int, db: Session = Depends(get_db)) -> dict:
    machine = db.scalar(select(Machine).where(Machine.id == machine_id))
    if machine is None:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")

    return {
        "id": machine.id,
        "name": machine.name,
        "type": machine.type,
        "location": machine.location,
        "status": machine.status,
        "installed_date": machine.installed_date,
        "last_maintenance": machine.last_maintenance,
    }


@router.get("/{machine_id}/health")
def get_machine_health(machine_id: int, db: Session = Depends(get_db)) -> dict:
    machine = db.scalar(select(Machine).where(Machine.id == machine_id))
    if machine is None:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")

    row = db.scalar(
        select(MachineHealth)
        .where(MachineHealth.machine_id == machine_id)
        .order_by(desc(MachineHealth.last_updated))
        .limit(1)
    )
    if row is None:
        return {
            "machine_id": machine_id,
            "health_score": None,
            "anomaly_score": None,
            "rul_hours": None,
            "last_updated": None,
        }

    return {
        "machine_id": machine_id,
        "health_score": row.health_score,
        "anomaly_score": row.anomaly_score,
        "rul_hours": row.rul_hours,
        "last_updated": row.last_updated,
    }


@router.get("/{machine_id}/telemetry")
def get_machine_telemetry(machine_id: int, limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    machine = db.scalar(select(Machine).where(Machine.id == machine_id))
    if machine is None:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")

    rows = db.scalars(
        select(Telemetry)
        .where(Telemetry.machine_id == machine_id)
        .order_by(desc(Telemetry.timestamp))
        .limit(max(1, min(limit, 500)))
    ).all()

    return [
        {
            "id": row.id,
            "machine_id": row.machine_id,
            "temperature": row.temperature,
            "vibration": row.vibration,
            "pressure": row.pressure,
            "rpm": row.rpm,
            "timestamp": row.timestamp,
        }
        for row in rows
    ]

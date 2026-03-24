"""Analytics endpoints for dashboard KPIs and operational insights."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.schemas.dependencies import get_db
from database.models.machine import Machine
from database.models.machine_health import MachineHealth
from database.models.maintenance_task import MaintenanceTask
from database.models.sim_product import SimProduct
from services.digital_twin import twin_repository


router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/kpi")
def get_kpi(db: Session = Depends(get_db)) -> dict:
    throughput = db.scalar(
        select(func.count()).select_from(SimProduct).where(SimProduct.status == "completed")
    ) or 0

    total_machines = db.scalar(select(func.count()).select_from(Machine)) or 0
    running_machines = db.scalar(
        select(func.count()).select_from(Machine).where(Machine.status == "running")
    ) or 0

    utilization = (float(running_machines) / float(total_machines)) if total_machines else 0.0

    downtime = db.scalar(
        select(func.count())
        .select_from(MaintenanceTask)
        .where(MaintenanceTask.status.in_(["scheduled", "in_progress"]))
    ) or 0

    twin = twin_repository.get_full_twin_state()
    metrics = twin.get("production_metrics", {})
    oee = round(utilization * (1.0 - min(float(downtime) / 100.0, 0.9)), 3)

    return {
        "throughput": int(metrics.get("throughput", throughput)),
        "utilization": round(utilization, 3),
        "downtime": int(downtime),
        "oee": oee,
    }


@router.get("/utilization")
def get_machine_utilization(db: Session = Depends(get_db)) -> list[dict]:
    machines = db.scalars(select(Machine).order_by(Machine.id.asc())).all()
    return [
        {
            "machine_id": machine.id,
            "machine_name": machine.name,
            "status": machine.status,
            "utilization": 1.0 if machine.status == "running" else 0.0,
        }
        for machine in machines
    ]


@router.get("/downtime")
def get_downtime_stats(db: Session = Depends(get_db)) -> dict:
    open_tasks = db.scalar(
        select(func.count()).select_from(MaintenanceTask).where(
            MaintenanceTask.status.in_(["scheduled", "in_progress"])
        )
    ) or 0
    completed_tasks = db.scalar(
        select(func.count()).select_from(MaintenanceTask).where(MaintenanceTask.status == "completed")
    ) or 0

    return {
        "open_maintenance_tasks": int(open_tasks),
        "completed_maintenance_tasks": int(completed_tasks),
        "downtime_events": int(open_tasks + completed_tasks),
    }


@router.get("/throughput")
def get_throughput_metrics(db: Session = Depends(get_db)) -> dict:
    completed = db.scalar(
        select(func.count()).select_from(SimProduct).where(SimProduct.status == "completed")
    ) or 0
    in_progress = db.scalar(
        select(func.count()).select_from(SimProduct).where(SimProduct.status == "in_progress")
    ) or 0
    created = db.scalar(select(func.count()).select_from(SimProduct)) or 0

    return {
        "created_products": int(created),
        "in_progress_products": int(in_progress),
        "completed_products": int(completed),
    }

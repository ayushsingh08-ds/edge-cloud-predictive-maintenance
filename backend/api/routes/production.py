"""Production monitoring endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.schemas.dependencies import get_db
from database.models.machine import Machine
from database.models.machine_queue import MachineQueue
from database.models.production_node import ProductionNode
from database.models.route import Route
from database.models.sim_product import SimProduct


router = APIRouter(prefix="/production", tags=["production"])


@router.get("/status")
def get_production_status(db: Session = Depends(get_db)) -> dict:
    total_products = db.scalar(select(func.count()).select_from(SimProduct)) or 0
    completed_products = db.scalar(
        select(func.count()).select_from(SimProduct).where(SimProduct.status == "completed")
    ) or 0
    in_progress_products = db.scalar(
        select(func.count()).select_from(SimProduct).where(SimProduct.status == "in_progress")
    ) or 0

    total_machines = db.scalar(select(func.count()).select_from(Machine)) or 0
    active_machines = db.scalar(
        select(func.count()).select_from(Machine).where(Machine.status == "running")
    ) or 0

    return {
        "total_products": int(total_products),
        "in_progress_products": int(in_progress_products),
        "completed_products": int(completed_products),
        "total_machines": int(total_machines),
        "active_machines": int(active_machines),
    }


@router.get("/products")
def list_products(db: Session = Depends(get_db)) -> list[dict]:
    products = db.scalars(select(SimProduct).order_by(SimProduct.created_at.desc())).all()
    node_names = {
        row.id: row.node_name
        for row in db.scalars(select(ProductionNode).order_by(ProductionNode.id.asc())).all()
    }

    return [
        {
            "product_id": item.product_id,
            "current_node_id": item.current_node_id,
            "current_location": node_names.get(item.current_node_id),
            "status": item.status,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }
        for item in products
    ]


@router.get("/routes")
def list_routes(db: Session = Depends(get_db)) -> list[dict]:
    routes = db.scalars(select(Route).order_by(Route.id.asc())).all()
    node_names = {
        row.id: row.node_name
        for row in db.scalars(select(ProductionNode).order_by(ProductionNode.id.asc())).all()
    }

    return [
        {
            "id": item.id,
            "route_name": item.route_name,
            "start_node_id": item.start_node_id,
            "start_node_name": node_names.get(item.start_node_id),
            "end_node_id": item.end_node_id,
            "end_node_name": node_names.get(item.end_node_id),
        }
        for item in routes
    ]


@router.get("/queues")
def list_machine_queues(db: Session = Depends(get_db)) -> list[dict]:
    queues = db.scalars(select(MachineQueue).order_by(MachineQueue.machine_id.asc())).all()
    machines = {
        row.id: row.name
        for row in db.scalars(select(Machine).order_by(Machine.id.asc())).all()
    }

    return [
        {
            "machine_id": item.machine_id,
            "machine_name": machines.get(item.machine_id),
            "queue_length": item.queue_length,
            "updated_at": item.updated_at,
        }
        for item in queues
    ]

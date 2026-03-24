"""Repository layer for routing engine database queries."""

from __future__ import annotations

from sqlalchemy import desc, select

from database.db_session import SessionLocal
from database.models.machine import Machine
from database.models.machine_health import MachineHealth
from database.models.maintenance_task import MaintenanceTask
from database.models.production_edge import ProductionEdge
from database.models.production_node import ProductionNode


def get_machine_health(machine_id: int) -> float | None:
    """Return latest machine health score, if available."""
    db = SessionLocal()
    try:
        row = db.scalar(
            select(MachineHealth)
            .where(MachineHealth.machine_id == machine_id)
            .order_by(desc(MachineHealth.last_updated))
            .limit(1)
        )
        return None if row is None else float(row.health_score)
    finally:
        db.close()


def get_machine_status(machine_id: int) -> str | None:
    db = SessionLocal()
    try:
        machine = db.scalar(select(Machine).where(Machine.id == machine_id))
        return None if machine is None else str(machine.status)
    finally:
        db.close()


def get_machine_queue(machine_id: int) -> int:
    """Return queue/load proxy for a machine.

    The current schema has no dedicated product queue table, so open
    maintenance tasks are used as a conservative load proxy.
    """
    db = SessionLocal()
    try:
        items = db.scalars(
            select(MaintenanceTask)
            .where(MaintenanceTask.machine_id == machine_id)
            .where(MaintenanceTask.status.in_(["scheduled", "in_progress"]))
        ).all()
        return len(items)
    finally:
        db.close()


def get_available_machines() -> list[dict]:
    """Return running machines with acceptable health and no open maintenance."""
    db = SessionLocal()
    try:
        machines = db.scalars(select(Machine).order_by(Machine.id.asc())).all()
        result: list[dict] = []

        for machine in machines:
            status = str(machine.status).lower()
            if status == "maintenance":
                continue

            open_maintenance = db.scalar(
                select(MaintenanceTask)
                .where(MaintenanceTask.machine_id == machine.id)
                .where(MaintenanceTask.status.in_(["scheduled", "in_progress"]))
                .limit(1)
            )
            if open_maintenance is not None:
                continue

            health = db.scalar(
                select(MachineHealth)
                .where(MachineHealth.machine_id == machine.id)
                .order_by(desc(MachineHealth.last_updated))
                .limit(1)
            )
            health_score = 1.0 if health is None else float(health.health_score)
            if health_score < 0.5:
                continue

            result.append(
                {
                    "machine_id": machine.id,
                    "status": machine.status,
                    "health_score": health_score,
                    "queue_length": get_machine_queue(machine.id),
                }
            )

        return result
    finally:
        db.close()


def get_machine_node(machine_id: int) -> dict | None:
    db = SessionLocal()
    try:
        node = db.scalar(
            select(ProductionNode)
            .where(ProductionNode.machine_id == machine_id)
            .where(ProductionNode.node_type == "machine")
            .order_by(ProductionNode.id.asc())
            .limit(1)
        )
        if node is None:
            return None

        return {
            "id": node.id,
            "node_name": node.node_name,
            "node_type": node.node_type,
            "machine_id": node.machine_id,
            "position_x": node.position_x,
            "position_y": node.position_y,
        }
    finally:
        db.close()


def get_graph_edges() -> list[dict]:
    db = SessionLocal()
    try:
        edges = db.scalars(select(ProductionEdge).order_by(ProductionEdge.id.asc())).all()
        return [
            {
                "id": edge.id,
                "from_node_id": edge.from_node_id,
                "to_node_id": edge.to_node_id,
                "distance": float(edge.distance),
                "travel_time": float(edge.travel_time),
                "capacity": float(edge.capacity),
            }
            for edge in edges
        ]
    finally:
        db.close()


def get_neighbors(node_id: int) -> list[dict]:
    db = SessionLocal()
    try:
        edges = db.scalars(
            select(ProductionEdge).where(ProductionEdge.from_node_id == node_id)
        ).all()

        output: list[dict] = []
        for edge in edges:
            node = db.scalar(select(ProductionNode).where(ProductionNode.id == edge.to_node_id))
            if node is None:
                continue

            output.append(
                {
                    "id": node.id,
                    "node_name": node.node_name,
                    "node_type": node.node_type,
                    "machine_id": node.machine_id,
                    "distance": float(edge.distance),
                    "travel_time": float(edge.travel_time),
                    "capacity": float(edge.capacity),
                }
            )

        return output
    finally:
        db.close()


def get_node(node_id: int) -> dict | None:
    db = SessionLocal()
    try:
        node = db.scalar(select(ProductionNode).where(ProductionNode.id == node_id))
        if node is None:
            return None
        return {
            "id": node.id,
            "node_name": node.node_name,
            "node_type": node.node_type,
            "machine_id": node.machine_id,
            "position_x": node.position_x,
            "position_y": node.position_y,
        }
    finally:
        db.close()


def get_machine_id_for_node(node_id: int) -> int | None:
    node = get_node(node_id)
    if node is None:
        return None
    return node.get("machine_id")


def get_all_machine_node_ids() -> list[int]:
    db = SessionLocal()
    try:
        node_ids = db.scalars(
            select(ProductionNode.id)
            .where(ProductionNode.node_type == "machine")
            .order_by(ProductionNode.id.asc())
        ).all()
        return list(node_ids)
    finally:
        db.close()

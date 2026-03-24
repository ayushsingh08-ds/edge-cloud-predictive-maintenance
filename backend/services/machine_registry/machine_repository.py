"""Repository layer for machine registry persistence."""

from __future__ import annotations

from sqlalchemy import or_, select

from database.db_session import SessionLocal
from database.models.machine import Machine
from database.models.machine_connection import MachineConnection


ALLOWED_MACHINE_STATUS = {"running", "stopped", "maintenance"}


def _machine_to_dict(machine: Machine) -> dict:
    return {
        "id": machine.id,
        "name": machine.name,
        "type": machine.type,
        "location": machine.location,
        "status": machine.status,
    }


def create_machine(name: str, type: str, location: str, status: str = "running") -> dict:
    if status not in ALLOWED_MACHINE_STATUS:
        raise ValueError(f"Invalid machine status: {status}")

    db = SessionLocal()
    try:
        machine = Machine(name=name, type=type, location=location, status=status)
        db.add(machine)
        db.commit()
        db.refresh(machine)
        return _machine_to_dict(machine)
    finally:
        db.close()


def get_machine(machine_id: int) -> dict | None:
    db = SessionLocal()
    try:
        machine = db.scalar(select(Machine).where(Machine.id == machine_id))
        if machine is None:
            return None
        return _machine_to_dict(machine)
    finally:
        db.close()


def get_all_machines() -> list[dict]:
    db = SessionLocal()
    try:
        machines = db.scalars(select(Machine).order_by(Machine.id.asc())).all()
        return [_machine_to_dict(machine) for machine in machines]
    finally:
        db.close()


def update_machine_status(machine_id: int, status: str) -> dict | None:
    if status not in ALLOWED_MACHINE_STATUS:
        raise ValueError(f"Invalid machine status: {status}")

    db = SessionLocal()
    try:
        machine = db.scalar(select(Machine).where(Machine.id == machine_id))
        if machine is None:
            return None

        machine.status = status
        db.commit()
        db.refresh(machine)
        return _machine_to_dict(machine)
    finally:
        db.close()


def delete_machine(machine_id: int) -> bool:
    db = SessionLocal()
    try:
        machine = db.scalar(select(Machine).where(Machine.id == machine_id))
        if machine is None:
            return False

        db.delete(machine)
        db.commit()
        return True
    finally:
        db.close()


def connect_machines(from_machine_id: int, to_machine_id: int) -> dict:
    if from_machine_id == to_machine_id:
        raise ValueError("A machine cannot connect to itself")

    db = SessionLocal()
    try:
        from_machine = db.scalar(select(Machine).where(Machine.id == from_machine_id))
        to_machine = db.scalar(select(Machine).where(Machine.id == to_machine_id))

        if from_machine is None or to_machine is None:
            raise ValueError("Both machines must exist before creating a connection")

        existing = db.scalar(
            select(MachineConnection).where(
                MachineConnection.from_machine_id == from_machine_id,
                MachineConnection.to_machine_id == to_machine_id,
            )
        )
        if existing is not None:
            return {
                "id": existing.id,
                "from_machine_id": existing.from_machine_id,
                "to_machine_id": existing.to_machine_id,
            }

        connection = MachineConnection(
            from_machine_id=from_machine_id,
            to_machine_id=to_machine_id,
        )
        db.add(connection)
        db.commit()
        db.refresh(connection)

        return {
            "id": connection.id,
            "from_machine_id": connection.from_machine_id,
            "to_machine_id": connection.to_machine_id,
        }
    finally:
        db.close()


def get_machine_connections(machine_id: int) -> list[dict]:
    db = SessionLocal()
    try:
        connections = db.scalars(
            select(MachineConnection).where(
                or_(
                    MachineConnection.from_machine_id == machine_id,
                    MachineConnection.to_machine_id == machine_id,
                )
            )
        ).all()

        return [
            {
                "id": connection.id,
                "from_machine_id": connection.from_machine_id,
                "to_machine_id": connection.to_machine_id,
            }
            for connection in connections
        ]
    finally:
        db.close()

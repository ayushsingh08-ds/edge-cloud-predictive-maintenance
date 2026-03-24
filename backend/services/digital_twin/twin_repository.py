"""Repository operations for digital twin persisted state."""

from __future__ import annotations

from copy import deepcopy

from sqlalchemy import desc, select

from database.db_session import SessionLocal
from database.models.twin_snapshot import TwinSnapshot


def _default_state() -> dict:
    return {
        "machines": {},
        "products": {},
        "queues": {},
        "maintenance": {},
        "production_metrics": {
            "throughput": 0,
            "active_machines": 0,
            "completed_products": 0,
            "average_processing_time": 0.0,
        },
    }


def _row_to_state(row: TwinSnapshot | None) -> dict:
    if row is None:
        return _default_state()

    return {
        "machines": row.machines or {},
        "products": row.products or {},
        "queues": row.queues or {},
        "maintenance": row.maintenance or {},
        "production_metrics": row.production_metrics or _default_state()["production_metrics"],
    }


def _get_latest_snapshot(db) -> TwinSnapshot | None:
    return db.scalar(
        select(TwinSnapshot)
        .order_by(desc(TwinSnapshot.created_at), desc(TwinSnapshot.id))
        .limit(1)
    )


def get_full_twin_state() -> dict:
    db = SessionLocal()
    try:
        latest = _get_latest_snapshot(db)
        return _row_to_state(latest)
    finally:
        db.close()


def store_twin_snapshot(state: dict) -> dict:
    db = SessionLocal()
    try:
        snapshot = TwinSnapshot(
            machines=deepcopy(state.get("machines", {})),
            products=deepcopy(state.get("products", {})),
            queues=deepcopy(state.get("queues", {})),
            maintenance=deepcopy(state.get("maintenance", {})),
            production_metrics=deepcopy(state.get("production_metrics", {})),
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        return _row_to_state(snapshot)
    finally:
        db.close()


def _persist_with_mutation(mutator) -> dict:
    current = get_full_twin_state()
    mutator(current)
    return store_twin_snapshot(current)


def update_machine_state(
    machine_id: int,
    status: str,
    health: float | None = None,
    current_product: str | None = None,
    queue_length: int | None = None,
) -> dict:
    def _mutate(state: dict) -> None:
        key = str(machine_id)
        machine_entry = state["machines"].setdefault(
            key,
            {
                "machine_id": machine_id,
                "status": "unknown",
                "health": None,
                "current_product": None,
                "queue_length": 0,
            },
        )

        machine_entry["status"] = status
        if health is not None:
            machine_entry["health"] = health
        if current_product is not None:
            machine_entry["current_product"] = current_product
        if queue_length is not None:
            machine_entry["queue_length"] = queue_length

    return _persist_with_mutation(_mutate)


def update_product_position(
    product_id: str,
    current_location: int | str,
    status: str,
    route: list[int] | list[str] | None = None,
) -> dict:
    def _mutate(state: dict) -> None:
        key = str(product_id)
        entry = state["products"].setdefault(
            key,
            {
                "product_id": str(product_id),
                "current_location": None,
                "status": "created",
                "route": [],
            },
        )
        entry["current_location"] = current_location
        entry["status"] = status
        if route is not None:
            entry["route"] = list(route)

    return _persist_with_mutation(_mutate)


def update_queue_state(
    machine_id: int,
    queue_length: int,
    products_in_queue: list[str] | None = None,
) -> dict:
    def _mutate(state: dict) -> None:
        key = str(machine_id)
        state["queues"][key] = {
            "machine_id": machine_id,
            "queue_length": max(0, int(queue_length)),
            "products_in_queue": products_in_queue or [],
        }

        machine_entry = state["machines"].setdefault(
            key,
            {
                "machine_id": machine_id,
                "status": "unknown",
                "health": None,
                "current_product": None,
                "queue_length": 0,
            },
        )
        machine_entry["queue_length"] = max(0, int(queue_length))

    return _persist_with_mutation(_mutate)


def update_machine_health(machine_id: int, health: float) -> dict:
    def _mutate(state: dict) -> None:
        key = str(machine_id)
        machine_entry = state["machines"].setdefault(
            key,
            {
                "machine_id": machine_id,
                "status": "unknown",
                "health": None,
                "current_product": None,
                "queue_length": 0,
            },
        )
        machine_entry["health"] = float(health)

    return _persist_with_mutation(_mutate)


def update_maintenance_state(
    machine_id: int,
    maintenance_status: str,
    scheduled_date: str | None = None,
) -> dict:
    def _mutate(state: dict) -> None:
        key = str(machine_id)
        state["maintenance"][key] = {
            "machine_id": machine_id,
            "maintenance_status": maintenance_status,
            "scheduled_date": scheduled_date,
        }

        machine_entry = state["machines"].setdefault(
            key,
            {
                "machine_id": machine_id,
                "status": "unknown",
                "health": None,
                "current_product": None,
                "queue_length": 0,
            },
        )
        if maintenance_status in {"scheduled", "in_progress"}:
            machine_entry["status"] = "maintenance"

    return _persist_with_mutation(_mutate)


def update_production_metrics(metrics: dict) -> dict:
    def _mutate(state: dict) -> None:
        state["production_metrics"].update(metrics)

    return _persist_with_mutation(_mutate)

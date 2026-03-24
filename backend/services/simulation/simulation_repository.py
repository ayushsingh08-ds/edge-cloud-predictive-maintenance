"""Repository layer for product flow simulation persistence."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from database.db_session import SessionLocal
from database.models.machine_queue import MachineQueue
from database.models.product_history import ProductHistory
from database.models.sim_product import SimProduct


def _product_to_dict(product: SimProduct) -> dict:
    return {
        "product_id": product.product_id,
        "current_node_id": product.current_node_id,
        "status": product.status,
        "created_at": product.created_at,
        "updated_at": product.updated_at,
    }


def create_product(product_id: str, start_node: int) -> dict:
    db = SessionLocal()
    try:
        existing = db.scalar(select(SimProduct).where(SimProduct.product_id == product_id))
        if existing is not None:
            return _product_to_dict(existing)

        product = SimProduct(
            product_id=product_id,
            current_node_id=start_node,
            status="created",
        )
        db.add(product)
        db.commit()
        db.refresh(product)
        return _product_to_dict(product)
    finally:
        db.close()


def update_product_location(product_id: str, node_id: int) -> dict | None:
    db = SessionLocal()
    try:
        product = db.scalar(select(SimProduct).where(SimProduct.product_id == product_id))
        if product is None:
            return None

        product.current_node_id = node_id
        db.commit()
        db.refresh(product)
        return _product_to_dict(product)
    finally:
        db.close()


def update_product_status(product_id: str, status: str) -> dict | None:
    db = SessionLocal()
    try:
        product = db.scalar(select(SimProduct).where(SimProduct.product_id == product_id))
        if product is None:
            return None

        product.status = status
        db.commit()
        db.refresh(product)
        return _product_to_dict(product)
    finally:
        db.close()


def get_product(product_id: str) -> dict | None:
    db = SessionLocal()
    try:
        product = db.scalar(select(SimProduct).where(SimProduct.product_id == product_id))
        if product is None:
            return None
        return _product_to_dict(product)
    finally:
        db.close()


def get_products_in_queue(machine_id: int) -> list[dict]:
    """Return queue placeholders for compatibility with requested signature.

    Dedicated queue-member table is not present; this returns placeholders based
    on persisted queue length.
    """
    queue_length = get_queue_length(machine_id)
    return [
        {
            "machine_id": machine_id,
            "position": idx + 1,
            "product_id": f"queue-item-{idx + 1}",
        }
        for idx in range(queue_length)
    ]


def update_queue(machine_id: int, queue_length: int) -> dict:
    db = SessionLocal()
    try:
        queue = db.scalar(select(MachineQueue).where(MachineQueue.machine_id == machine_id))
        if queue is None:
            queue = MachineQueue(machine_id=machine_id, queue_length=max(0, queue_length))
            db.add(queue)
        else:
            queue.queue_length = max(0, queue_length)

        db.commit()
        db.refresh(queue)
        return {
            "machine_id": queue.machine_id,
            "queue_length": queue.queue_length,
            "updated_at": queue.updated_at,
        }
    finally:
        db.close()


def get_queue_length(machine_id: int) -> int:
    db = SessionLocal()
    try:
        queue = db.scalar(select(MachineQueue).where(MachineQueue.machine_id == machine_id))
        if queue is None:
            return 0
        return int(queue.queue_length)
    finally:
        db.close()


def store_product_history(
    product_id: str,
    node_id: int,
    timestamp: datetime | None = None,
) -> dict:
    db = SessionLocal()
    try:
        entry = ProductHistory(
            product_id=product_id,
            node_id=node_id,
            timestamp=timestamp or datetime.now(timezone.utc),
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return {
            "id": entry.id,
            "product_id": entry.product_id,
            "node_id": entry.node_id,
            "timestamp": entry.timestamp,
        }
    finally:
        db.close()


def get_product_history(product_id: str) -> list[dict]:
    db = SessionLocal()
    try:
        rows = db.scalars(
            select(ProductHistory)
            .where(ProductHistory.product_id == product_id)
            .order_by(ProductHistory.timestamp.asc())
        ).all()

        return [
            {
                "id": item.id,
                "product_id": item.product_id,
                "node_id": item.node_id,
                "timestamp": item.timestamp,
            }
            for item in rows
        ]
    finally:
        db.close()

"""Alert endpoints for machine and global alert views."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from api.schemas.dependencies import get_db
from database.models.alert import Alert


router = APIRouter(prefix="/alerts", tags=["alerts"])


def _alert_to_dict(alert: Alert) -> dict:
    return {
        "id": alert.id,
        "machine_id": alert.machine_id,
        "alert_type": alert.alert_type,
        "message": alert.message,
        "severity": alert.severity,
        "timestamp": alert.timestamp,
    }


@router.get("")
def list_alerts(limit: int = 100, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(
        select(Alert).order_by(desc(Alert.timestamp)).limit(max(1, min(limit, 1000)))
    ).all()
    return [_alert_to_dict(row) for row in rows]


@router.get("/{machine_id}")
def list_machine_alerts(machine_id: int, limit: int = 100, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(
        select(Alert)
        .where(Alert.machine_id == machine_id)
        .order_by(desc(Alert.timestamp))
        .limit(max(1, min(limit, 1000)))
    ).all()
    return [_alert_to_dict(row) for row in rows]

"""Repository operations for analytics KPI persistence and retrieval."""

from __future__ import annotations

from sqlalchemy import desc, select

from database.db_session import SessionLocal
from database.models.analytics_snapshot import AnalyticsSnapshot


def _row_to_dict(row: AnalyticsSnapshot | None) -> dict:
    if row is None:
        return {
            "throughput": 0.0,
            "utilization": {},
            "downtime": {},
            "mtbf": {},
            "mttr": {},
            "oee": 0.0,
            "bottleneck_machine": {},
            "timestamp": None,
        }

    return {
        "throughput": float(row.throughput),
        "utilization": row.utilization or {},
        "downtime": row.downtime or {},
        "mtbf": row.mtbf or {},
        "mttr": row.mttr or {},
        "oee": float(row.oee),
        "bottleneck_machine": row.bottleneck_machine or {},
        "timestamp": row.created_at,
    }


def _get_latest_snapshot(db) -> AnalyticsSnapshot | None:
    return db.scalar(
        select(AnalyticsSnapshot)
        .order_by(desc(AnalyticsSnapshot.created_at))
        .limit(1)
    )


def _persist_metric(metric_key: str, value) -> dict:
    db = SessionLocal()
    try:
        latest = _get_latest_snapshot(db)
        if latest is None:
            latest = AnalyticsSnapshot()
            db.add(latest)
            db.flush()

        setattr(latest, metric_key, value)
        db.commit()
        db.refresh(latest)
        return _row_to_dict(latest)
    finally:
        db.close()


def store_throughput(value: float) -> dict:
    return _persist_metric("throughput", float(value))


def store_utilization(value: dict) -> dict:
    return _persist_metric("utilization", value)


def store_downtime(value: dict) -> dict:
    return _persist_metric("downtime", value)


def store_mtbf(value: dict) -> dict:
    return _persist_metric("mtbf", value)


def store_mttr(value: dict) -> dict:
    return _persist_metric("mttr", value)


def store_oee(value: float) -> dict:
    return _persist_metric("oee", float(value))


def store_bottleneck(value: dict) -> dict:
    return _persist_metric("bottleneck_machine", value)


def get_analytics_metrics() -> dict:
    db = SessionLocal()
    try:
        return _row_to_dict(_get_latest_snapshot(db))
    finally:
        db.close()


def get_machine_utilization() -> dict:
    snapshot = get_analytics_metrics()
    return snapshot.get("utilization", {})


def get_downtime_stats() -> dict:
    snapshot = get_analytics_metrics()
    return snapshot.get("downtime", {})

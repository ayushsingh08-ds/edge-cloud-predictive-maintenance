"""Database session manager and basic CRUD utilities for routing persistence."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator, Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base, JobORM, OperationORM, RoutingHistoryORM


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./predictive_maintenance.db")

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def save_job_record(db: Session, payload: dict[str, Any]) -> JobORM:
    record = JobORM(
        job_id=payload["job_id"],
        arrival_time=payload["arrival_time"],
        due_date=payload["due_date"],
        start_time=payload.get("start_time"),
        completion_time=payload.get("completion_time"),
        sequencing_mode=payload.get("sequencing_mode", "serial"),
    )
    db.add(record)
    db.flush()
    return record


def save_operation_record(db: Session, job_fk: int, payload: dict[str, Any]) -> OperationORM:
    record = OperationORM(
        job_fk=job_fk,
        op_id=payload["op_id"],
        sequence_type=payload.get("sequence_type", "serial"),
        candidate_machines=payload.get("candidate_machines", []),
        assigned_machine=payload.get("assigned_machine"),
        processing_time=payload["processing_time"],
        status=payload.get("status", "pending"),
        completed=payload.get("completed", False),
        start_time=payload.get("start_time"),
        completion_time=payload.get("completion_time"),
        reroute_count=payload.get("reroute_count", 0),
    )
    db.add(record)
    db.flush()
    return record


def save_routing_event(db: Session, job_fk: int, payload: dict[str, Any]) -> RoutingHistoryORM:
    record = RoutingHistoryORM(
        job_fk=job_fk,
        operation_id=payload.get("operation_id", 0),
        event_time=payload.get("event_time", 0.0),
        event_type=payload.get("event_type", "operation_routed"),
        from_machine_id=payload.get("from_machine_id"),
        to_machine_id=payload.get("to_machine_id"),
        machine_id=payload.get("machine_id"),
        candidate_machines=payload.get("candidate_machines", []),
        policy=payload.get("policy"),
        event_metadata=payload.get("event_metadata", {}),
    )
    db.add(record)
    db.flush()
    return record


def fetch_job_with_operations(db: Session, job_id: int) -> dict[str, Any] | None:
    job = db.execute(
        select(JobORM)
        .where(JobORM.job_id == job_id)
        .order_by(JobORM.created_at.desc(), JobORM.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if job is None:
        return None

    operations = db.execute(select(OperationORM).where(OperationORM.job_fk == job.id)).scalars().all()
    routing = db.execute(select(RoutingHistoryORM).where(RoutingHistoryORM.job_fk == job.id)).scalars().all()

    return {
        "job": job,
        "operations": operations,
        "routing_events": routing,
    }


def serialize_job_record(payload: dict[str, Any]) -> dict[str, Any]:
    job = payload["job"]
    operations = sorted(payload["operations"], key=lambda op: op.op_id)
    routing_events = sorted(payload["routing_events"], key=lambda ev: ev.event_time)

    return {
        "job_id": job.job_id,
        "arrival_time": job.arrival_time,
        "due_date": job.due_date,
        "start_time": job.start_time,
        "completion_time": job.completion_time,
        "sequencing_mode": job.sequencing_mode,
        "operations": [
            {
                "op_id": op.op_id,
                "sequence_type": op.sequence_type,
                "candidate_machines": op.candidate_machines,
                "assigned_machine": op.assigned_machine,
                "processing_time": op.processing_time,
                "status": op.status,
                "completed": op.completed,
                "start_time": op.start_time,
                "completion_time": op.completion_time,
                "reroute_count": op.reroute_count,
            }
            for op in operations
        ],
        "routing_events": [
            {
                "time": ev.event_time,
                "event": ev.event_type,
                "job_id": job.job_id,
                "operation": ev.operation_id,
                "machine_id": ev.machine_id,
                "from_machine_id": ev.from_machine_id,
                "to_machine_id": ev.to_machine_id,
                "candidate_machines": ev.candidate_machines,
                "policy": ev.policy,
                "metadata": ev.event_metadata,
            }
            for ev in routing_events
        ],
    }


def fetch_operations(
    db: Session,
    *,
    job_id: int | None = None,
    op_id: int | None = None,
    limit: int = 200,
) -> list[OperationORM]:
    stmt = select(OperationORM)
    if job_id is not None:
        stmt = stmt.join(JobORM, OperationORM.job_fk == JobORM.id).where(JobORM.job_id == job_id)
    if op_id is not None:
        stmt = stmt.where(OperationORM.op_id == op_id)
    stmt = stmt.order_by(OperationORM.job_fk.desc(), OperationORM.op_id.asc()).limit(limit)
    return list(db.execute(stmt).scalars().all())


def fetch_routing_history(
    db: Session,
    *,
    job_id: int | None = None,
    operation_id: int | None = None,
    limit: int = 500,
) -> list[RoutingHistoryORM]:
    stmt = select(RoutingHistoryORM)
    if job_id is not None:
        stmt = stmt.join(JobORM, RoutingHistoryORM.job_fk == JobORM.id).where(JobORM.job_id == job_id)
    if operation_id is not None:
        stmt = stmt.where(RoutingHistoryORM.operation_id == operation_id)
    stmt = stmt.order_by(RoutingHistoryORM.event_time.asc(), RoutingHistoryORM.id.asc()).limit(limit)
    return list(db.execute(stmt).scalars().all())


def fetch_recent_jobs_with_details(db: Session, *, limit: int = 100) -> list[dict[str, Any]]:
    jobs = db.execute(select(JobORM).order_by(JobORM.id.desc()).limit(limit)).scalars().all()
    payload: list[dict[str, Any]] = []
    for job in jobs:
        operations = db.execute(select(OperationORM).where(OperationORM.job_fk == job.id)).scalars().all()
        routing = db.execute(select(RoutingHistoryORM).where(RoutingHistoryORM.job_fk == job.id)).scalars().all()
        payload.append(
            serialize_job_record(
                {
                    "job": job,
                    "operations": operations,
                    "routing_events": routing,
                }
            )
        )
    return payload

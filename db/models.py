"""SQLAlchemy models for flexible job-shop routing persistence."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class JobORM(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(Integer, index=True)
    arrival_time: Mapped[float] = mapped_column(Float)
    due_date: Mapped[float] = mapped_column(Float)
    start_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    completion_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    sequencing_mode: Mapped[str] = mapped_column(String(20), default="serial")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    operations: Mapped[list["OperationORM"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    routing_events: Mapped[list["RoutingHistoryORM"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class OperationORM(Base):
    __tablename__ = "operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_fk: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    op_id: Mapped[int] = mapped_column(Integer)
    sequence_type: Mapped[str] = mapped_column(String(20), default="serial")
    candidate_machines: Mapped[list[int]] = mapped_column(JSON)
    assigned_machine: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processing_time: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    start_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    completion_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    reroute_count: Mapped[int] = mapped_column(Integer, default=0)

    job: Mapped["JobORM"] = relationship(back_populates="operations")


class RoutingHistoryORM(Base):
    __tablename__ = "routing_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_fk: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    operation_id: Mapped[int] = mapped_column(Integer)
    event_time: Mapped[float] = mapped_column(Float)
    event_type: Mapped[str] = mapped_column(String(50))
    from_machine_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    to_machine_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    machine_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    candidate_machines: Mapped[list[int]] = mapped_column(JSON, default=list)
    policy: Mapped[str | None] = mapped_column(String(40), nullable=True)
    event_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    job: Mapped["JobORM"] = relationship(back_populates="routing_events")

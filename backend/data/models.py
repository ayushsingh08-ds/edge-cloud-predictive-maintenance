from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Telemetry(Base):
    __tablename__ = "telemetry"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    machine_id: Mapped[str] = mapped_column(String(50), index=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON)
    # Individual shortcut columns for common metrics to speed up playback/scaling
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    vibration: Mapped[float | None] = mapped_column(Float, nullable=True)
    load: Mapped[float | None] = mapped_column(Float, nullable=True)


class MachineHealth(Base):
    __tablename__ = "machine_health"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    machine_id: Mapped[str] = mapped_column(String(50), index=True)
    health_score: Mapped[float] = mapped_column(Float)
    risk_score: Mapped[float] = mapped_column(Float)
    remaining_useful_life: Mapped[float] = mapped_column(Float)


class RoutingLog(Base):
    __tablename__ = "routing_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    request_id: Mapped[str] = mapped_column(String(100), index=True)
    divider_id: Mapped[str] = mapped_column(String(50))
    to_node: Mapped[str] = mapped_column(String(50))
    policy: Mapped[str] = mapped_column(String(50))


class MachineFailure(Base):
    __tablename__ = "machine_failures"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    machine_id: Mapped[str] = mapped_column(String(50), index=True)
    failure_type: Mapped[str] = mapped_column(String(50))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=True)


class MaintenanceLog(Base):
    __tablename__ = "maintenance_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    machine_id: Mapped[str] = mapped_column(String(50), index=True)
    action: Mapped[str] = mapped_column(String(100))
    reason: Mapped[str] = mapped_column(String(200))


class QueueHistory(Base):
    __tablename__ = "queue_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    node_id: Mapped[str] = mapped_column(String(50), index=True)
    queue_length: Mapped[int] = mapped_column(Integer)


class ThroughputHistory(Base):
    __tablename__ = "throughput_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    machine_id: Mapped[str] = mapped_column(String(50), index=True)
    throughput_hr: Mapped[float] = mapped_column(Float)
    completed_jobs: Mapped[int] = mapped_column(Integer)

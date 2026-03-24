"""Machine ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Machine(Base):
    __tablename__ = "machines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    type: Mapped[str] = mapped_column(String(80), nullable=False)
    location: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    installed_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    last_maintenance: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    health_records = relationship(
        "MachineHealth",
        back_populates="machine",
        cascade="all, delete-orphan",
    )
    telemetry_records = relationship(
        "Telemetry",
        back_populates="machine",
        cascade="all, delete-orphan",
    )
    rul_predictions = relationship(
        "RULPrediction",
        back_populates="machine",
        cascade="all, delete-orphan",
    )
    maintenance_tasks = relationship(
        "MaintenanceTask",
        back_populates="machine",
        cascade="all, delete-orphan",
    )
    alerts = relationship(
        "Alert",
        back_populates="machine",
        cascade="all, delete-orphan",
    )

"""Maintenance task ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class MaintenanceTask(Base):
    __tablename__ = "maintenance_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    machine_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("machines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_type: Mapped[str] = mapped_column(String(80), nullable=False)
    priority: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    scheduled_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    machine = relationship("Machine", back_populates="maintenance_tasks")

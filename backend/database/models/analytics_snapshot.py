"""Analytics KPI snapshot ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from .base import Base


class AnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    throughput: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    utilization: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    downtime: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    mtbf: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    mttr: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    oee: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    bottleneck_machine: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
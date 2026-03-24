"""Digital twin snapshot ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON
from sqlalchemy.sql import func

from .base import Base


class TwinSnapshot(Base):
    __tablename__ = "twin_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    machines: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    products: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    queues: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    maintenance: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    production_metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
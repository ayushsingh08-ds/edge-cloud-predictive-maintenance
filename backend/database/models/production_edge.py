"""Production edge ORM model."""

from sqlalchemy import Float, ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ProductionEdge(Base):
    __tablename__ = "production_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    from_node_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("production_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_node_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("production_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    distance: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    travel_time: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    capacity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    waypoints: Mapped[list[dict]] = mapped_column(JSON, nullable=True, default=list)
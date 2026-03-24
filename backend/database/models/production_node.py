"""Production node ORM model."""

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ProductionNode(Base):
    __tablename__ = "production_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    node_name: Mapped[str] = mapped_column(String(120), nullable=False)
    node_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    machine_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("machines.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    position_x: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    position_y: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
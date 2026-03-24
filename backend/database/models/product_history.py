"""Product movement history ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ProductHistory(Base):
    __tablename__ = "product_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[str] = mapped_column(
        String(80),
        ForeignKey("sim_products.product_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("production_nodes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
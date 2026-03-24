"""Production route ORM model."""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    route_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    start_node_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("production_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    end_node_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("production_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
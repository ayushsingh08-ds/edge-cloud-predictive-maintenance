"""Machine connection ORM model."""

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class MachineConnection(Base):
    __tablename__ = "machine_connections"
    __table_args__ = (
        UniqueConstraint("from_machine_id", "to_machine_id", name="uq_machine_connection"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    from_machine_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("machines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_machine_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("machines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

"""Initialize PostgreSQL schema for predictive maintenance backend."""

from database.db_session import engine
from database.models.base import Base
from database.models import (
    alert,
    analytics_snapshot,
    machine,
    machine_connection,
    machine_health,
    machine_queue,
    maintenance_task,
    product_history,
    production_edge,
    production_node,
    route,
    rul_prediction,
    sim_product,
    telemetry,
    twin_snapshot,
)


def init_db() -> None:
    """Create all tables declared in ORM models."""
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")

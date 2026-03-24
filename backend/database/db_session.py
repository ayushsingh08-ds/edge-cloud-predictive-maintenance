"""Database session and engine configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL or "postgresql://user:password@" in DATABASE_URL:
    sqlite_path = Path(__file__).resolve().parents[1] / "data" / "smart_factory_dev.db"
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    DATABASE_URL = f"sqlite:///{sqlite_path.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = scoped_session(
    sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        future=True,
    )
)


def get_db():
    """Yield a SQLAlchemy session and ensure it is closed afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

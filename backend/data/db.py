from __future__ import annotations

import logging
from datetime import datetime
from threading import Lock
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session

from .models import Base


from pathlib import Path

class Database:
    def __init__(self, database_url: str | None = None):
        if database_url is None:
            project_root = Path(__file__).resolve().parents[1]
            db_path = project_root / "data" / "smart_factory.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            database_url = f"sqlite:///{db_path}"
        self.engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},  # For SQLite
        )
        self.SessionFactory = sessionmaker(bind=self.engine)
        self._lock = Lock()
        self._initialize()

    def _initialize(self):
        Base.metadata.create_all(self.engine)

    def session(self) -> Session:
        return self.SessionFactory()


# Global DB instance
db = Database()

"""Shared FastAPI dependencies for API routes."""

from __future__ import annotations

from typing import Generator

from database.db_session import SessionLocal


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from __future__ import annotations

from fastapi import FastAPI

from config.config import get_settings
from config.logging_setup import configure_logging

logger = configure_logging()
settings = get_settings()

app = FastAPI(title="Smart Factory Digital Twin")


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.on_event("startup")
def on_startup() -> None:
    logger.info(
        "Application startup complete on %s:%s",
        settings.api_host,
        settings.api_port,
    )

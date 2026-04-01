"""WebSocket message schemas for live dashboard streaming."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class DashboardOperationEvent(BaseModel):
    event_type: Literal[
        "operation_routed",
        "operation_started",
        "operation_interrupted",
        "operation_completed",
        "job_rerouted",
        "machine_failed",
        "machine_repaired",
        "stream_started",
        "stream_completed",
        "stream_error",
        "heartbeat",
    ]
    simulation_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = Field(default_factory=dict)


class DashboardSimulationState(BaseModel):
    simulation_id: str
    status: Literal["queued", "running", "completed", "failed"]
    sim_time_hours: float = 0.0
    duration_hours: float = 0.0
    events_emitted: int = 0
    latest_event_type: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RunAndStreamRequest(BaseModel):
    policy: str
    duration_hours: float = Field(default=8.0, gt=0)
    num_machines: int = Field(default=3, ge=1, le=20)
    arrival_rate: float = Field(default=6.0, gt=0)
    enable_failures: bool = True
    random_seed: int | None = None
    stream_tick_hours: float = Field(default=0.1, gt=0, le=1.0)


class RunAndStreamResponse(BaseModel):
    simulation_id: str
    status: Literal["queued", "running"]
    ws_endpoint: str
    message: str

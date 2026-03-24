"""Telemetry event definitions."""

from __future__ import annotations

from dataclasses import dataclass

from events.base_event import BaseEvent


@dataclass
class TelemetryRaw(BaseEvent):
    event_name = "telemetry.raw"

    machine_id: str
    temperature: float
    vibration: float
    pressure: float
    rpm: float


@dataclass
class TelemetryCleaned(BaseEvent):
    event_name = "telemetry.cleaned"

    machine_id: str
    temperature: float
    vibration: float
    pressure: float
    rpm: float

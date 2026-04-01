"""Run-and-stream simulation endpoint for real-time dashboard updates."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, cast

from fastapi import APIRouter, HTTPException

from api.dashboard_models import RunAndStreamRequest, RunAndStreamResponse
from api.websocket import simulation_ws_hub
from services.edge.publisher import EventPublisher
from services.simulation.engine import FactoryConfig, FactorySimulation, SchedulingPolicy


router = APIRouter()
_active_tasks: dict[str, asyncio.Task[Any]] = {}
_stream_event_publisher = EventPublisher(routing_key="simulation.stream")


async def _run_simulation_stream(simulation_id: str, request: RunAndStreamRequest) -> None:
    try:
        policy = SchedulingPolicy[request.policy.upper()]
    except KeyError as exc:
        error_payload = {
            "event_type": "stream_error",
            "simulation_id": simulation_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {"error": f"Unsupported policy: {request.policy}"},
        }
        await simulation_ws_hub.broadcast(
            simulation_id,
            error_payload,
        )
        _stream_event_publisher.publish(
            {"simulation_id": simulation_id, "error": f"Unsupported policy: {request.policy}"},
            event_type="stream_error",
            routing_key="simulation.stream_error",
        )
        raise ValueError(f"Unsupported policy: {request.policy}") from exc

    config = FactoryConfig(
        num_machines=request.num_machines,
        arrival_rate_per_hour=request.arrival_rate,
        enable_failures=request.enable_failures,
        scheduling_policy=policy,
        random_seed=request.random_seed or 42,
    )

    sim = FactorySimulation(config)
    sim_runtime = cast(Any, sim)
    sim_runtime.env.process(sim_runtime.job_arrivals())
    sim_runtime.env.process(sim_runtime.operation_dispatcher())
    for machine in sim_runtime.machines:
        worker = sim_runtime.env.process(sim_runtime.machine_worker(machine))
        sim_runtime.worker_processes[machine.machine_id] = worker
        if config.enable_failures:
            sim_runtime.env.process(sim_runtime.machine_failure_process(machine))
            sim_runtime.env.process(sim_runtime.preventive_maintenance_process(machine))

    started_payload = {
        "event_type": "stream_started",
        "simulation_id": simulation_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "status": "running",
            "duration_hours": request.duration_hours,
            "policy": request.policy,
        },
    }
    await simulation_ws_hub.broadcast(simulation_id, started_payload)
    _stream_event_publisher.publish(
        started_payload,
        event_type="stream_started",
        routing_key="simulation.stream_started",
    )

    next_event_index = 0
    while sim_runtime.env.now < request.duration_hours:
        step_to = min(sim_runtime.env.now + request.stream_tick_hours, request.duration_hours)
        sim_runtime.env.run(until=step_to)

        new_events = sim_runtime.event_log[next_event_index:]
        next_event_index = len(sim_runtime.event_log)

        for event in new_events:
            if event.get("event") in {
                "operation_routed",
                "operation_started",
                "operation_interrupted",
                "operation_completed",
                "job_rerouted",
                "machine_failed",
                "machine_repaired",
            }:
                event_type = str(event.get("event"))
                stream_event = {
                    "event_type": event_type,
                    "simulation_id": simulation_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "payload": event,
                }
                await simulation_ws_hub.broadcast(simulation_id, stream_event)
                _stream_event_publisher.publish(
                    {"simulation_id": simulation_id, **event},
                    event_type=event_type,
                    routing_key=f"simulation.{event_type}",
                )

        await asyncio.sleep(0)

    summary = sim_runtime.summary()
    completed_payload = {
        "event_type": "stream_completed",
        "simulation_id": simulation_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "status": "completed",
            "summary": summary,
            "events_emitted": next_event_index,
        },
    }
    await simulation_ws_hub.broadcast(simulation_id, completed_payload)
    _stream_event_publisher.publish(
        completed_payload,
        event_type="stream_completed",
        routing_key="simulation.stream_completed",
    )


@router.post("/run-and-stream", response_model=RunAndStreamResponse)
async def run_and_stream(request: RunAndStreamRequest) -> RunAndStreamResponse:
    simulation_id = str(uuid4())[:8]

    if simulation_id in _active_tasks and not _active_tasks[simulation_id].done():
        raise HTTPException(status_code=409, detail="Simulation stream already active")

    task = asyncio.create_task(_run_simulation_stream(simulation_id, request))
    _active_tasks[simulation_id] = task

    return RunAndStreamResponse(
        simulation_id=simulation_id,
        status="queued",
        ws_endpoint=f"/ws/simulation/{simulation_id}",
        message="Simulation started. Connect websocket endpoint for live operation events.",
    )


@router.get("/stream-status/{simulation_id}")
async def stream_status(simulation_id: str) -> dict[str, Any]:
    task = _active_tasks.get(simulation_id)
    state = simulation_ws_hub.get_state(simulation_id)
    return {
        "simulation_id": simulation_id,
        "active": bool(task and not task.done()),
        "state": state,
    }


__all__ = ["router"]

"""WebSocket hub for per-simulation live event streaming."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, cast
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.routes import simulation as simulation_routes


router = APIRouter()
simulation_routes_any = cast(Any, simulation_routes)


class SimulationWebSocketHub:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._state: dict[str, dict[str, Any]] = {}

    async def connect(self, simulation_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[simulation_id].add(websocket)

    def disconnect(self, simulation_id: str, websocket: WebSocket) -> None:
        if simulation_id in self._connections and websocket in self._connections[simulation_id]:
            self._connections[simulation_id].remove(websocket)
            if not self._connections[simulation_id]:
                self._connections.pop(simulation_id, None)

    async def broadcast(self, simulation_id: str, payload: dict[str, Any]) -> None:
        self._state[simulation_id] = payload
        dead: list[WebSocket] = []
        for socket in self._connections.get(simulation_id, set()):
            try:
                await socket.send_json(payload)
            except Exception:
                dead.append(socket)

        for socket in dead:
            self.disconnect(simulation_id, socket)

    def get_state(self, simulation_id: str) -> dict[str, Any] | None:
        return self._state.get(simulation_id)


simulation_ws_hub = SimulationWebSocketHub()


@router.websocket("/events")
async def stream_dashboard_events(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            simulations = cast(
                dict[str, dict[str, Any]],
                simulation_routes_any.list_completed_simulations(),
            )
            latest_sim_id = next(reversed(simulations), None) if simulations else None
            latest_sim = simulations.get(latest_sim_id) if latest_sim_id else None
            await websocket.send_json(
                {
                    "event_type": "dashboard_snapshot",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "completed_simulations": len(simulations),
                    "latest_simulation": latest_sim["simulation_id"] if latest_sim else None,
                }
            )
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return


@router.websocket("/events/{simulation_id}")
async def stream_simulation_events(websocket: WebSocket, simulation_id: str) -> None:
    await websocket.accept()
    try:
        while True:
            simulation = cast(
                dict[str, Any] | None,
                simulation_routes_any.get_completed_simulation(simulation_id),
            )
            await websocket.send_json(
                {
                    "event_type": "simulation_snapshot",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "simulation_id": simulation_id,
                    "status": "completed" if simulation else "not_found",
                    "events": simulation.get("events", [])[-20:] if simulation else [],
                }
            )
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return


@router.websocket("/simulation/{simulation_id}")
async def simulation_socket(websocket: WebSocket, simulation_id: str) -> None:
    await simulation_ws_hub.connect(simulation_id, websocket)
    try:
        cached = simulation_ws_hub.get_state(simulation_id)
        if cached is not None:
            await websocket.send_json(cached)
        else:
            await websocket.send_json(
                {
                    "event_type": "heartbeat",
                    "simulation_id": simulation_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "payload": {"status": "waiting_for_stream"},
                }
            )

        # Keep socket alive and support ping messages from clients.
        while True:
            _ = await websocket.receive_text()
            await websocket.send_json(
                {
                    "event_type": "heartbeat",
                    "simulation_id": simulation_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "payload": {"status": "connected"},
                }
            )
    except WebSocketDisconnect:
        simulation_ws_hub.disconnect(simulation_id, websocket)

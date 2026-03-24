"""WebSocket connection manager for real-time dashboard streaming."""

from __future__ import annotations

import asyncio

from fastapi import WebSocket


class ConnectionManager:
    """Manage active websocket clients and broadcast JSON events."""

    def __init__(self) -> None:
        self._active_connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._active_connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._active_connections.discard(websocket)

    async def send_personal_message(self, message: dict | str, websocket: WebSocket) -> None:
        if isinstance(message, dict):
            await websocket.send_json(message)
        else:
            await websocket.send_text(str(message))

    async def broadcast(self, message: dict | str) -> None:
        async with self._lock:
            targets = list(self._active_connections)

        stale_connections: list[WebSocket] = []
        for connection in targets:
            try:
                if isinstance(message, dict):
                    await connection.send_json(message)
                else:
                    await connection.send_text(str(message))
            except Exception:
                stale_connections.append(connection)

        if stale_connections:
            async with self._lock:
                for connection in stale_connections:
                    self._active_connections.discard(connection)

    async def get_connected_clients(self) -> int:
        async with self._lock:
            return len(self._active_connections)

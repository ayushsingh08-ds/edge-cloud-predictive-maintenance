"""WebSocket server endpoint for real-time Smart Factory event streaming."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.websocket.connection_manager import ConnectionManager
from api.websocket.event_listener import RabbitMQEventListener


router = APIRouter(tags=["websocket"])
manager = ConnectionManager()
listener = RabbitMQEventListener(manager)


@router.on_event("startup")
async def startup_event_listener() -> None:
    loop = asyncio.get_running_loop()
    listener.start(loop)


@router.on_event("shutdown")
async def shutdown_event_listener() -> None:
    listener.stop()


@router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket) -> None:
    await manager.connect(websocket)

    await manager.send_personal_message(
        {
            "event": "ws.connected",
            "data": {"message": "Connected to Smart Factory real-time stream"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        websocket,
    )

    heartbeat_task = asyncio.create_task(_heartbeat(websocket))

    try:
        while True:
            # Keep the connection alive and allow optional client pings/commands.
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        await manager.disconnect(websocket)
    finally:
        heartbeat_task.cancel()


async def _heartbeat(websocket: WebSocket) -> None:
    try:
        while True:
            await asyncio.sleep(20)
            await manager.send_personal_message(
                {
                    "event": "heartbeat",
                    "data": {"connected": True},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                websocket,
            )
    except Exception:
        pass

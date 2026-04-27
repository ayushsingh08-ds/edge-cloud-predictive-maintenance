import asyncio
import json
import websockets

async def check_ws():
    uri = "ws://127.0.0.1:8005/ws/events"
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to WebSocket")
            for _ in range(20):
                message = await websocket.recv()
                data = json.loads(message)
                print(f"Received event: {data.get('event_type')}")
                if data.get('event_type') == "BULK_UPDATE":
                    events = data.get('payload', [])
                    for ev in events:
                        print(f"  - {ev.get('event_type')}")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(check_ws())

"""FastAPI API Gateway for Smart Factory backend services."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import alerts, analytics, machines, maintenance, production, twin
from api.websocket import router as websocket_router


app = FastAPI(
    title="Smart Factory API Gateway",
    description="REST gateway for Flutter dashboard and factory backend services",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(machines.router)
app.include_router(maintenance.router)
app.include_router(production.router)
app.include_router(twin.router)
app.include_router(analytics.router)
app.include_router(alerts.router)
app.include_router(websocket_router)


@app.get("/", tags=["root"])
def root() -> dict:
    return {
        "service": "smart-factory-api-gateway",
        "status": "ok",
        "message": "Smart Factory API Gateway is running",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.app:app", host="0.0.0.0", port=8000, reload=True)

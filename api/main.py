"""
FastAPI Backend for Edge-Cloud Predictive Maintenance System
============================================================

Serves REST API endpoints for the frontend dashboard to:
- Query real-time machine status
- Run simulations with different policies
- Train and evaluate RL agents
- Fetch anomalies and alerts
- Get performance metrics
- Configure system parameters
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json
from pathlib import Path
from datetime import datetime
import logging

from api.routes import machines, jobs, anomalies, simulation, rl_training, analytics, operations, routing, streaming
from api import websocket
from config.config import get_settings
from db.database import init_db
from services.integration import RabbitMQEventConsumers

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
event_consumers = RabbitMQEventConsumers()

# Create FastAPI app
app = FastAPI(
    title="Predictive Maintenance API",
    description="REST API for edge-cloud predictive maintenance system",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(machines.router, prefix="/api/machines", tags=["Machines"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(anomalies.router, prefix="/api/anomalies", tags=["Anomalies"])
app.include_router(simulation.router, prefix="/api/simulation", tags=["Simulation"])
app.include_router(rl_training.router, prefix="/api/rl-training", tags=["RL Training"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(operations.router, prefix="/api/operations", tags=["Operations"])
app.include_router(routing.router, prefix="/api/routing", tags=["Routing"])
app.include_router(streaming.router, prefix="/api/streaming", tags=["Streaming"])
app.include_router(websocket.router, prefix="/ws", tags=["WebSocket"])


@app.on_event("startup")
async def on_startup() -> None:
    init_db()
    settings = get_settings()
    if settings.use_rabbitmq and settings.enable_event_consumers:
        event_consumers.start()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    event_consumers.stop()


# Health check endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
    }


@app.get("/api/status")
async def api_status():
    """Get overall system status."""
    return {
        "system_status": "operational",
        "timestamp": datetime.now().isoformat(),
        "event_consumers": event_consumers.status(),
        "services": {
            "machines": "healthy",
            "simulation": "ready",
            "rl_training": "ready",
            "anomaly_detection": "ready",
        },
    }


@app.get("/api/config")
async def get_system_config():
    """Get current system configuration."""
    # Load from simulation config
    from services.simulation.engine import FactoryConfig
    
    config = FactoryConfig()
    return {
        "factory": {
            "num_machines": config.num_machines,
            "arrival_rate_per_hour": config.arrival_rate_per_hour,
            "mean_processing_time_hours": config.mean_processing_time_hours,
            "enable_failures": config.enable_failures,
        },
        "scheduler": {
            "health_w1": config.health_w1,
            "health_w2": config.health_w2,
            "health_w3": config.health_w3,
            "health_w4": config.health_w4,
        },
    }


@app.get("/")
async def root():
    """Root endpoint - API information."""
    return {
        "name": "Edge-Cloud Predictive Maintenance API",
        "version": "1.0.0",
        "docs": "/api/docs",
        "endpoints": {
            "machines": "/api/machines",
            "jobs": "/api/jobs",
            "anomalies": "/api/anomalies",
            "simulation": "/api/simulation",
            "rl_training": "/api/rl-training",
            "analytics": "/api/analytics",
            "operations": "/api/operations",
            "routing": "/api/routing",
            "streaming": "/api/streaming",
            "ws": "/ws",
        },
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.schemas.dependencies import get_db
from services.simulation.simulation_manager import simulation_manager

router = APIRouter(prefix="/simulation", tags=["simulation"])

@router.post("/start")
async def start_simulation(db: Session = Depends(get_db)) -> dict:
    """Starts the digital twin simulation, launching sensor streams for all machines."""
    await simulation_manager.start_simulation(db)
    return {"status": "success", "message": "Simulation started", "running": True}

@router.post("/stop")
async def stop_simulation() -> dict:
    """Stops the digital twin simulation and halts all sensor streams."""
    await simulation_manager.stop_simulation()
    return {"status": "success", "message": "Simulation stopped", "running": False}

@router.get("/status")
def get_status() -> dict:
    """Retrieves the current execution status of the simulation."""
    return {"running": simulation_manager.is_running}

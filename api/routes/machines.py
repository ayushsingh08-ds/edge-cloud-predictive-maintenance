"""
Machine endpoints - Get machine status, health, sensors, maintenance info
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List
from datetime import datetime
import logging

from api.models import MachineStatus, MachineDetailResponse, MachineHealth, SensorReading
from services.edge.sensor_stream import SensorRecord

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=List[MachineStatus])
async def list_machines():
    """
    Get list of all machines with current status.
    
    Returns:
        List of machines with their current state, health, and sensor readings.
    """
    try:
        # Create mock machines data (for frontend demo)
        machines_list = []
        
        for machine_id in range(3):
            health_index = max(0.05, 0.85 - (machine_id * 0.15))
            
            machine_status = MachineStatus(
                machine_id=machine_id,
                name=f"Machine-{machine_id}",
                state=["busy", "idle", "idle"][machine_id],
                queue_length=5 - machine_id,
                health=MachineHealth(
                    health_index=health_index,
                    rul_hours=max(0, 500 - machine_id * 100),
                    failure_count=machine_id,
                    repair_count=0,
                ),
                latest_sensors=SensorReading(
                    temperature=50 + (machine_id * 5),
                    vibration=30 + (machine_id * 10),
                    pressure=100 - machine_id * 2,
                    timestamp=datetime.now(),
                ),
                utilization=0.65 - (machine_id * 0.1),
                downtime_hours=4.5 + (machine_id * 0.5),
            )
            machines_list.append(machine_status)
        
        return machines_list
    
    except Exception as e:
        logger.error(f"Error listing machines: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{machine_id}", response_model=MachineDetailResponse)
async def get_machine_detail(machine_id: int):
    """
    Get detailed information about a specific machine.
    
    Args:
        machine_id: Machine ID (0-indexed)
    
    Returns:
        Detailed machine information including health, sensors, and history.
    """
    try:
        if machine_id >= 3:
            raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")
        
        health_index = max(0.05, 0.85 - (machine_id * 0.15))
        
        machine_status = MachineStatus(
            machine_id=machine_id,
            name=f"Machine-{machine_id}",
            state=["busy", "idle", "idle"][machine_id],
            queue_length=5 - machine_id,
            health=MachineHealth(
                health_index=health_index,
                rul_hours=max(0, 500 - machine_id * 100),
                failure_count=machine_id,
                repair_count=0,
            ),
            latest_sensors=SensorReading(
                temperature=50 + (machine_id * 5),
                vibration=30 + (machine_id * 10),
                pressure=100 - machine_id * 2,
                timestamp=datetime.now(),
            ),
            utilization=0.65 - (machine_id * 0.1),
            downtime_hours=4.5 + (machine_id * 0.5),
        )
        
        return MachineDetailResponse(
            machine=machine_status,
            busy_time_hours=15.5,
            failure_statistics={
                "total_failures": machine_id,
                "failures_per_day": machine_id / 1.0,
                "mean_time_between_failures": 500 / (machine_id + 1),
                "average_repair_time": 2.0,
            },
            repair_times=[2.0, 1.5, 2.5],
            maintenance_history=[
                {
                    "timestamp": datetime.now().isoformat(),
                    "type": "repair",
                    "duration_hours": 2.0,
                    "cost": 500.0,
                }
            ],
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting machine detail: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{machine_id}/health")
async def get_machine_health(machine_id: int):
    """
    Get current health metrics for a machine.
    
    Args:
        machine_id: Machine ID
    
    Returns:
        Health index, RUL, failure count.
    """
    try:
        if machine_id >= 3:
            raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")
        
        health_index = max(0.05, 0.85 - (machine_id * 0.15))
        
        return {
            "machine_id": machine_id,
            "health_index": health_index,
            "rul_hours": max(0, 500 - machine_id * 100),
            "failure_count": machine_id,
            "utilization": 0.65 - (machine_id * 0.1),
            "status": "healthy" if health_index > 0.7 else "degraded" if health_index > 0.3 else "critical",
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting machine health: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{machine_id}/sensors")
async def get_machine_sensors(machine_id: int):
    """
    Get latest sensor readings from a machine.
    
    Args:
        machine_id: Machine ID
    
    Returns:
        Current temperature, vibration, pressure readings.
    """
    try:
        if machine_id >= 3:
            raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")
        
        return {
            "machine_id": machine_id,
            "timestamp": datetime.now().isoformat(),
            "sensors": {
                "temperature": 50 + (machine_id * 5) + (5 if machine_id == 0 else 0),
                "vibration": 30 + (machine_id * 10),
                "pressure": 100 - machine_id * 2,
            },
            "status": "normal",
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting machine sensors: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]

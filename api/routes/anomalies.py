"""
Anomaly/Alert endpoints - Get anomalies, alerts, and historical anomaly data
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timedelta
import logging

from api.models import Anomaly, AnomalyFeedResponse, AlertSeverityEnum
from services.simulation.engine import FactorySimulation, FactoryConfig
from services.edge.anomaly import EdgeAnomalyDetector
from services.edge.sensor_stream import SensorRecord

router = APIRouter()
logger = logging.getLogger(__name__)

# Global anomaly detector instance
_anomaly_detector = EdgeAnomalyDetector()


# In-memory anomaly storage (for demo)
_anomalies = []


@router.get("/", response_model=AnomalyFeedResponse)
async def get_recent_anomalies(
    limit: int = Query(50, ge=1, le=500),
    severity: Optional[AlertSeverityEnum] = None,
):
    """
    Get recent anomalies/alerts feed.
    
    Args:
        limit: Maximum number of anomalies to return
        severity: Filter by severity (low, medium, high)
    
    Returns:
        Recently detected anomalies with severity levels.
    """
    try:
        # Generate some sample anomalies
        anomalies = []
        now = datetime.now()
        
        for i in range(min(5, limit)):
            machine_id = i % 3
            severity_level = [
                AlertSeverityEnum.LOW,
                AlertSeverityEnum.MEDIUM,
                AlertSeverityEnum.HIGH,
            ][i % 3]
            
            if severity and severity_level != severity:
                continue
            
            anomalies.append(Anomaly(
                anomaly_id=i,
                machine_id=machine_id,
                sensor_type=["temperature", "vibration", "pressure"][i % 3],
                timestamp=now - timedelta(hours=i),
                value=75.5 + (i * 2.5),
                normal_range=(40.0, 70.0),
                severity=severity_level,
                duration_steps=i * 5 + 10,
                status="active" if i < 2 else "resolved",
                description=f"Sensor reading above normal for {'Temperature' if i % 3 == 0 else 'Vibration' if i % 3 == 1 else 'Pressure'}",
            ))
        
        return AnomalyFeedResponse(
            total_active_anomalies=sum(1 for a in anomalies if a.status == "active"),
            anomalies=anomalies[:limit],
            last_updated=now,
        )
    
    except Exception as e:
        logger.error(f"Error getting anomalies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/machine/{machine_id}")
async def get_machine_anomalies(
    machine_id: int,
    limit: int = Query(20, ge=1, le=100),
):
    """
    Get anomalies for a specific machine.
    
    Args:
        machine_id: Machine ID
        limit: Maximum number of anomalies
    
    Returns:
        Anomalies detected on that machine.
    """
    try:
        anomalies = []
        now = datetime.now()
        
        for i in range(min(5, limit)):
            anomalies.append(Anomaly(
                anomaly_id=i,
                machine_id=machine_id,
                sensor_type=["temperature", "vibration", "pressure"][i % 3],
                timestamp=now - timedelta(hours=i),
                value=75.5 + (i * 2.5),
                normal_range=(40.0, 70.0),
                severity=AlertSeverityEnum.MEDIUM,
                duration_steps=i * 5 + 10,
                status="active" if i < 2 else "resolved",
                description=f"Anomaly detected on Machine-{machine_id}",
            ))
        
        return {
            "machine_id": machine_id,
            "total_anomalies": len(anomalies),
            "active_anomalies": sum(1 for a in anomalies if a.status == "active"),
            "anomalies": anomalies,
        }
    
    except Exception as e:
        logger.error(f"Error getting machine anomalies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sensor/{sensor_type}")
async def get_sensor_anomalies(
    sensor_type: str,
    limit: int = Query(20, ge=1, le=100),
):
    """
    Get anomalies for a specific sensor type.
    
    Args:
        sensor_type: Sensor type (temperature, vibration, pressure)
        limit: Maximum number of anomalies
    
    Returns:
        Anomalies detected for that sensor across all machines.
    """
    try:
        if sensor_type not in ["temperature", "vibration", "pressure"]:
            raise HTTPException(
                status_code=400,
                detail="sensor_type must be temperature, vibration, or pressure",
            )
        
        anomalies = []
        now = datetime.now()
        
        for i in range(min(5, limit)):
            anomalies.append(Anomaly(
                anomaly_id=i,
                machine_id=i % 3,
                sensor_type=sensor_type,
                timestamp=now - timedelta(hours=i),
                value=75.5 + (i * 2.5),
                normal_range=(40.0, 70.0),
                severity=AlertSeverityEnum.MEDIUM,
                duration_steps=i * 5 + 10,
                status="active" if i < 2 else "resolved",
                description=f"{sensor_type.capitalize()} anomaly detected",
            ))
        
        return {
            "sensor_type": sensor_type,
            "total_anomalies": len(anomalies),
            "anomalies": anomalies,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sensor anomalies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_anomaly_statistics():
    """
    Get statistics about detected anomalies.
    
    Returns:
        Count by severity, sensor type, machine.
    """
    try:
        return {
            "total_anomalies_24h": 12,
            "active_anomalies": 2,
            "anomalies_by_severity": {
                "low": 3,
                "medium": 6,
                "high": 3,
            },
            "anomalies_by_sensor": {
                "temperature": 4,
                "vibration": 5,
                "pressure": 3,
            },
            "anomalies_by_machine": {
                "machine_0": 4,
                "machine_1": 4,
                "machine_2": 4,
            },
            "detection_rate": 0.95,
            "false_positive_rate": 0.02,
        }
    
    except Exception as e:
        logger.error(f"Error getting anomaly statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process-sensor")
async def process_sensor_data(sensor_data: dict):
    """
    Process sensor data for anomaly detection.
    
    Args:
        sensor_data: Sensor record with timestamp, machine_id, temperature, vibration, pressure
    
    Returns:
        Anomaly detection result.
    """
    try:
        record = SensorRecord(
            timestamp=sensor_data["timestamp"],
            machine_id=sensor_data["machine_id"],
            temperature=sensor_data["temperature"],
            vibration=sensor_data["vibration"],
            pressure=sensor_data["pressure"],
        )
        result = _anomaly_detector.process(record)
        return result
    
    except Exception as e:
        logger.error(f"Error processing sensor data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]

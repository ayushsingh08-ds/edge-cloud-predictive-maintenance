from pydantic import BaseModel
from typing import List, Literal
from datetime import datetime

# Base Event
class BaseEvent(BaseModel):
    event_type: str
    version: str = "1.0"
    timestamp: datetime
    machine_id: str

# 1️. Sensor Telemetry Event

class SensorEvent(BaseEvent):
    event_type: Literal["sensor_reading"]
    sensor_id: str

    # Core measurements
    temperature: float
    vibration: float
    pressure: float
    rotation_speed: float

    # Operating context
    load: float
    ambient_temperature: float
    operating_mode: str

# 2. Anomaly Event 

class AnomalyEvent(BaseEvent):
    event_type: Literal["anomaly_detected"]
    sensor_id: str

    anomaly_score: float
    is_anomaly: bool
    triggered_features: List[str]
    severity: Literal["low", "medium", "high"]

# 3. RUL Prediction Event 

class RULEvent(BaseEvent):
    event_type: Literal["rul_prediction"]

    predicted_hours_remaining: float
    confidence: float
    health_status: Literal["healthy", "warning", "critical"]


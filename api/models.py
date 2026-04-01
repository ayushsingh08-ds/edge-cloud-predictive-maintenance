"""
Pydantic models for API request/response schemas
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class SchedulingPolicyEnum(str, Enum):
    """Scheduling policy options."""
    RANDOM = "random"
    SPT = "spt"
    QUEUE_BASED = "queue_based"
    HEALTH_AWARE = "health_aware"
    RL = "rl"


class AlertSeverityEnum(str, Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ============================================================================
# Machine Models
# ============================================================================

class SensorReading(BaseModel):
    """Single sensor reading."""
    temperature: float = Field(..., description="Temperature in Celsius")
    vibration: float = Field(..., description="Vibration level (0-100)")
    pressure: float = Field(..., description="Pressure in PSI")
    timestamp: datetime = Field(default_factory=datetime.now)


class MachineHealth(BaseModel):
    """Machine health status."""
    health_index: float = Field(..., ge=0, le=1, description="Health from 0 (dead) to 1 (perfect)")
    rul_hours: float = Field(..., description="Remaining useful life in hours")
    failure_count: int = Field(..., description="Total failure count")
    repair_count: int = Field(..., description="Total repair count")
    last_failure_timestamp: Optional[datetime] = None
    last_repair_timestamp: Optional[datetime] = None


class MachineStatus(BaseModel):
    """Current machine status."""
    machine_id: int
    name: str
    state: str = Field(..., description="busy, idle, or failed")
    current_job_id: Optional[int] = None
    queue_length: int
    health: MachineHealth
    latest_sensors: SensorReading
    utilization: float = Field(..., ge=0, le=1, description="Utilization %")
    downtime_hours: float


class MachineDetailResponse(BaseModel):
    """Detailed machine information."""
    machine: MachineStatus
    busy_time_hours: float
    failure_statistics: Dict[str, Any]
    repair_times: List[float]
    maintenance_history: List[Dict[str, Any]]


# ============================================================================
# Job Models
# ============================================================================

class JobStatus(BaseModel):
    """Job status and details."""
    job_id: int
    arrival_time: datetime
    due_date: datetime
    processing_time_hours: float
    assigned_machine: Optional[int] = None
    start_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None
    status: str = Field(..., description="waiting, processing, or completed")
    tardiness_hours: Optional[float] = None


class JobQueueResponse(BaseModel):
    """Job queue status."""
    total_jobs_waiting: int
    total_jobs_processing: int
    total_jobs_completed: int
    queue: List[JobStatus]
    average_wait_time: float


# ============================================================================
# Anomaly Models
# ============================================================================

class Anomaly(BaseModel):
    """Anomaly/Alert record."""
    anomaly_id: int
    machine_id: int
    sensor_type: str = Field(..., description="temperature, vibration, or pressure")
    timestamp: datetime
    value: float
    normal_range: tuple[float, float] = Field(..., description="(min, max)")
    severity: AlertSeverityEnum = AlertSeverityEnum.MEDIUM
    duration_steps: int = 0
    status: str = Field(..., description="active or resolved")
    description: str


class AnomalyFeedResponse(BaseModel):
    """Recent anomalies feed."""
    total_active_anomalies: int
    anomalies: List[Anomaly]
    last_updated: datetime


# ============================================================================
# Simulation Models
# ============================================================================

class SimulationParams(BaseModel):
    """Parameters for running a simulation."""
    policy: SchedulingPolicyEnum
    duration_hours: float = Field(..., ge=0.1, le=168, description="1 minute to 1 week")
    num_machines: int = Field(default=3, ge=1, le=10)
    arrival_rate: float = Field(default=6.0, ge=0.1, le=20)
    enable_failures: bool = True
    random_seed: Optional[int] = None


class SimulationMetrics(BaseModel):
    """Results from a simulation."""
    policy: str
    duration_hours: float
    jobs_completed: int
    jobs_failed: int
    average_tardiness_hours: float
    total_downtime_hours: float
    total_failures: int
    utilization: float = Field(..., ge=0, le=1)
    throughput_jobs_per_hour: float
    average_wait_time: float


class SimulationResponse(BaseModel):
    """Complete simulation result."""
    simulation_id: str
    timestamp: datetime
    parameters: SimulationParams
    metrics: SimulationMetrics


class PolicyComparisonResponse(BaseModel):
    """Comparison of multiple policies."""
    comparison_id: str
    timestamp: datetime
    results: Dict[str, SimulationMetrics]  # policy_name -> metrics


# ============================================================================
# RL Training Models
# ============================================================================

class PPOHyperparamsRequest(BaseModel):
    """Hyperparameters for PPO training."""
    learning_rate: float = Field(default=3e-4, ge=1e-5, le=0.1)
    n_steps: int = Field(default=2048, ge=512, le=8192)
    batch_size: int = Field(default=64, ge=32, le=256)
    n_epochs: int = Field(default=20, ge=5, le=50)
    gamma: float = Field(default=0.99, ge=0.9, le=0.999)
    gae_lambda: float = Field(default=0.95, ge=0.9, le=0.99)
    clip_range: float = Field(default=0.2, ge=0.1, le=0.5)
    ent_coef: float = Field(default=0.01, ge=0, le=0.1)


class RLTrainingParams(BaseModel):
    """Parameters for starting RL training."""
    total_timesteps: int = Field(default=50000, ge=10000, le=500000)
    num_parallel_envs: int = Field(default=4, ge=1, le=8)
    eval_interval: int = Field(default=5000, ge=1000, le=50000)
    hyperparams: Optional[PPOHyperparamsRequest] = None
    name: Optional[str] = Field(default=None, description="Name for this training session")


class RLTrainingProgress(BaseModel):
    """Training progress information."""
    training_id: str
    status: str = Field(..., description="running, completed, or failed")
    total_timesteps: int
    completed_timesteps: int
    progress_percent: float
    current_reward: Optional[float] = None
    best_reward: Optional[float] = None
    estimated_time_remaining_seconds: float
    start_time: datetime
    last_update: datetime


class ModelEvaluationResult(BaseModel):
    """Results from evaluating a trained model."""
    model_name: str
    num_episodes: int
    mean_episode_reward: float
    std_episode_reward: float
    mean_episode_length: float
    mean_tardiness_hours: float
    mean_downtime_hours: float
    mean_throughput: float


class RLModelInfo(BaseModel):
    """Information about a trained RL model."""
    model_id: str
    name: str
    created_at: datetime
    timesteps: int
    file_size_kb: float
    eval_results: Optional[ModelEvaluationResult] = None


# ============================================================================
# Analytics Models
# ============================================================================

class PerformanceMetrics(BaseModel):
    """Overall performance metrics."""
    timestamp: datetime
    utilization: float = Field(..., ge=0, le=1)
    throughput_jobs_per_hour: float
    average_tardiness_hours: float
    total_downtime_hours: float
    failure_rate: float
    maintenance_cost: float


class MetricsHistory(BaseModel):
    """Historical metrics data."""
    metrics_type: str = Field(..., description="hourly, daily, or custom")
    data_points: List[PerformanceMetrics]
    trend: str = Field(..., description="improving, stable, or degrading")


class SystemReport(BaseModel):
    """Comprehensive system report."""
    report_id: str
    timestamp: datetime
    summary: Dict[str, Any]
    metrics: PerformanceMetrics
    alerts: List[Anomaly]
    recommendations: List[str]


# ============================================================================
# Configuration Models
# ============================================================================

class HealthAwareWeightsRequest(BaseModel):
    """Weight parameters for health-aware scheduler."""
    w1: float = Field(default=0.35, ge=0, le=1, description="Processing time weight")
    w2: float = Field(default=0.30, ge=0, le=1, description="Health weight")
    w3: float = Field(default=0.20, ge=0, le=1, description="Queue length weight")
    w4: float = Field(default=0.15, ge=0, le=1, description="Urgency weight")


class FactoryConfigRequest(BaseModel):
    """Factory configuration."""
    num_machines: int = Field(default=3, ge=1, le=20)
    arrival_rate_per_hour: float = Field(default=6.0, ge=0.1, le=50)
    mean_processing_time_hours: float = Field(default=0.5, ge=0.1, le=10)
    enable_failures: bool = True
    failure_rate: float = Field(default=0.05, ge=0, le=0.5)


# ============================================================================
# Flexible Routing Models
# ============================================================================

class OperationSchema(BaseModel):
    """Operation definition for flexible job-shop jobs."""
    op_id: int
    candidate_machines: List[int] = Field(..., min_length=1)
    processing_time: float = Field(..., gt=0)
    sequence_type: str = Field(default="serial", description="serial, parallel, or flexible")
    completed: bool = False
    status: str = Field(default="pending", description="pending, ready, in_progress, completed, interrupted")
    assigned_machine: Optional[int] = None
    start_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None
    reroute_count: int = 0


class JobSubmissionSchema(BaseModel):
    """Request model to submit a multi-operation job."""
    job_id: int
    arrival_time: datetime
    due_date: datetime
    operations: List[OperationSchema] = Field(..., min_length=1)
    sequencing_mode: str = Field(default="serial", description="serial, parallel, or flexible")


class RoutingEventSchema(BaseModel):
    """Operation-to-machine routing event payload."""
    time: float
    event: str = Field(default="job_routed")
    job_id: int
    operation: int
    machine_id: int
    from_machine_id: Optional[int] = None
    to_machine_id: Optional[int] = None
    candidate_machines: List[int] = Field(default_factory=list)
    policy: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class JobDetailWithOperations(BaseModel):
    """Detailed job model with operation-level tracking."""
    job_id: int
    arrival_time: datetime
    due_date: datetime
    status: str
    current_operation_index: int
    operations: List[OperationSchema]
    start_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None
    rerouting_history: List[RoutingEventSchema] = Field(default_factory=list)


class DashboardStreamEvent(BaseModel):
    """Schema for websocket event payloads consumed by the dashboard."""
    event_type: str
    timestamp: datetime
    simulation_id: Optional[str] = None
    status: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    events: List[Dict[str, Any]] = Field(default_factory=list)


# ============================================================================
# Error Models
# ============================================================================

class ErrorResponse(BaseModel):
    """Error response format."""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


__all__ = [
    "SchedulingPolicyEnum",
    "AlertSeverityEnum",
    "SensorReading",
    "MachineHealth",
    "MachineStatus",
    "MachineDetailResponse",
    "JobStatus",
    "JobQueueResponse",
    "Anomaly",
    "AnomalyFeedResponse",
    "SimulationParams",
    "SimulationMetrics",
    "SimulationResponse",
    "PolicyComparisonResponse",
    "PPOHyperparamsRequest",
    "RLTrainingParams",
    "RLTrainingProgress",
    "ModelEvaluationResult",
    "RLModelInfo",
    "PerformanceMetrics",
    "MetricsHistory",
    "SystemReport",
    "HealthAwareWeightsRequest",
    "FactoryConfigRequest",
    "OperationSchema",
    "JobSubmissionSchema",
    "RoutingEventSchema",
    "JobDetailWithOperations",
    "ErrorResponse",
]

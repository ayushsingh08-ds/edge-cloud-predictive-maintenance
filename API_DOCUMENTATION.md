# 🚀 FastAPI Backend - Edge-Cloud Predictive Maintenance System

## Overview

This is a **production-ready REST API** built with **FastAPI** and **Uvicorn** that exposes all the capabilities of the Edge-Cloud Predictive Maintenance System to a frontend application.

The API provides:

- ✅ Real-time machine status monitoring
- ✅ Job queue management
- ✅ Anomaly detection alerts
- ✅ Simulation runs with different policies
- ✅ RL agent training and evaluation
- ✅ Analytics and performance metrics
- ✅ Event-driven domain messages over RabbitMQ topics for decoupled consumers
- ✅ Interactive API documentation (Swagger UI)

---

## 🎯 Quick Start

### Installation

```bash
# Install FastAPI and Uvicorn
pip install fastapi uvicorn

# Alternatively, install from requirements file
pip install -r requirements.txt
```

### Running the Server

```bash
# Development mode (with hot reload)
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Access the API

- **Base URL**: `http://localhost:8000`
- **Swagger UI**: `http://localhost:8000/api/docs`
- **ReDoc**: `http://localhost:8000/api/redoc`
- **Health Check**: `http://localhost:8000/health`

---

## 📚 API Endpoints

### 1. **Machines** - Real-time Machine Status

```
GET  /api/machines/                    # List all machines
GET  /api/machines/{machine_id}        # Get detailed machine info
GET  /api/machines/{machine_id}/health # Get health metrics
GET  /api/machines/{machine_id}/sensors # Get sensor readings
```

**Example Response** (`GET /api/machines/`):

```json
[
  {
    "machine_id": 0,
    "name": "Machine-0",
    "state": "busy",
    "queue_length": 5,
    "health": {
      "health_index": 0.85,
      "rul_hours": 500,
      "failure_count": 0
    },
    "latest_sensors": {
      "temperature": 50.0,
      "vibration": 30.0,
      "pressure": 100.0
    },
    "utilization": 0.65,
    "downtime_hours": 4.5
  }
]
```

### 2. **Jobs** - Job Queue Management

```
GET  /api/jobs/queue                   # Get job queue status
GET  /api/jobs/{job_id}                # Get specific job status
GET  /api/jobs/completed/recent        # Get recently completed jobs
GET  /api/jobs/statistics              # Get job processing statistics
```

**Example Response** (`GET /api/jobs/queue`):

```json
{
  "total_jobs_waiting": 12,
  "total_jobs_processing": 3,
  "total_jobs_completed": 87,
  "queue": [
    {
      "job_id": 100,
      "processing_time_hours": 0.5,
      "status": "waiting"
    }
  ],
  "average_wait_time": 30.0
}
```

### 3. **Anomalies** - Alert & Anomaly Management

```
GET  /api/anomalies/                          # Get recent anomalies
GET  /api/anomalies/machine/{machine_id}     # Get machine-specific anomalies
GET  /api/anomalies/sensor/{sensor_type}     # Get sensor-type anomalies
GET  /api/anomalies/statistics               # Get anomaly statistics
POST /api/anomalies/{anomaly_id}/acknowledge # Mark anomaly as acknowledged
```

**Example Response** (`GET /api/anomalies/`):

```json
{
  "total_active_anomalies": 2,
  "anomalies": [
    {
      "anomaly_id": 0,
      "machine_id": 0,
      "sensor_type": "temperature",
      "severity": "high",
      "value": 75.5,
      "normal_range": [40.0, 70.0],
      "status": "active"
    }
  ],
  "last_updated": "2026-04-01T15:30:00Z"
}
```

### 4. **Simulation** - Policy Comparison & Testing

```
POST /api/simulation/run               # Run simulation with specific policy
GET  /api/simulation/{simulation_id}   # Get simulation results
POST /api/simulation/compare-policies  # Compare multiple policies
GET  /api/simulation/history/recent    # Get recent simulations
```

**Request Body** (`POST /api/simulation/run`):

```json
{
  "policy": "health_aware",
  "duration_hours": 8.0,
  "num_machines": 3,
  "arrival_rate": 6.0,
  "enable_failures": true
}
```

**Example Response**:

```json
{
  "simulation_id": "abc12345",
  "status": "completed",
  "parameters": {...},
  "metrics": {
    "policy": "health_aware",
    "jobs_completed": 42,
    "average_tardiness_hours": 0.05,
    "throughput_jobs_per_hour": 5.9
  }
}
```

Simulation streams are also emitted as live domain events over WebSocket and RabbitMQ topic routing keys such as `simulation.operation_started`, `simulation.operation_completed`, and `simulation.stream_completed`.

Job and machine projections can be consumed asynchronously by enabling background RabbitMQ consumers in the API process:

- `ENABLE_EVENT_CONSUMERS=true`
- Job queue bindings: `simulation.operation_routed`, `simulation.operation_started`, `simulation.operation_interrupted`, `simulation.operation_completed`, `simulation.job_rerouted`
- Machine queue bindings: `simulation.machine_failed`, `simulation.machine_repaired`, `simulation.operation_started`, `simulation.operation_completed`

When enabled, consumer runtime state is exposed via `GET /api/status` under `event_consumers`.

### 5. **RL Training** - Model Training & Evaluation

```
POST /api/rl-training/start                    # Start training session
GET  /api/rl-training/{training_id}/status    # Get training progress
POST /api/rl-training/{training_id}/stop      # Stop training
GET  /api/rl-training/models/list             # List trained models
POST /api/rl-training/{model_id}/evaluate     # Evaluate model
POST /api/rl-training/compare-with-baselines  # Compare with baselines
GET  /api/rl-training/training-histories/recent # Get recent sessions
```

**Request Body** (`POST /api/rl-training/start`):

```json
{
  "total_timesteps": 50000,
  "num_parallel_envs": 4,
  "eval_interval": 5000,
  "name": "Training-v1",
  "hyperparams": {
    "learning_rate": 0.0003,
    "gamma": 0.99,
    "clip_range": 0.2
  }
}
```

### 6. **Analytics** - Metrics, Reports & Forecasting

```
GET  /api/analytics/metrics/current        # Get current KPI metrics
GET  /api/analytics/metrics/history        # Get historical metrics
GET  /api/analytics/kpi/dashboard          # Get dashboard KPIs
GET  /api/analytics/report/system          # Generate system report
GET  /api/analytics/comparison/policies    # Policy comparison analysis
GET  /api/analytics/forecast/rul           # RUL forecasts for machines
```

**Example Response** (`GET /api/analytics/metrics/current`):

```json
{
  "timestamp": "2026-04-01T15:30:00Z",
  "utilization": 0.65,
  "throughput_jobs_per_hour": 5.9,
  "average_tardiness_hours": 0.05,
  "total_downtime_hours": 4.5,
  "failure_rate": 0.015,
  "on_time_percentage": 97.5
}
```

---

## 🏗️ Project Structure

```
api/
├── main.py                    # FastAPI app initialization, CORS setup
├── models.py                  # Pydantic schemas & request/response models
└── routes/
    ├── machines.py            # Machine monitoring endpoints
    ├── jobs.py               # Job queue management endpoints
    ├── anomalies.py          # Anomaly detection endpoints
    ├── simulation.py         # Simulation & policy comparison endpoints
    ├── rl_training.py        # RL training & evaluation endpoints
    └── analytics.py          # Metrics, reports, forecasting endpoints
```

---

## 📊 Data Models

### Machine Status

```python
{
  "machine_id": int,
  "name": str,
  "state": str,  # "busy", "idle", "failed"
  "queue_length": int,
  "health": {
    "health_index": float,      # 0-1 scale
    "rul_hours": float,         # Remaining useful life
    "failure_count": int,
    "repair_count": int
  },
  "latest_sensors": {
    "temperature": float,
    "vibration": float,
    "pressure": float,
    "timestamp": datetime
  },
  "utilization": float,         # 0-1 scale
  "downtime_hours": float
}
```

### Job Status

```python
{
  "job_id": int,
  "arrival_time": datetime,
  "due_date": datetime,
  "processing_time_hours": float,
  "assigned_machine": Optional[int],
  "status": str,               # "waiting", "processing", "completed"
  "tardiness_hours": Optional[float]
}
```

### Anomaly Alert

```python
{
  "anomaly_id": int,
  "machine_id": int,
  "sensor_type": str,          # "temperature", "vibration", "pressure"
  "timestamp": datetime,
  "value": float,
  "normal_range": [float, float],
  "severity": str,             # "low", "medium", "high"
  "duration_steps": int,
  "status": str                # "active", "resolved"
}
```

---

## 🔐 Authentication & Security

Currently, the API has **no authentication** (open for development). For production:

1. **Enable HTTPS** - Use SSL certificates
2. **Add JWT authentication** - Implement token-based auth
3. **API Keys** - Use API key headers for client authentication
4. **Rate Limiting** - Use `slowapi` for rate limiting
5. **CORS** - Configure allowed origins

```python
# Example: Add JWT middleware
from fastapi_jwt_auth import AuthJWT

@app.post("/login")
async def login(credentials: LoginCredentials, Authorize: AuthJWT = Depends()):
    # Validate credentials
    access_token = Authorize.create_access_token(subject=user_id)
    return {"access_token": access_token}

@app.get("/protected")
async def protected_route(Authorize: AuthJWT = Depends()):
    Authorize.jwt_required()
    return {"message": "This is protected"}
```

---

## 🚀 Deployment

### Docker Deployment

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
# Build and run
docker build -t predictive-maint-api .
docker run -p 8000:8000 predictive-maint-api
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: predictive-maint-api
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: api
          image: predictive-maint-api:latest
          ports:
            - containerPort: 8000
          env:
            - name: WORKERS
              value: "4"
```

### Cloud Platforms

**AWS Lambda**:

```bash
# Use Mangum for ASGI to Lambda adapter
pip install mangum
# Then deploy with AWS SAM or Serverless Framework
```

**Google Cloud Run**:

```bash
gcloud run deploy predictive-maint-api --source . --platform managed
```

**Azure App Service**:

```bash
# Deploy with Azure CLI
az webapp up --name predictive-maint-api --resource-group myResourceGroup
```

---

## 📈 Performance & Monitoring

### Response Metrics

- **Machines endpoint**: ~10-50ms
- **Analytics endpoint**: ~50-200ms
- **Simulation endpoint**: 5-10 seconds (depends on duration)
- **RL Training**: Minutes (depends on timesteps)

### Logging

```python
# Enabled by default in uvicorn
# To increase verbosity:
python -m uvicorn api.main:app --log-level debug
```

### Health Monitoring

```bash
# Health check endpoint
curl http://localhost:8000/health

# Returns:
{
  "status": "ok",
  "version": "1.0.0",
  "timestamp": "2026-04-01T15:30:00Z"
}
```

---

## 🔧 Development

### Adding a New Endpoint

1. **Create route file** (`api/routes/my_feature.py`):

```python
from fastapi import APIRouter
from api.models import MyModel

router = APIRouter()

@router.get("/endpoint")
async def my_endpoint():
    return {"data": "value"}
```

2. **Import in main.py**:

```python
from api.routes import my_feature

app.include_router(
    my_feature.router,
    prefix="/api/my-feature",
    tags=["My Feature"]
)
```

### Testing

```bash
# Run with pytest
pip install pytest pytest-asyncio

# Test a specific endpoint
pytest tests/test_machines.py -v

# Test coverage
pytest --cov=api tests/

# Integration testing with httpx
from httpx import AsyncClient
from api.main import app

async def test_machines():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/machines/")
        assert response.status_code == 200
```

---

## 📖 API Documentation

Auto-generated interactive docs available at:

- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **OpenAPI JSON**: http://localhost:8000/api/openapi.json

---

## ⚡ Next Steps for Frontend Integration

### 1. Install Frontend Dependencies

```bash
npm install axios  # or your preferred HTTP client
```

### 2. Create API Client

```javascript
const API_BASE = "http://localhost:8000/api";

const fetchMachines = async () => {
  const response = await fetch(`${API_BASE}/machines/`);
  return response.json();
};

const runSimulation = async (params) => {
  const response = await fetch(`${API_BASE}/simulation/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return response.json();
};
```

### 3. Error Handling

```javascript
try {
  const data = await fetchMachines();
} catch (error) {
  console.error("API Error:", error.message);
  // Handle 500 Internal Server Error
  // Handle 404 Not Found
  // Handle 422 Validation Error
}
```

### 4. Real-time Updates (WebSocket)

```python
# Coming soon: Add WebSocket support for real-time updates
from fastapi import WebSocket

@app.websocket("/ws/machines/{machine_id}")
async def websocket_machine(websocket: WebSocket, machine_id: int):
    await websocket.accept()
    while True:
        data = await get_machine_data(machine_id)
        await websocket.send_json(data)
```

For decoupled consumers, the same operational events are also published to the RabbitMQ exchange `predictive_maintenance.events`, so downstream services can subscribe without coupling to the FastAPI request lifecycle.

---

## 🧠 Models, Algorithms, and Metrics

This section explains exactly what intelligence is currently running in the backend, and how to interpret reported metrics.

### Scheduling Algorithms in Production

The simulator supports the following scheduling policies:

- `RANDOM`: Randomly selects a machine from the operation candidate set.
- `SPT` (Shortest Processing Time proxy): Scores candidates using queue workload, queue length, and processing-time preference.
- `QUEUE_BASED`: Picks the least occupied candidate queue.
- `HEALTH_AWARE`: Uses weighted scoring across machine health, queue length, processing time, and due-date urgency.

These policies are used during simulation and policy-comparison endpoints.

### Reinforcement Learning Model

- **Algorithm**: PPO (Proximal Policy Optimization)
- **Library**: `stable-baselines3`
- **Policy network**: `MlpPolicy`
- **Environment**: Gymnasium wrapper over factory simulation
- **Action**: Select candidate machine index for current operation
- **Observation**: Queue lengths, machine health, operation candidate mask, urgency, operation index, elapsed time, utilization
- **Reward**: Multi-objective penalty combining tardiness and downtime deltas

### Routing and Operations Analytics

Routing analytics are computed from simulation/job histories:

- **Routing efficiency**:

  $$
  	ext{efficiency} = \frac{\text{direct operations}}{\max(\text{actual hops}, 1)}
  $$

- **Routing success rate**:

  $$
  1 - \frac{\text{affected jobs (rerouted)}}{\max(\text{jobs}, 1)}
  $$

- **Rerouting delay proxy**:

  $$
  	ext{avg delay} = \frac{\text{total reroutes} \times 0.05}{\max(\text{jobs}, 1)}
  $$

- **Bottleneck operations**: Top operations by reroute count.

### Metrics You Can Trust as Measured Outputs

These are produced from simulation runs and RL evaluation episodes:

- Throughput (`throughput_jobs_per_hour`)
- Utilization (`utilization`)
- Average tardiness (`avg_tardiness_hours`)
- Total downtime (`downtime_hours`)
- Failure count (`failures`)
- Jobs completed (`jobs_completed`)
- RL episode reward (`episode_reward`)
- Routing metrics (efficiency, reroutes, bottlenecks)

### Metrics Currently Placeholder / Demo Values

Some endpoint fields are currently synthetic/demo and should not be treated as final model-validation numbers:

- `detection_rate` and `false_positive_rate` in anomaly statistics
- Some training progress values in RL status endpoints (progress is time-based simulation)
- Some historical analytics trend points are generated sample series

### Accuracy, Precision, Recall, F1, AUC Status

At present, there is **no fully wired supervised anomaly-classification pipeline** exposing true classification metrics such as:

- Accuracy
- Precision
- Recall
- F1-score
- ROC-AUC

For the current RL + operations optimization stack, preferred success criteria are:

- Lower tardiness
- Lower downtime
- Higher throughput
- Higher utilization
- Better routing efficiency and fewer reroutes

### Recommended Benchmark Reporting (for frontend)

For each policy/model, display at least:

- Mean and standard deviation over multiple episodes/runs
- Throughput, tardiness, downtime, failures, utilization
- Relative improvement vs baseline policy (`RANDOM` or `QUEUE_BASED`)

Example improvement formula:

$$
	ext{improvement\%} = \frac{\text{baseline} - \text{candidate}}{\max(|\text{baseline}|, \epsilon)} \times 100
$$

Use this with "lower is better" metrics (tardiness, downtime). For "higher is better" metrics (throughput, utilization), invert numerator accordingly.

---

## 📝 Requirements

```txt
fastapi==0.135.2
uvicorn==0.42.0
pydantic==2.12.5
stable-baselines3==2.3.2
gymnasium==0.29.1
lightgbm>=4.0.0
scikit-learn>=1.3.0
pandas>=2.0.0
numpy>=1.24.0
```

---

**Status**: ✅ **OPERATIONAL**  
**Version**: 1.0.0  
**Last Updated**: April 1, 2026

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

## 📱 Flutter Frontend Integration

This section provides comprehensive guidance for integrating the FastAPI backend with a Flutter frontend application.

### 1. **Setup Flutter Dependencies**

Add the following to your `pubspec.yaml`:

```yaml
dependencies:
  flutter:
    sdk: flutter
  http: ^1.2.0 # HTTP client for REST API calls
  web_socket_channel: ^2.4.0 # WebSocket support for real-time updates
  provider: ^6.0.0 # State management (optional)
  json_annotation: ^4.8.0 # JSON serialization
  json_serializable: ^6.6.0 # Code generation for JSON
  intl: ^0.19.0 # Date/time formatting

dev_dependencies:
  build_runner: ^2.4.0 # Code generation
  json_serializable: ^6.6.0
```

### 2. **API Client Setup**

Create an API client class for centralized API communication:

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';

class ApiClient {
  static const String baseUrl = 'http://localhost:8000';
  static const String wsBaseUrl = 'ws://localhost:8000';

  // HTTP Client
  final http.Client _client = http.Client();

  // WebSocket Channels
  WebSocketChannel? _dashboardChannel;
  WebSocketChannel? _simulationChannel;

  // Headers for authenticated requests (add JWT if needed)
  Map<String, String> get _headers => {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    // 'Authorization': 'Bearer $token', // Add if using JWT
  };

  // Dispose resources
  void dispose() {
    _dashboardChannel?.sink.close();
    _simulationChannel?.sink.close();
    _client.close();
  }
}
```

### 3. **REST API Integration**

#### Machines API

```dart
class MachineService extends ApiClient {
  Future<List<Machine>> getMachines() async {
    try {
      final response = await _client.get(
        Uri.parse('$baseUrl/api/machines/'),
        headers: _headers,
      );

      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        return data.map((json) => Machine.fromJson(json)).toList();
      } else {
        throw Exception('Failed to load machines: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Network error: $e');
    }
  }

  Future<Machine> getMachine(int machineId) async {
    final response = await _client.get(
      Uri.parse('$baseUrl/api/machines/$machineId'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      return Machine.fromJson(json.decode(response.body));
    } else {
      throw Exception('Failed to load machine');
    }
  }
}
```

#### Jobs API

```dart
class JobService extends ApiClient {
  Future<JobQueueResponse> getJobQueue() async {
    final response = await _client.get(
      Uri.parse('$baseUrl/api/jobs/queue'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      return JobQueueResponse.fromJson(json.decode(response.body));
    } else {
      throw Exception('Failed to load job queue');
    }
  }

  Future<JobStatus> getJobStatus(int jobId) async {
    final response = await _client.get(
      Uri.parse('$baseUrl/api/jobs/$jobId'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      return JobStatus.fromJson(json.decode(response.body));
    } else {
      throw Exception('Failed to load job status');
    }
  }
}
```

#### Simulation API

```dart
class SimulationService extends ApiClient {
  Future<SimulationResponse> runSimulation(SimulationParams params) async {
    final response = await _client.post(
      Uri.parse('$baseUrl/api/simulation/run'),
      headers: _headers,
      body: json.encode(params.toJson()),
    );

    if (response.statusCode == 200) {
      return SimulationResponse.fromJson(json.decode(response.body));
    } else {
      throw Exception('Failed to run simulation');
    }
  }

  Future<SimulationResult> getSimulationResult(String simulationId) async {
    final response = await _client.get(
      Uri.parse('$baseUrl/api/simulation/$simulationId'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      return SimulationResult.fromJson(json.decode(response.body));
    } else {
      throw Exception('Failed to load simulation result');
    }
  }
}
```

### 4. **WebSocket Real-Time Updates**

#### Dashboard Live Updates

```dart
class WebSocketService extends ApiClient {
  Stream<Map<String, dynamic>> getDashboardStream() {
    _dashboardChannel = WebSocketChannel.connect(
      Uri.parse('$wsBaseUrl/ws/events'),
    );

    return _dashboardChannel!.stream.map((message) {
      return json.decode(message as String) as Map<String, dynamic>;
    });
  }

  Stream<Map<String, dynamic>> getSimulationStream(String simulationId) {
    _simulationChannel = WebSocketChannel.connect(
      Uri.parse('$wsBaseUrl/ws/simulation/$simulationId'),
    );

    return _simulationChannel!.stream.map((message) {
      return json.decode(message as String) as Map<String, dynamic>;
    });
  }
}
```

#### Usage in Flutter Widget

```dart
class DashboardScreen extends StatefulWidget {
  @override
  _DashboardScreenState createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final WebSocketService _wsService = WebSocketService();
  StreamSubscription? _subscription;
  Map<String, dynamic>? _latestData;

  @override
  void initState() {
    super.initState();
    _connectToDashboard();
  }

  void _connectToDashboard() {
    _subscription = _wsService.getDashboardStream().listen(
      (data) {
        setState(() {
          _latestData = data;
        });
      },
      onError: (error) {
        print('WebSocket error: $error');
        // Handle reconnection logic
      },
      onDone: () {
        print('WebSocket connection closed');
      },
    );
  }

  @override
  void dispose() {
    _subscription?.cancel();
    _wsService.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Dashboard')),
      body: _latestData != null
          ? Column(
              children: [
                Text('Completed Simulations: ${_latestData!['completed_simulations']}'),
                Text('Latest Simulation: ${_latestData!['latest_simulation']}'),
              ],
            )
          : CircularProgressIndicator(),
    );
  }
}
```

### 5. **Data Models (Dart Classes)**

Create data classes for JSON serialization:

```dart
// machine.dart
import 'package:json_annotation/json_annotation.dart';

part 'machine.g.dart';

@JsonSerializable()
class Machine {
  final int machineId;
  final String name;
  final String state;
  final int queueLength;
  final MachineHealth health;
  final Map<String, dynamic> latestSensors;
  final double utilization;
  final double downtimeHours;

  Machine({
    required this.machineId,
    required this.name,
    required this.state,
    required this.queueLength,
    required this.health,
    required this.latestSensors,
    required this.utilization,
    required this.downtimeHours,
  });

  factory Machine.fromJson(Map<String, dynamic> json) => _$MachineFromJson(json);
  Map<String, dynamic> toJson() => _$MachineToJson(this);
}

@JsonSerializable()
class MachineHealth {
  final double healthIndex;
  final double rulHours;
  final int failureCount;

  MachineHealth({
    required this.healthIndex,
    required this.rulHours,
    required this.failureCount,
  });

  factory MachineHealth.fromJson(Map<String, dynamic> json) => _$MachineHealthFromJson(json);
  Map<String, dynamic> toJson() => _$MachineHealthToJson(this);
}
```

```dart
// simulation.dart
import 'package:json_annotation/json_annotation.dart';

part 'simulation.g.dart';

@JsonSerializable()
class SimulationParams {
  final String policy;
  final double durationHours;
  final int numMachines;
  final double arrivalRate;
  final bool enableFailures;
  final int? randomSeed;

  SimulationParams({
    required this.policy,
    this.durationHours = 8.0,
    this.numMachines = 3,
    this.arrivalRate = 6.0,
    this.enableFailures = true,
    this.randomSeed,
  });

  factory SimulationParams.fromJson(Map<String, dynamic> json) => _$SimulationParamsFromJson(json);
  Map<String, dynamic> toJson() => _$SimulationParamsToJson(this);
}

@JsonSerializable()
class SimulationResponse {
  final String simulationId;
  final String status;
  final Map<String, dynamic> parameters;
  final Map<String, dynamic> metrics;

  SimulationResponse({
    required this.simulationId,
    required this.status,
    required this.parameters,
    required this.metrics,
  });

  factory SimulationResponse.fromJson(Map<String, dynamic> json) => _$SimulationResponseFromJson(json);
  Map<String, dynamic> toJson() => _$SimulationResponseToJson(this);
}
```

### 6. **State Management with Provider**

```dart
// app_state.dart
import 'package:flutter/foundation.dart';

class AppState extends ChangeNotifier {
  List<Machine> _machines = [];
  JobQueueResponse? _jobQueue;
  Map<String, dynamic>? _dashboardData;

  List<Machine> get machines => _machines;
  JobQueueResponse? get jobQueue => _jobQueue;
  Map<String, dynamic>? get dashboardData => _dashboardData;

  void updateMachines(List<Machine> machines) {
    _machines = machines;
    notifyListeners();
  }

  void updateJobQueue(JobQueueResponse queue) {
    _jobQueue = queue;
    notifyListeners();
  }

  void updateDashboardData(Map<String, dynamic> data) {
    _dashboardData = data;
    notifyListeners();
  }
}
```

### 7. **Error Handling & Retry Logic**

```dart
class ApiException implements Exception {
  final String message;
  final int? statusCode;

  ApiException(this.message, {this.statusCode});

  @override
  String toString() => 'ApiException: $message (Status: $statusCode)';
}

class RetryHelper {
  static Future<T> retry<T>(
    Future<T> Function() function, {
    int maxRetries = 3,
    Duration delay = const Duration(seconds: 1),
  }) async {
    int attempts = 0;
    while (attempts < maxRetries) {
      try {
        return await function();
      } catch (e) {
        attempts++;
        if (attempts >= maxRetries) rethrow;
        await Future.delayed(delay * attempts);
      }
    }
    throw Exception('Max retries exceeded');
  }
}
```

### 8. **Complete Flutter App Example**

```dart
// main.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'services/api_client.dart';
import 'screens/dashboard_screen.dart';

void main() {
  runApp(MyApp());
}

class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AppState()),
        Provider(create: (_) => ApiClient()),
      ],
      child: MaterialApp(
        title: 'Predictive Maintenance',
        theme: ThemeData(primarySwatch: Colors.blue),
        home: DashboardScreen(),
      ),
    );
  }
}
```

### 9. **Testing API Integration**

```dart
// test/api_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:mockito/mockito.dart';

class MockClient extends Mock implements http.Client {}

void main() {
  group('API Integration Tests', () {
    test('should fetch machines successfully', () async {
      final mockClient = MockClient();
      final machineService = MachineService(client: mockClient);

      when(mockClient.get(any, headers: anyNamed('headers')))
          .thenAnswer((_) async => http.Response('[]', 200));

      final machines = await machineService.getMachines();
      expect(machines, isEmpty);
    });
  });
}
```

### 10. **Deployment Considerations**

#### CORS Configuration

The backend already includes CORS configuration for Flutter development. For production:

```python
# In api/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-flutter-web-domain.com",
        "com.yourcompany.app",  # iOS
        "com.yourcompany.app",  # Android
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### Environment Variables

Create environment configurations for different deployments:

```dart
// config.dart
class Config {
  static const String apiUrl = String.fromEnvironment(
    'API_URL',
    defaultValue: 'http://localhost:8000',
  );

  static const String wsUrl = String.fromEnvironment(
    'WS_URL',
    defaultValue: 'ws://localhost:8000',
  );
}
```

#### Build Commands

```bash
# Android APK
flutter build apk --release

# iOS (on macOS)
flutter build ios --release

# Web
flutter build web --release
```

---

## 📱 Flutter Integration Summary

✅ **HTTP Client**: Use `http` package for REST API calls  
✅ **WebSocket**: Use `web_socket_channel` for real-time updates  
✅ **State Management**: Provider/Bloc for app state  
✅ **JSON Serialization**: `json_serializable` for type safety  
✅ **Error Handling**: Custom exceptions with retry logic  
✅ **Testing**: Unit tests for API services  
✅ **Deployment**: CORS, environment configs, build optimization

The Flutter frontend can now seamlessly integrate with the FastAPI backend for a complete predictive maintenance dashboard experience.

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

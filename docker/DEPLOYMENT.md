# Smart Factory Backend - Docker Deployment Guide

This guide covers deploying the Smart Factory Digital Twin backend system using Docker and Docker Compose.

## Prerequisites

- Docker Desktop (Windows/Mac) or Docker Engine (Linux)
- Docker Compose v1.29+
- At least 4GB RAM available for Docker
- Ports 5432, 5672, 8000, 8001, 15672 available

## Directory Structure

```
docker/
├── Dockerfile.backend          # Backend microservices container
├── Dockerfile.api              # FastAPI API Gateway container
├── Dockerfile.websocket        # WebSocket server container
├── docker-compose.yml          # Orchestration configuration
├── entrypoint-backend.sh       # Backend service startup script
├── entrypoint-api.sh           # API Gateway startup script
├── entrypoint-websocket.sh     # WebSocket server startup script
├── .env.docker                 # Environment variables
├── .dockerignore                # Docker build ignore patterns
└── DEPLOYMENT.md               # This file
```

## Quick Start

### 1. Clone Repository

```bash
cd edge-cloud-predictive-maintenance
```

### 2. Build Images

```bash
docker-compose -f docker/docker-compose.yml build
```

### 3. Start All Services

```bash
docker-compose -f docker/docker-compose.yml up -d
```

This will start:

- PostgreSQL database
- RabbitMQ message broker
- All backend microservices
- FastAPI API Gateway
- WebSocket server
- pgAdmin for database management

### 4. Verify Services are Running

```bash
docker-compose -f docker/docker-compose.yml ps
```

Check health with:

```bash
docker-compose -f docker/docker-compose.yml logs -f api
```

### 5. Stop All Services

```bash
docker-compose -f docker/docker-compose.yml down
```

To also remove volumes:

```bash
docker-compose -f docker/docker-compose.yml down -v
```

## Services & Ports

| Service       | Port  | URL                    | Purpose                   |
| ------------- | ----- | ---------------------- | ------------------------- |
| FastAPI       | 8000  | http://localhost:8000  | REST API endpoints        |
| WebSocket     | 8001  | ws://localhost:8001/ws | Real-time events          |
| PostgreSQL    | 5432  | localhost:5432         | Database                  |
| RabbitMQ AMQP | 5672  | localhost:5672         | Message broker            |
| RabbitMQ UI   | 15672 | http://localhost:15672 | Message broker management |
| pgAdmin       | 5050  | http://localhost:5050  | Database admin UI         |

## Frontend Connection

### REST API Endpoints

```
http://localhost:8000/machines           # List all machines
http://localhost:8000/machines/{id}      # Get machine details
http://localhost:8000/machines/{id}/health
http://localhost:8000/maintenance        # Maintenance tasks
http://localhost:8000/production/status  # Production metrics
http://localhost:8000/alerts             # Active alerts
http://localhost:8000/twin/state         # Digital twin state
http://localhost:8000/analytics/kpi      # Analytics KPIs
```

### WebSocket Connection

```javascript
// JavaScript/Flutter
const ws = new WebSocket("ws://localhost:8001/ws/events");

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log("Event:", message.event);
  console.log("Data:", message.data);
};
```

### Expected Events

- `machine.health.updated` - Machine health score changes
- `product.moved` - Product moves between nodes
- `alert.created` - New alert generated
- `maintenance.scheduled` - Maintenance scheduled
- `twin.state.updated` - Digital twin state changes
- `production.metrics.updated` - Production metrics update

## Database Management

### Access pgAdmin

1. Open http://localhost:5050
2. Login with:
   - Email: `admin@example.com`
   - Password: `admin`
3. Add new server:
   - Host: `postgres`
   - Port: `5432`
   - Maintenance DB: `smart_factory`
   - Username: `user`
   - Password: `password`

### Direct PostgreSQL Connection

```bash
psql -h localhost -U user -d smart_factory
```

## RabbitMQ Management

### Access RabbitMQ Management UI

1. Open http://localhost:15672
2. Login with:
   - Username: `admin`
   - Password: `admin123`

### Topics

- `sensor_exchange` - Topic exchange for all sensor/system events
- Topics include: `sensor.raw`, `sensor.cleaned`, `edge.anomaly`, `maintenance.alert`, `product.*`, `machine.*`, `twin.*`, `analytics.*`

## Environment Configuration

### Default Environment Variables

File: `docker/.env.docker`

```
DATABASE_URL=postgresql://user:password@postgres:5432/smart_factory
RABBITMQ_HOST=rabbitmq
RABBITMQ_USER=admin
RABBITMQ_PASS=admin123
API_HOST=0.0.0.0
API_PORT=8000
SENSOR_MODE=normal
```

### Customize Environment

1. Edit `docker/.env.docker`
2. Rebuild images:
   ```bash
   docker-compose -f docker/docker-compose.yml build --no-cache
   ```
3. Restart services:
   ```bash
   docker-compose -f docker/docker-compose.yml up -d
   ```

## Backend Services

### Alert Manager

- Listens for maintenance alerts
- Creates alert records
- Publishes alert events

### Decision Engine

- Processes anomalies
- Decides maintenance actions
- Routes decisions

### Anomaly Detector

- Analyzes sensor data
- Detects anomalies in real-time
- Publishes anomaly events

### Data Adapter

- Adapts data from various sources
- Cleans and normalizes data
- Prepares for further processing

### RUL Predictor

- Predicts Remaining Useful Life
- Processes historical data
- Updates RUL estimates

### Sensor Simulator

- Generates synthetic sensor data
- Simulates normal/degrading/failing modes
- Feeds data into the pipeline

## Deployment Patterns

### Development Mode

```bash
# Run with live logs
docker-compose -f docker/docker-compose.yml up
```

### Production Mode

```bash
# Run in detached mode
docker-compose -f docker/docker-compose.yml up -d

# Check status
docker-compose -f docker/docker-compose.yml ps

# View logs
docker-compose -f docker/docker-compose.yml logs -f api
```

### Scaling Services

For multiple instances of a service:

```bash
# Scale sensor simulator to 3 instances
docker-compose -f docker/docker-compose.yml up -d --scale sensor_simulator=3
```

## Troubleshooting

### Services Won't Start

1. Check logs:

   ```bash
   docker-compose -f docker/docker-compose.yml logs
   ```

2. Verify ports are available:

   ```bash
   netstat -an | grep LISTEN
   ```

3. Restart Docker daemon

### Database Connection Issues

1. Verify PostgreSQL is running:

   ```bash
   docker-compose -f docker/docker-compose.yml exec postgres pg_isready
   ```

2. Check database exists:
   ```bash
   docker-compose -f docker/docker-compose.yml exec postgres psql -U user -d smart_factory -c "\dt"
   ```

### RabbitMQ Connection Issues

1. Verify RabbitMQ is running:

   ```bash
   docker-compose -f docker/docker-compose.yml logs rabbitmq
   ```

2. Check AMQP connectivity:
   ```bash
   docker-compose -f docker/docker-compose.yml exec api python -c "import pika; pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))"
   ```

### API Not Responding

1. Check API logs:

   ```bash
   docker-compose -f docker/docker-compose.yml logs api
   ```

2. Test API health:

   ```bash
   curl http://localhost:8000/machines
   ```

3. Verify database schema is initialized:
   ```bash
   docker-compose -f docker/docker-compose.yml exec postgres psql -U user -d smart_factory -c "\dt"
   ```

## Performance Tuning

### Increase Memory for Services

Edit `docker-compose.yml`:

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G
```

### Database Optimization

Edit PostgreSQL environment in `docker-compose.yml`:

```yaml
postgres:
  environment:
    POSTGRES_INIT_ARGS: "-E UTF8 -c shared_buffers=256MB -c effective_cache_size=1GB"
```

### RabbitMQ Tuning

```yaml
rabbitmq:
  environment:
    RABBITMQ_CHANNEL_MAX: 2048
    RABBITMQ_CONNECTION_MAX: 0
```

## Integrating with Flutter Frontend

### Base URLs

```dart
const String API_BASE_URL = 'http://localhost:8000';
const String WS_BASE_URL = 'ws://localhost:8001';
```

### REST Client

```dart
final response = await http.get(
  Uri.parse('$API_BASE_URL/machines'),
);
```

### WebSocket Listener

```dart
final channel = IOWebSocketChannel.connect('$WS_BASE_URL/ws/events');

channel.stream.listen((message) {
  final event = jsonDecode(message);
  // Handle event
});
```

## Maintenance

### Backup Database

```bash
docker-compose -f docker/docker-compose.yml exec postgres pg_dump -U user smart_factory > backup.sql
```

### Restore Database

```bash
docker-compose -f docker/docker-compose.yml exec -T postgres psql -U user smart_factory < backup.sql
```

### View Real-time Logs

```bash
# All services
docker-compose -f docker/docker-compose.yml logs -f

# Specific service
docker-compose -f docker/docker-compose.yml logs -f api

# Last 100 lines
docker-compose -f docker/docker-compose.yml logs --tail 100 api
```

### Update Services

```bash
# Rebuild and restart
docker-compose -f docker/docker-compose.yml down
docker-compose -f docker/docker-compose.yml build --no-cache
docker-compose -f docker/docker-compose.yml up -d
```

## Next Steps

1. Deploy Docker Compose stack
2. Verify all services are healthy
3. Connect Flutter frontend to REST API and WebSocket
4. Monitor logs and metrics
5. Configure production environment variables
6. Set up backup/restore procedures
7. Configure monitoring and alerting

## Support

For issues or questions:

1. Check logs: `docker-compose logs`
2. Verify service connectivity
3. Consult troubleshooting section
4. Review backend code in `backend/` directory

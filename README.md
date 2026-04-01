# Smart Factory Digital Twin - Environment Setup

This repository is prepared as a production-style baseline for a large-scale Python project.

Scope of this setup:

- Environment setup with Python 3.10
- Dependency management with pinned requirements
- Configuration loading from `.env`
- Database and RabbitMQ connection stubs
- Centralized logging
- Import verification test
- Docker and Docker Compose stack

Out of scope for now:

- Simulation, ML, RL, API business logic, and integration implementation

## Folder Structure

```text
.
|-- services/
|   |-- simulation/
|   |-- edge/
|   |-- cloud_ai/
|   |-- scheduler/
|   `-- integration/
|-- api/
|-- database/
|   |-- __init__.py
|   |-- connection.py
|   `-- rabbitmq.py
|-- config/
|   |-- __init__.py
|   |-- config.py
|   `-- logging_setup.py
|-- models/
|-- notebooks/
|-- docker/
|-- tests/
|   `-- test_env.py
|-- logs/
|-- requirements.txt
|-- .env
|-- Dockerfile
|-- docker-compose.yml
|-- README.md
`-- main.py
```

Service folders are intentionally empty for now.

## Python Version

Use Python 3.10.

## Create Virtual Environment

### Windows (PowerShell)

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Windows (CMD)

```bat
py -3.10 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Linux/macOS

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Environment Variables

The `.env` file contains:

```dotenv
DB_HOST=localhost
DB_NAME=smart_factory
DB_USER=postgres
DB_PASS=postgres
RABBITMQ_HOST=localhost
RABBITMQ_USER=guest
RABBITMQ_PASS=guest
API_HOST=0.0.0.0
API_PORT=8000
```

## Verify Dependency Imports

```bash
python tests/test_env.py
```

## Run FastAPI Locally

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Health endpoint:

- `GET /health`

## Run Full Stack with Docker Compose

```bash
docker compose up --build
```

Services:

- FastAPI: `http://localhost:8000`
- PostgreSQL: `localhost:5432`
- RabbitMQ: `amqp://guest:guest@localhost:5672/`
- RabbitMQ Management UI: `http://localhost:15672`

## Troubleshooting Guide

### 1) Pip resolver conflicts

Symptoms:

- `ResolutionImpossible`

Fix:

- Upgrade pip, setuptools, wheel:
  - `python -m pip install --upgrade pip setuptools wheel`
- Recreate venv and reinstall dependencies.

### 2) Torch / Torch-Geometric wheel mismatch

Symptoms:

- Install fails on `torch-geometric`
- Runtime import errors for torch geometric extensions

Fix:

- Ensure Python is exactly 3.10.
- Keep the pinned `torch`, `torchvision`, `torchaudio`, and `torch-geometric` versions.
- If needed, install PyG wheels from official index matching torch version before reinstalling `torch-geometric`.

### 3) LightGBM build issues on Windows

Symptoms:

- Fails building wheel from source

Fix:

- Use the pinned version in this project (wheel available for common setups).
- Upgrade pip and retry.

### 4) psycopg2 installation issues

Symptoms:

- Compiler or `pg_config` errors

Fix:

- Use `psycopg2-binary` (already pinned) instead of source `psycopg2`.

### 5) RabbitMQ connection refused

Symptoms:

- Cannot connect to AMQP broker

Fix:

- Confirm container is healthy: `docker compose ps`
- Confirm `.env` host is `rabbitmq` inside containers and `localhost` for local runs.
- Verify port `5672` is available.

### 6) PostgreSQL authentication failures

Symptoms:

- `password authentication failed`

Fix:

- Ensure `.env` values match container credentials.
- Default compose credentials are `postgres/postgres` database `smart_factory`.

## Recommended Next Step

After environment verification passes, begin implementing domain modules in `services/` one component at a time (simulation, edge, cloud_ai, scheduler, integration).

"""Integration-style API Gateway smoke test for Smart Factory backend."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import desc, select

from api.app import app
from database.db_session import SessionLocal
from database.init_db import init_db
from database.models.machine import Machine
from database.models.machine_health import MachineHealth
from services.digital_twin import twin_repository


def print_header(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _pretty(data) -> str:
    return json.dumps(data, indent=2, default=str)


def seed_minimum_data() -> None:
    """Seed minimum records so all requested endpoints can return useful data."""
    init_db()

    db = SessionLocal()
    try:
        machine = db.scalar(select(Machine).where(Machine.id == 1))
        if machine is None:
            machine = Machine(
                id=1,
                name="Machine A",
                type="CNC",
                location="Line 1 - A",
                status="running",
            )
            db.add(machine)
            db.commit()
            db.refresh(machine)

        latest_health = db.scalar(
            select(MachineHealth)
            .where(MachineHealth.machine_id == 1)
            .order_by(desc(MachineHealth.last_updated))
            .limit(1)
        )
        if latest_health is None:
            db.add(
                MachineHealth(
                    machine_id=1,
                    health_score=0.85,
                    anomaly_score=0.15,
                    rul_hours=120.0,
                )
            )
            db.commit()

    finally:
        db.close()

    # Ensure twin state exists with expected structure.
    state = twin_repository.get_full_twin_state()
    if not state.get("machines"):
        twin_repository.store_twin_snapshot(
            {
                "machines": {
                    "1": {
                        "machine_id": 1,
                        "status": "running",
                        "health": 0.85,
                        "current_product": None,
                        "queue_length": 0,
                    }
                },
                "products": {},
                "queues": {},
                "maintenance": {},
                "production_metrics": {
                    "throughput": 10,
                    "active_machines": 1,
                    "completed_products": 5,
                    "average_processing_time": 12.5,
                },
            }
        )


def validate_response(path: str, payload) -> None:
    if path == "/machines":
        _ensure(isinstance(payload, list), "/machines must return list")
        if payload:
            _ensure("id" in payload[0], "/machines item missing id")
            _ensure("name" in payload[0], "/machines item missing name")
            _ensure("status" in payload[0], "/machines item missing status")
        return

    if path == "/machines/1":
        _ensure(isinstance(payload, dict), "/machines/1 must return object")
        _ensure("id" in payload, "/machines/1 missing id")
        _ensure("name" in payload, "/machines/1 missing name")
        _ensure("status" in payload, "/machines/1 missing status")
        return

    if path == "/machines/1/health":
        _ensure(isinstance(payload, dict), "/machines/1/health must return object")
        _ensure("machine_id" in payload, "/machines/1/health missing machine_id")
        _ensure("health_score" in payload, "/machines/1/health missing health_score")
        return

    if path == "/maintenance":
        _ensure(isinstance(payload, list), "/maintenance must return list")
        return

    if path == "/production/status":
        _ensure(isinstance(payload, dict), "/production/status must return object")
        for key in [
            "total_products",
            "in_progress_products",
            "completed_products",
            "total_machines",
            "active_machines",
        ]:
            _ensure(key in payload, f"/production/status missing {key}")
        return

    if path == "/alerts":
        _ensure(isinstance(payload, list), "/alerts must return list")
        return

    if path == "/twin/state":
        _ensure(isinstance(payload, dict), "/twin/state must return object")
        for key in ["machines", "products", "queues", "maintenance", "production_metrics"]:
            _ensure(key in payload, f"/twin/state missing {key}")
        return

    if path == "/analytics/kpi":
        _ensure(isinstance(payload, dict), "/analytics/kpi must return object")
        for key in ["throughput", "utilization", "downtime", "oee"]:
            _ensure(key in payload, f"/analytics/kpi missing {key}")
        return


def run_api_test() -> None:
    print_header("API Test Started")

    print("[1/6] Seeding minimum database/twin data...")
    seed_minimum_data()

    print("[2/6] Starting FastAPI server (TestClient)...")
    endpoints = [
        "/machines",
        "/machines/1",
        "/machines/1/health",
        "/maintenance",
        "/production/status",
        "/alerts",
        "/twin/state",
        "/analytics/kpi",
    ]

    with TestClient(app) as client:
        print("[3/6] Sending HTTP requests...")
        for path in endpoints:
            response = client.get(path)
            _ensure(response.status_code == 200, f"{path} returned {response.status_code}")

            try:
                payload = response.json()
            except Exception as exc:  # pragma: no cover - defensive parsing check
                raise AssertionError(f"{path} did not return valid JSON") from exc

            validate_response(path, payload)

            print(f"GET {path} -> {response.status_code} OK")
            print(_pretty(payload))

    print("[4/6] Verified valid JSON for all endpoints")
    print("[5/6] Verified required data fields for all endpoints")
    print("[6/6] API Gateway endpoint checks complete")

    print("\nAll API endpoints working correctly.")


if __name__ == "__main__":
    run_api_test()

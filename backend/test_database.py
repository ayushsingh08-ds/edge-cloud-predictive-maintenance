"""End-to-end database verification script for Smart Factory backend.

This script validates:
- Connection and session creation
- Table creation
- Inserts across all ORM models
- Queries and relationship loading
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import desc, select

from database.db_session import SessionLocal
from database.init_db import init_db
from database.models.alert import Alert
from database.models.machine import Machine
from database.models.machine_health import MachineHealth
from database.models.maintenance_task import MaintenanceTask
from database.models.rul_prediction import RULPrediction
from database.models.telemetry import Telemetry


def print_header(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def run_database_test() -> None:
    print_header("SMART FACTORY DATABASE INTEGRATION TEST")

    # 1) Ensure tables exist.
    print("[1/10] Initializing database tables...")
    init_db()
    print("  OK: Tables initialized/verified")

    db = SessionLocal()
    try:
        print("[2/10] Creating machine record...")
        machine = Machine(
            name="CNC-Alpha-01",
            type="CNC",
            location="Factory Floor A",
            status="running",
            installed_date=datetime.utcnow() - timedelta(days=500),
            last_maintenance=datetime.utcnow() - timedelta(days=30),
        )
        db.add(machine)
        db.commit()
        db.refresh(machine)
        print(f"  OK: Machine created -> id={machine.id}, name={machine.name}")

        print("[3/10] Inserting telemetry data...")
        telemetry_1 = Telemetry(
            machine_id=machine.id,
            temperature=72.3,
            vibration=0.26,
            pressure=30.1,
            rpm=1450.0,
            timestamp=datetime.utcnow() - timedelta(minutes=5),
        )
        telemetry_2 = Telemetry(
            machine_id=machine.id,
            temperature=74.1,
            vibration=0.34,
            pressure=30.4,
            rpm=1468.0,
            timestamp=datetime.utcnow(),
        )
        db.add_all([telemetry_1, telemetry_2])
        db.commit()
        print("  OK: Telemetry inserted (2 records)")

        print("[4/10] Inserting machine health record...")
        health = MachineHealth(
            machine_id=machine.id,
            health_score=88.5,
            anomaly_score=0.17,
            rul_hours=124.0,
            last_updated=datetime.utcnow(),
        )
        db.add(health)
        db.commit()
        db.refresh(health)
        print(f"  OK: Health stored -> score={health.health_score}, anomaly={health.anomaly_score}")

        print("[5/10] Inserting RUL prediction...")
        rul = RULPrediction(
            machine_id=machine.id,
            rul_hours=120.0,
            confidence=0.93,
            timestamp=datetime.utcnow(),
        )
        db.add(rul)
        db.commit()
        db.refresh(rul)
        print(f"  OK: RUL stored -> rul_hours={rul.rul_hours}, confidence={rul.confidence}")

        print("[6/10] Inserting maintenance task...")
        task = MaintenanceTask(
            machine_id=machine.id,
            task_type="Bearing Inspection",
            priority="high",
            status="scheduled",
            scheduled_date=datetime.utcnow() + timedelta(days=1),
            completed_date=None,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        print(f"  OK: Maintenance task stored -> id={task.id}, status={task.status}")

        print("[7/10] Inserting alert...")
        alert = Alert(
            machine_id=machine.id,
            alert_type="anomaly_detected",
            message="Vibration trend indicates possible bearing wear",
            severity="warning",
            timestamp=datetime.utcnow(),
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        print(f"  OK: Alert stored -> id={alert.id}, severity={alert.severity}")

        print_header("[8/10] QUERYING DATA BACK")

        queried_machine = db.scalar(select(Machine).where(Machine.id == machine.id))
        if queried_machine is None:
            raise RuntimeError("Machine query failed: no machine returned.")

        latest_telemetry = db.scalar(
            select(Telemetry)
            .where(Telemetry.machine_id == queried_machine.id)
            .order_by(desc(Telemetry.timestamp))
            .limit(1)
        )

        latest_health = db.scalar(
            select(MachineHealth)
            .where(MachineHealth.machine_id == queried_machine.id)
            .order_by(desc(MachineHealth.last_updated))
            .limit(1)
        )

        latest_rul = db.scalar(
            select(RULPrediction)
            .where(RULPrediction.machine_id == queried_machine.id)
            .order_by(desc(RULPrediction.timestamp))
            .limit(1)
        )

        tasks = list(
            db.scalars(
                select(MaintenanceTask).where(MaintenanceTask.machine_id == queried_machine.id)
            )
        )
        alerts = list(db.scalars(select(Alert).where(Alert.machine_id == queried_machine.id)))

        print("Machine Info:")
        print(
            f"  id={queried_machine.id}, name={queried_machine.name}, "
            f"type={queried_machine.type}, location={queried_machine.location}, "
            f"status={queried_machine.status}"
        )

        print("Latest Telemetry:")
        if latest_telemetry:
            print(
                f"  temp={latest_telemetry.temperature}, vibration={latest_telemetry.vibration}, "
                f"pressure={latest_telemetry.pressure}, rpm={latest_telemetry.rpm}, "
                f"timestamp={latest_telemetry.timestamp}"
            )
        else:
            print("  None")

        print("Health Record:")
        if latest_health:
            print(
                f"  health_score={latest_health.health_score}, "
                f"anomaly_score={latest_health.anomaly_score}, "
                f"rul_hours={latest_health.rul_hours}, "
                f"last_updated={latest_health.last_updated}"
            )
        else:
            print("  None")

        print("RUL Prediction:")
        if latest_rul:
            print(
                f"  rul_hours={latest_rul.rul_hours}, confidence={latest_rul.confidence}, "
                f"timestamp={latest_rul.timestamp}"
            )
        else:
            print("  None")

        print("Maintenance Tasks:")
        for item in tasks:
            print(
                f"  id={item.id}, task_type={item.task_type}, priority={item.priority}, "
                f"status={item.status}, scheduled={item.scheduled_date}, completed={item.completed_date}"
            )

        print("Alerts:")
        for item in alerts:
            print(
                f"  id={item.id}, type={item.alert_type}, severity={item.severity}, "
                f"message={item.message}, timestamp={item.timestamp}"
            )

        print_header("[9/10] VERIFYING RELATIONSHIPS")
        db.refresh(queried_machine)
        print(f"machine.telemetry_records count: {len(queried_machine.telemetry_records)}")
        print(f"machine.health_records count: {len(queried_machine.health_records)}")
        print(f"machine.rul_predictions count: {len(queried_machine.rul_predictions)}")
        print(f"machine.maintenance_tasks count: {len(queried_machine.maintenance_tasks)}")
        print(f"machine.alerts count: {len(queried_machine.alerts)}")

        print_header("[10/10] RESULT")
        print("Machine created: YES")
        print("Telemetry inserted: YES")
        print("Health stored: YES")
        print("RUL stored: YES")
        print("Maintenance task stored: YES")
        print("Alert stored: YES")
        print("Data successfully queried: YES")
        print("Database-backed state verification completed successfully.")

    except Exception as exc:
        db.rollback()
        print_header("TEST FAILED")
        print(f"Error: {exc}")
        raise
    finally:
        db.close()
        print("\nSession closed.")


if __name__ == "__main__":
    run_database_test()

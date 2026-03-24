"""Integration-style test for Analytics Service KPIs and persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import delete

from database.db_session import SessionLocal
from database.init_db import init_db
from database.models.analytics_snapshot import AnalyticsSnapshot
from database.models.machine import Machine
from database.models.machine_queue import MachineQueue
from database.models.maintenance_task import MaintenanceTask
from database.models.sim_product import SimProduct
from services.analytics import analytics_repository
from services.analytics.analytics_service import AnalyticsService
from services.analytics.bottleneck_detector import detect_bottleneck_machine
from services.analytics.metrics_calculator import (
    calculate_downtime,
    calculate_machine_utilization,
    calculate_mtbf,
    calculate_mttr,
    calculate_oee,
    calculate_throughput,
)


@dataclass
class PublishedEvent:
    topic: str
    payload: dict


class TestPublisher:
    """Capture analytics events without requiring RabbitMQ."""

    def __init__(self) -> None:
        self.events: list[PublishedEvent] = []

    def publish(self, topic: str, message: dict) -> None:
        self.events.append(PublishedEvent(topic=topic, payload=message))


def print_header(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_analytics_test() -> None:
    print_header("Analytics Test Started")

    print("[1/9] Initializing schema and resetting analytics snapshots...")
    init_db()

    db = SessionLocal()
    publisher = TestPublisher()
    service = AnalyticsService(publisher=publisher)

    try:
        db.execute(delete(AnalyticsSnapshot))
        db.commit()

        print("[2/9] Inserting production data: 10 completed products...")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        machine_a = Machine(
            name=f"Machine A - Analytics Test {stamp}",
            type="CNC",
            location="Line 1 - A",
            status="running",
        )
        machine_b = Machine(
            name=f"Machine B - Analytics Test {stamp}",
            type="Assembler",
            location="Line 1 - B",
            status="running",
        )
        db.add_all([machine_a, machine_b])
        db.commit()
        db.refresh(machine_a)
        db.refresh(machine_b)
        machine_a_id = machine_a.id
        machine_b_id = machine_b.id
        machine_a_label = machine_a.name.split(" - ")[0]
        machine_b_label = machine_b.name.split(" - ")[0]

        completed_products = [
            SimProduct(
                product_id=f"AN-P-{stamp}-{idx}",
                current_node_id=None,
                status="completed",
            )
            for idx in range(10)
        ]
        db.add_all(completed_products)

        print("[3/9] Inserting machine runtime and downtime reference data...")
        # Runtime data is simulated test input for KPI formulas.
        runtime_hours = 8.0
        downtime_hours = 2.0
        total_time = runtime_hours + downtime_hours

        print("[4/9] Inserting maintenance data: 2 maintenance events...")
        maintenance_events = [
            MaintenanceTask(
                machine_id=machine_a_id,
                task_type="repair",
                priority="high",
                status="completed",
                scheduled_date=datetime(2026, 3, 24, 9, 0, tzinfo=timezone.utc),
                completed_date=datetime(2026, 3, 24, 10, 0, tzinfo=timezone.utc),
            ),
            MaintenanceTask(
                machine_id=machine_a_id,
                task_type="repair",
                priority="high",
                status="completed",
                scheduled_date=datetime(2026, 3, 24, 13, 0, tzinfo=timezone.utc),
                completed_date=datetime(2026, 3, 24, 14, 0, tzinfo=timezone.utc),
            ),
        ]
        db.add_all(maintenance_events)

        print("[5/9] Inserting queue data...")
        db.add_all(
            [
                MachineQueue(machine_id=machine_a_id, queue_length=3),
                MachineQueue(machine_id=machine_b_id, queue_length=8),
            ]
        )
        db.commit()

        print("[6/9] Running analytics calculations...")
        throughput = calculate_throughput(completed_count=10, hours=1.0)
        utilization = {
            machine_a_id: calculate_machine_utilization(active_time=runtime_hours, total_time=total_time),
            machine_b_id: calculate_machine_utilization(active_time=7.0, total_time=10.0),
        }
        downtime = {machine_a_id: calculate_downtime([downtime_hours])}
        mtbf = {machine_a_id: calculate_mtbf(total_operating_time=10.0, number_of_failures=2)}
        mttr = {machine_a_id: calculate_mttr(total_repair_time=2.0, number_of_repairs=2)}

        availability = runtime_hours / total_time
        performance = 0.9
        quality = 1.0
        oee = calculate_oee(availability=availability, performance=performance, quality=quality)

        bottleneck = detect_bottleneck_machine(
            queue_by_machine={machine_a_id: 3, machine_b_id: 8},
            avg_processing_time_by_machine={machine_a_id: 0.5, machine_b_id: 0.9},
            utilization_by_machine=utilization,
            downtime_by_machine={machine_a_id: 2.0, machine_b_id: 0.5},
        )

        print(f"Throughput Calculated: {throughput}")
        print(f"Machine Utilization Calculated: {utilization[machine_a_id]}")
        print(f"Downtime Calculated: {downtime[machine_a_id]}")
        print(f"MTBF Calculated: {mtbf[machine_a_id]}")
        print(f"MTTR Calculated: {mttr[machine_a_id]}")
        print(f"OEE Calculated: {oee}")

        bottleneck_machine_id = bottleneck.get("machine_id")
        bottleneck_name = (
            machine_b_label
            if bottleneck_machine_id == machine_b_id
            else machine_a_label
        )
        print(f"Bottleneck Machine Detected: {bottleneck_name}")

        print("[7/9] Storing analytics and publishing analytics.updated...")
        snapshot = service.store_metrics(
            {
                "throughput": throughput,
                "utilization": utilization,
                "downtime": downtime,
                "mtbf": mtbf,
                "mttr": mttr,
                "oee": oee,
                "bottleneck_machine": bottleneck,
            }
        )
        service.publish_analytics_updated(snapshot)

        print("Analytics Stored in Database")
        print("analytics.updated Event Published")

        print("[8/9] Retrieving analytics metrics from database...")
        stored = analytics_repository.get_analytics_metrics()

        print("\nStored Analytics Metrics:")
        print(f"throughput={stored.get('throughput')}")
        print(f"utilization={stored.get('utilization')}")
        print(f"downtime={stored.get('downtime')}")
        print(f"mtbf={stored.get('mtbf')}")
        print(f"mttr={stored.get('mttr')}")
        print(f"oee={stored.get('oee')}")
        print(f"bottleneck_machine={stored.get('bottleneck_machine')}")

        print("[9/9] Verifying expected outputs and event publishing...")
        _ensure(stored.get("throughput") == 10.0, "Throughput mismatch")
        _ensure(stored.get("utilization", {}).get(str(machine_a_id), stored.get("utilization", {}).get(machine_a_id)) == 0.8, "Utilization mismatch")
        _ensure(stored.get("downtime", {}).get(str(machine_a_id), stored.get("downtime", {}).get(machine_a_id)) == 2.0, "Downtime mismatch")
        _ensure(stored.get("mtbf", {}).get(str(machine_a_id), stored.get("mtbf", {}).get(machine_a_id)) == 5.0, "MTBF mismatch")
        _ensure(stored.get("mttr", {}).get(str(machine_a_id), stored.get("mttr", {}).get(machine_a_id)) == 1.0, "MTTR mismatch")
        _ensure(abs(float(stored.get("oee", 0.0)) - 0.72) < 1e-9, "OEE mismatch")

        stored_bottleneck = stored.get("bottleneck_machine", {})
        _ensure(stored_bottleneck.get("machine_id") == machine_b_id, "Bottleneck machine mismatch")

        analytics_events = [event for event in publisher.events if event.topic == "analytics.updated"]
        _ensure(analytics_events, "analytics.updated event was not published")

        print("\nAnalytics Service Test Completed Successfully.")

    except Exception as exc:
        db.rollback()
        print_header("TEST FAILED")
        print(f"Error: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_analytics_test()

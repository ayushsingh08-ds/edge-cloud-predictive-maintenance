"""Analytics service orchestrating KPI calculation, persistence, and events."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, select

from database.db_session import SessionLocal
from database.models.machine import Machine
from database.models.machine_queue import MachineQueue
from database.models.maintenance_task import MaintenanceTask
from database.models.product_history import ProductHistory
from database.models.sim_product import SimProduct
from messaging.rabbitmq_client import RabbitMQClient
from services.analytics import analytics_repository
from services.analytics.bottleneck_detector import detect_bottleneck_machine
from services.analytics.metrics_calculator import (
    calculate_downtime,
    calculate_machine_utilization,
    calculate_mtbf,
    calculate_mttr,
    calculate_oee,
    calculate_throughput,
)


class AnalyticsService:
    """Compute factory KPIs and publish analytics updates."""

    def __init__(self, publisher: RabbitMQClient | None = None) -> None:
        self.client = publisher or RabbitMQClient()

    @staticmethod
    def _to_datetime(value) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return None

    def collect_production_data(self) -> dict:
        db = SessionLocal()
        try:
            machines = db.scalars(select(Machine).order_by(Machine.id.asc())).all()
            products = db.scalars(select(SimProduct).order_by(SimProduct.created_at.asc())).all()
            queues = db.scalars(select(MachineQueue).order_by(MachineQueue.machine_id.asc())).all()
            tasks = db.scalars(
                select(MaintenanceTask).order_by(desc(MaintenanceTask.scheduled_date))
            ).all()
            history = db.scalars(
                select(ProductHistory).order_by(ProductHistory.timestamp.asc())
            ).all()

            return {
                "machines": machines,
                "products": products,
                "queues": queues,
                "maintenance_tasks": tasks,
                "product_history": history,
            }
        finally:
            db.close()

    def _machine_processing_time_map(self, history: list[ProductHistory]) -> dict[int, float]:
        per_machine: dict[int, list[float]] = {}
        latest_by_product: dict[str, tuple[int | None, datetime]] = {}

        for event in history:
            product_id = event.product_id
            node_id = event.node_id
            timestamp = self._to_datetime(event.timestamp)
            if timestamp is None:
                continue

            previous = latest_by_product.get(product_id)
            if previous is not None:
                prev_node, prev_time = previous
                if prev_node is not None:
                    delta = max(0.0, (timestamp - prev_time).total_seconds() / 3600.0)
                    per_machine.setdefault(prev_node, []).append(delta)

            latest_by_product[product_id] = (node_id, timestamp)

        return {
            machine_id: (sum(samples) / len(samples) if samples else 0.0)
            for machine_id, samples in per_machine.items()
        }

    def calculate_metrics(self, data: dict) -> dict:
        machines: list[Machine] = data["machines"]
        products: list[SimProduct] = data["products"]
        queues: list[MachineQueue] = data["queues"]
        maintenance_tasks: list[MaintenanceTask] = data["maintenance_tasks"]
        history: list[ProductHistory] = data["product_history"]

        now = datetime.now(timezone.utc)
        one_hour_ago = now - timedelta(hours=1)

        completed_last_hour = [
            product
            for product in products
            if product.status == "completed"
            and self._to_datetime(product.updated_at)
            and self._to_datetime(product.updated_at) >= one_hour_ago
        ]
        throughput = calculate_throughput(len(completed_last_hour), 1.0)

        planned_hours = 1.0
        utilization: dict[int, float] = {}
        for machine in machines:
            active = 1.0 if str(machine.status).lower() == "running" else 0.0
            utilization[machine.id] = calculate_machine_utilization(active, planned_hours)

        downtime_by_machine: dict[int, float] = {}
        repairs_by_machine: dict[int, int] = {}
        failures_by_machine: dict[int, int] = {}

        for task in maintenance_tasks:
            scheduled = self._to_datetime(task.scheduled_date)
            completed = self._to_datetime(task.completed_date)
            if scheduled is None:
                continue

            if completed is not None:
                hours = max(0.0, (completed - scheduled).total_seconds() / 3600.0)
                downtime_by_machine[task.machine_id] = downtime_by_machine.get(task.machine_id, 0.0) + hours
                repairs_by_machine[task.machine_id] = repairs_by_machine.get(task.machine_id, 0) + 1
            else:
                failures_by_machine[task.machine_id] = failures_by_machine.get(task.machine_id, 0) + 1

        downtime = {
            machine_id: calculate_downtime([hours])
            for machine_id, hours in downtime_by_machine.items()
        }

        mtbf: dict[int, float] = {}
        mttr: dict[int, float] = {}
        for machine in machines:
            failures = failures_by_machine.get(machine.id, 0)
            repairs = repairs_by_machine.get(machine.id, 0)
            total_operating_time = planned_hours * max(1, len(products) or 1)
            total_repair_time = downtime_by_machine.get(machine.id, 0.0)

            mtbf[machine.id] = calculate_mtbf(total_operating_time, failures)
            mttr[machine.id] = calculate_mttr(total_repair_time, repairs)

        availability = sum(utilization.values()) / len(utilization) if utilization else 0.0
        avg_processing = self._machine_processing_time_map(history)
        avg_cycle = (sum(avg_processing.values()) / len(avg_processing)) if avg_processing else 1.0
        performance = min(1.0, (1.0 / max(0.001, avg_cycle)))

        total_count = max(1, len(products))
        good_count = sum(1 for product in products if product.status in {"completed", "in_progress"})
        quality = max(0.0, min(1.0, good_count / total_count))
        oee = calculate_oee(availability, performance, quality)

        queue_by_machine = {queue.machine_id: int(queue.queue_length) for queue in queues}
        bottleneck = detect_bottleneck_machine(
            queue_by_machine=queue_by_machine,
            avg_processing_time_by_machine=avg_processing,
            utilization_by_machine=utilization,
            downtime_by_machine=downtime,
        )

        return {
            "throughput": throughput,
            "utilization": utilization,
            "downtime": downtime,
            "mtbf": mtbf,
            "mttr": mttr,
            "oee": oee,
            "bottleneck_machine": bottleneck,
        }

    def store_metrics(self, metrics: dict) -> dict:
        analytics_repository.store_throughput(metrics["throughput"])
        analytics_repository.store_utilization(metrics["utilization"])
        analytics_repository.store_downtime(metrics["downtime"])
        analytics_repository.store_mtbf(metrics["mtbf"])
        analytics_repository.store_mttr(metrics["mttr"])
        analytics_repository.store_oee(metrics["oee"])
        return analytics_repository.store_bottleneck(metrics["bottleneck_machine"])

    def publish_analytics_updated(self, snapshot: dict) -> None:
        payload = {
            "event_name": "analytics.updated",
            "throughput": snapshot.get("throughput", 0.0),
            "utilization": snapshot.get("utilization", {}),
            "downtime": snapshot.get("downtime", {}),
            "mtbf": snapshot.get("mtbf", {}),
            "mttr": snapshot.get("mttr", {}),
            "oee": snapshot.get("oee", 0.0),
            "bottleneck_machine": snapshot.get("bottleneck_machine", {}),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.client.publish("analytics.updated", payload)

    def run_analytics(self) -> dict:
        data = self.collect_production_data()
        metrics = self.calculate_metrics(data)
        snapshot = self.store_metrics(metrics)
        self.publish_analytics_updated(snapshot)
        return snapshot

    def get_snapshot(self) -> dict:
        return analytics_repository.get_analytics_metrics()

    def process_event(self, routing_key: str, payload: dict) -> dict:
        _ = routing_key
        _ = payload
        return self.run_analytics()

    def start(self) -> None:
        print("[+] Analytics Service listening for KPI trigger events...")

        result = self.client.channel.queue_declare(queue="", exclusive=True)
        queue_name = result.method.queue

        topics = [
            "product.completed",
            "machine.status.changed",
            "maintenance.completed",
            "machine.queue.updated",
            "twin.state.updated",
        ]
        for topic in topics:
            self.client.channel.queue_bind(
                exchange="sensor_exchange",
                queue=queue_name,
                routing_key=topic,
            )

        def callback(ch, method, properties, body):
            try:
                payload = json.loads(body)
                routing_key = getattr(method, "routing_key", "")
                snapshot = self.process_event(routing_key, payload)
                print(
                    "[ANALYTICS] "
                    f"throughput={snapshot.get('throughput')} oee={snapshot.get('oee')}"
                )
            except Exception as exc:
                print(f"[ERROR] Analytics processing failed: {exc}")

        self.client.channel.basic_consume(
            queue=queue_name,
            on_message_callback=callback,
            auto_ack=True,
        )
        self.client.channel.start_consuming()

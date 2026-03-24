"""Routing engine service for product movement decisions."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from messaging.rabbitmq_client import RabbitMQClient
from services.routing_engine.path_finder import PathFinder
from services.routing_engine import routing_repository as repository


class RoutingEngineService:
    """Decide next machine and assign production routes using graph + machine state."""

    def __init__(
        self,
        max_queue_length: int = 5,
        health_threshold: float = 0.5,
        publisher: RabbitMQClient | None = None,
    ) -> None:
        self.max_queue_length = max_queue_length
        self.health_threshold = health_threshold
        self.client = publisher or RabbitMQClient()

        self._assigned_routes: dict[str, list[int]] = {}
        self._maintenance_blocked_machines: set[int] = set()
        self._unhealthy_blocked_machines: set[int] = set()

    @staticmethod
    def _safe_int(value: int | str | None) -> int:
        if value is None:
            raise ValueError("Missing required integer value")
        if isinstance(value, int):
            return value
        text = str(value)
        digits = "".join(ch for ch in text if ch.isdigit())
        return int(digits) if digits else int(text)

    def avoid_unhealthy_machines(self) -> set[int]:
        blocked: set[int] = set(self._unhealthy_blocked_machines)

        for node_id in repository.get_all_machine_node_ids():
            machine_id = repository.get_machine_id_for_node(node_id)
            if machine_id is None:
                continue

            health = repository.get_machine_health(machine_id)
            if health is not None and health < self.health_threshold:
                blocked.add(node_id)

        return blocked

    def avoid_maintenance_machines(self) -> set[int]:
        blocked: set[int] = set(self._maintenance_blocked_machines)

        for node_id in repository.get_all_machine_node_ids():
            machine_id = repository.get_machine_id_for_node(node_id)
            if machine_id is None:
                continue

            status = repository.get_machine_status(machine_id)
            if status is not None and status.lower() == "maintenance":
                blocked.add(node_id)

        return blocked

    def balance_load(self, candidate_nodes: list[dict]) -> dict | None:
        if not candidate_nodes:
            return None

        ranked = sorted(
            candidate_nodes,
            key=lambda item: (
                int(item["queue_length"] > self.max_queue_length),
                item["queue_length"],
                -item["health_score"],
                item["travel_time"],
            ),
        )
        return ranked[0]

    def decide_next_machine(self, product_id: str, current_node: int) -> dict | None:
        neighbors = repository.get_neighbors(current_node)
        if not neighbors:
            return None

        blocked = self.avoid_maintenance_machines() | self.avoid_unhealthy_machines()

        candidates: list[dict] = []
        for neighbor in neighbors:
            node_id = int(neighbor["id"])
            if node_id in blocked:
                continue

            machine_id = neighbor.get("machine_id")
            if machine_id is None:
                # Conveyor/buffer nodes are usually safe transit nodes.
                candidates.append(
                    {
                        "node_id": node_id,
                        "node_name": neighbor.get("node_name"),
                        "machine_id": None,
                        "health_score": 1.0,
                        "queue_length": 0,
                        "travel_time": float(neighbor.get("travel_time", 1.0)),
                    }
                )
                continue

            health = repository.get_machine_health(machine_id)
            health_score = 1.0 if health is None else float(health)
            status = repository.get_machine_status(machine_id) or "unknown"
            queue_len = repository.get_machine_queue(machine_id)

            if status.lower() == "maintenance":
                continue
            if health_score < self.health_threshold:
                continue

            candidates.append(
                {
                    "node_id": node_id,
                    "node_name": neighbor.get("node_name"),
                    "machine_id": machine_id,
                    "health_score": health_score,
                    "queue_length": queue_len,
                    "travel_time": float(neighbor.get("travel_time", 1.0)),
                }
            )

        best = self.balance_load(candidates)
        if best is None:
            return None

        self.publish_routing_decision(
            product_id=product_id,
            next_machine=best,
            current_node=current_node,
            route=[current_node, int(best["node_id"])],
        )

        return best

    def assign_route(self, product_id: str, start_node: int, end_node: int) -> list[int]:
        edges = repository.get_graph_edges()
        finder = PathFinder(edges)

        blocked = self.avoid_maintenance_machines() | self.avoid_unhealthy_machines()
        path = finder.shortest_path(start_node=start_node, end_node=end_node, blocked_nodes=blocked)

        if not path:
            path = finder.find_alternative_path(
                start_node=start_node,
                end_node=end_node,
                blocked_nodes=blocked,
            )

        if not path:
            raise ValueError(
                f"No route found for product {product_id} from node {start_node} to {end_node}"
            )

        self._assigned_routes[product_id] = path

        payload = {
            "event_name": "product.route.assigned",
            "product_id": str(product_id),
            "start_node": int(start_node),
            "end_node": int(end_node),
            "route": path,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.client.publish("product.route.assigned", payload)

        return path

    def publish_routing_decision(
        self,
        product_id: str,
        next_machine: dict,
        current_node: int | None = None,
        route: list[int] | None = None,
    ) -> None:
        payload = {
            "event_name": "routing.decision",
            "product_id": str(product_id),
            "current_node": None if current_node is None else int(current_node),
            "next_node": int(next_machine["node_id"]),
            "route": route or [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.client.publish("routing.decision", payload)

    def _default_end_node(self) -> int:
        machine_nodes = repository.get_all_machine_node_ids()
        if not machine_nodes:
            raise ValueError("No machine nodes available for route assignment")
        return machine_nodes[-1]

    def _handle_product_created(self, payload: dict) -> None:
        product_id = str(payload.get("product_id"))
        start_node = payload.get("current_node")

        if start_node is None:
            machine_id = payload.get("machine_id")
            if machine_id is None:
                raise ValueError("product.created missing current_node/machine_id")

            machine_node = repository.get_machine_node(self._safe_int(machine_id))
            if machine_node is None:
                raise ValueError(f"No machine node mapped for machine_id={machine_id}")
            start_node = machine_node["id"]

        start = self._safe_int(start_node)
        end = self._safe_int(payload.get("end_node") or self._default_end_node())

        route = self.assign_route(product_id=product_id, start_node=start, end_node=end)

        if len(route) > 1:
            next_node = route[1]
            self.publish_routing_decision(
                product_id=product_id,
                next_machine={"node_id": next_node},
                current_node=start,
                route=route,
            )

    def _handle_product_completed(self, payload: dict) -> None:
        product_id = str(payload.get("product_id"))
        self._assigned_routes.pop(product_id, None)

    def _handle_machine_health_updated(self, payload: dict) -> None:
        machine_id = self._safe_int(payload.get("machine_id"))
        node = repository.get_machine_node(machine_id)
        if node is None:
            return

        score = float(payload.get("health_score", 1.0))
        if score < self.health_threshold:
            self._unhealthy_blocked_machines.add(int(node["id"]))
        else:
            self._unhealthy_blocked_machines.discard(int(node["id"]))

    def _handle_maintenance_scheduled(self, payload: dict) -> None:
        machine_id = self._safe_int(payload.get("machine_id"))
        node = repository.get_machine_node(machine_id)
        if node is None:
            return
        self._maintenance_blocked_machines.add(int(node["id"]))

    def process_event(self, routing_key: str, payload: dict) -> None:
        if routing_key == "product.created":
            self._handle_product_created(payload)
            return

        if routing_key == "product.completed":
            self._handle_product_completed(payload)
            return

        if routing_key == "machine.health.updated":
            self._handle_machine_health_updated(payload)
            return

        if routing_key == "maintenance.scheduled":
            self._handle_maintenance_scheduled(payload)
            return

    def start(self) -> None:
        """Start Routing Engine subscriptions and process incoming events."""
        print("[+] Routing Engine listening for product/machine/maintenance events...")

        result = self.client.channel.queue_declare(queue="", exclusive=True)
        queue_name = result.method.queue

        topics = [
            "product.created",
            "product.completed",
            "machine.health.updated",
            "maintenance.scheduled",
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
                self.process_event(routing_key, payload)
            except Exception as exc:
                print(f"[ERROR] Routing event handling failed: {exc}")

        self.client.channel.basic_consume(
            queue=queue_name,
            on_message_callback=callback,
            auto_ack=True,
        )
        self.client.channel.start_consuming()

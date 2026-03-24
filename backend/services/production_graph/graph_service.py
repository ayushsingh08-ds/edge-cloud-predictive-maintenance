"""Business logic for production line graph operations."""

from __future__ import annotations

from collections import deque

from services.production_graph import graph_repository as repository


class ProductionGraphService:
    """Service for building and querying a factory layout graph."""

    def add_machine_node(self, machine_id: int, node_name: str) -> dict:
        existing = repository.get_node_by_machine_id(machine_id)
        if existing is not None:
            return existing

        return repository.create_node(
            node_name=node_name,
            node_type="machine",
            machine_id=machine_id,
        )

    def add_conveyor_node(self, node_name: str) -> dict:
        return repository.create_node(
            node_name=node_name,
            node_type="conveyor",
            machine_id=None,
        )

    def connect_nodes(self, from_node_id: int, to_node_id: int) -> dict:
        return repository.create_edge(
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            distance=1.0,
            travel_time=1.0,
        )

    def get_next_nodes(self, node_id: int) -> list[dict]:
        return repository.get_neighbors(node_id)

    def get_factory_graph(self) -> dict:
        return {
            "nodes": repository.get_all_nodes(),
            "edges": repository.get_edges(),
            "routes": repository.get_routes(),
        }

    def find_path(self, start_node_id: int, end_node_id: int) -> list[int]:
        if start_node_id == end_node_id:
            return [start_node_id]

        if repository.get_node(start_node_id) is None:
            raise ValueError(f"Start node {start_node_id} not found")
        if repository.get_node(end_node_id) is None:
            raise ValueError(f"End node {end_node_id} not found")

        queue: deque[tuple[int, list[int]]] = deque([(start_node_id, [start_node_id])])
        visited = {start_node_id}

        while queue:
            current_node, path = queue.popleft()
            neighbors = repository.get_neighbors(current_node)

            for item in neighbors:
                next_node_id = item["node"]["id"]
                if next_node_id in visited:
                    continue

                next_path = [*path, next_node_id]
                if next_node_id == end_node_id:
                    return next_path

                visited.add(next_node_id)
                queue.append((next_node_id, next_path))

        return []

    def get_machine_node(self, machine_id: int) -> dict | None:
        return repository.get_node_by_machine_id(machine_id)

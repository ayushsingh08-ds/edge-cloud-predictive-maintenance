"""Path finding utilities for routing engine decisions."""

from __future__ import annotations

import heapq
from collections import deque


class PathFinder:
    """Compute shortest and alternative paths over production graph edges."""

    def __init__(self, edges: list[dict]) -> None:
        self.edges = edges
        self._adjacency = self._build_adjacency(edges)

    @staticmethod
    def _build_adjacency(edges: list[dict]) -> dict[int, list[dict]]:
        adjacency: dict[int, list[dict]] = {}
        for edge in edges:
            from_node = int(edge["from_node_id"])
            adjacency.setdefault(from_node, []).append(edge)
        return adjacency

    def bfs_path_finding(
        self,
        start_node: int,
        end_node: int,
        blocked_nodes: set[int] | None = None,
    ) -> list[int]:
        blocked = blocked_nodes or set()
        if start_node in blocked or end_node in blocked:
            return []
        if start_node == end_node:
            return [start_node]

        queue: deque[tuple[int, list[int]]] = deque([(start_node, [start_node])])
        visited = {start_node}

        while queue:
            node, path = queue.popleft()
            for edge in self._adjacency.get(node, []):
                next_node = int(edge["to_node_id"])
                if next_node in blocked or next_node in visited:
                    continue

                next_path = [*path, next_node]
                if next_node == end_node:
                    return next_path

                visited.add(next_node)
                queue.append((next_node, next_path))

        return []

    def dijkstra(
        self,
        start_node: int,
        end_node: int,
        blocked_nodes: set[int] | None = None,
        weight_key: str = "travel_time",
    ) -> list[int]:
        blocked = blocked_nodes or set()
        if start_node in blocked or end_node in blocked:
            return []
        if start_node == end_node:
            return [start_node]

        queue: list[tuple[float, int]] = [(0.0, start_node)]
        costs: dict[int, float] = {start_node: 0.0}
        prev: dict[int, int] = {}

        while queue:
            current_cost, node = heapq.heappop(queue)
            if node == end_node:
                break

            if current_cost > costs.get(node, float("inf")):
                continue

            for edge in self._adjacency.get(node, []):
                nxt = int(edge["to_node_id"])
                if nxt in blocked:
                    continue

                edge_cost = float(edge.get(weight_key, edge.get("distance", 1.0)))
                new_cost = current_cost + max(0.0, edge_cost)

                if new_cost < costs.get(nxt, float("inf")):
                    costs[nxt] = new_cost
                    prev[nxt] = node
                    heapq.heappush(queue, (new_cost, nxt))

        if end_node not in costs:
            return []

        path = [end_node]
        while path[-1] != start_node:
            path.append(prev[path[-1]])
        path.reverse()
        return path

    def shortest_path(
        self,
        start_node: int,
        end_node: int,
        blocked_nodes: set[int] | None = None,
    ) -> list[int]:
        """Preferred shortest path using Dijkstra, with BFS fallback."""
        path = self.dijkstra(start_node, end_node, blocked_nodes=blocked_nodes)
        if path:
            return path
        return self.bfs_path_finding(start_node, end_node, blocked_nodes=blocked_nodes)

    def find_alternative_path(
        self,
        start_node: int,
        end_node: int,
        blocked_nodes: set[int] | None = None,
    ) -> list[int]:
        """Find an alternative path by excluding one internal node from the best path."""
        blocked = blocked_nodes or set()
        baseline = self.shortest_path(start_node, end_node, blocked_nodes=blocked)
        if not baseline:
            return []

        if len(baseline) <= 2:
            return baseline

        for internal_node in baseline[1:-1]:
            candidate_blocked = set(blocked)
            candidate_blocked.add(internal_node)
            candidate = self.shortest_path(
                start_node,
                end_node,
                blocked_nodes=candidate_blocked,
            )
            if candidate and candidate != baseline:
                return candidate

        return baseline

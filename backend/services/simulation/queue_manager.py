"""Queue management for machine processing simulation."""

from __future__ import annotations

from collections import defaultdict, deque

from services.simulation import simulation_repository


class QueueManager:
    """Maintain per-machine in-memory queues and sync queue length to DB."""

    def __init__(self) -> None:
        self._queues: dict[int, deque[str]] = defaultdict(deque)

    def add_to_queue(self, machine_id: int, product_id: str) -> int:
        queue = self._queues[machine_id]
        queue.append(product_id)
        simulation_repository.update_queue(machine_id, len(queue))
        return len(queue)

    def remove_from_queue(self, machine_id: int) -> str | None:
        queue = self._queues[machine_id]
        if not queue:
            simulation_repository.update_queue(machine_id, 0)
            return None

        product_id = queue.popleft()
        simulation_repository.update_queue(machine_id, len(queue))
        return product_id

    def get_queue(self, machine_id: int) -> list[str]:
        return list(self._queues[machine_id])

    def get_queue_length(self, machine_id: int) -> int:
        return len(self._queues[machine_id])

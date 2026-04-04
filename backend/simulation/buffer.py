from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Deque, Optional

from .job import Job


def _empty_job_queue() -> Deque[Job]:
    return deque()


@dataclass(slots=True)
class Buffer:
    name: str
    capacity: int | None = None
    queue: Deque[Job] = field(default_factory=_empty_job_queue)

    def put(self, job: Job) -> bool:
        if self.capacity is not None and len(self.queue) >= self.capacity:
            return False
        self.queue.append(job)
        job.mark_queued()
        return True

    def get(self) -> Optional[Job]:
        if not self.queue:
            return None
        return self.queue.popleft()

    def peek(self) -> Optional[Job]:
        return self.queue[0] if self.queue else None

    def has_space(self) -> bool:
        return self.capacity is None or len(self.queue) < self.capacity

    def release_when_available(self, downstream_available: Callable[[], bool]) -> Optional[Job]:
        if not self.queue:
            return None
        if not downstream_available():
            return None
        return self.queue.popleft()

    def __len__(self) -> int:
        return len(self.queue)

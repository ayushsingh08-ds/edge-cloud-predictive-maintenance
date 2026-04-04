from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class JobStatus(str, Enum):
    CREATED = "Created"
    QUEUED = "Queued"
    IN_PROCESS = "In Process"
    COMPLETED = "Completed"
    FAILED = "Failed"


def _empty_attributes() -> dict[str, Any]:
    return {}


@dataclass(slots=True)
class Job:
    job_id: str
    arrival_time: float
    processing_time: float
    operations: list[str] = field(default_factory=list)
    due_date: float | None = None
    priority: int = 0
    operation_processing_times: dict[str, float] = field(default_factory=dict)
    status: JobStatus = JobStatus.CREATED
    attributes: dict[str, Any] = field(default_factory=_empty_attributes)
    start_time: float | None = None
    completion_time: float | None = None
    current_operation_index: int = 0

    def __post_init__(self) -> None:
        if not self.operations and self.operation_processing_times:
            self.operations = list(self.operation_processing_times.keys())
        if self.operations and self.operations[0] not in self.operation_processing_times:
            self.operation_processing_times[self.operations[0]] = self.processing_time

    def mark_queued(self) -> None:
        self.status = JobStatus.QUEUED

    def mark_in_process(self, start_time: float) -> None:
        self.status = JobStatus.IN_PROCESS
        self.start_time = start_time

    def mark_completed(self, completion_time: float) -> None:
        self.status = JobStatus.COMPLETED
        self.completion_time = completion_time

    def mark_failed(self) -> None:
        self.status = JobStatus.FAILED

    def current_operation(self) -> str | None:
        if self.current_operation_index >= len(self.operations):
            return None
        return self.operations[self.current_operation_index]

    def processing_time_for_current_operation(self) -> float:
        operation = self.current_operation()
        if operation is None:
            return self.processing_time
        return float(self.operation_processing_times.get(operation, self.processing_time))

    def advance_operation(self) -> bool:
        self.current_operation_index += 1
        return self.current_operation_index < len(self.operations)

    def operation_count(self) -> int:
        return len(self.operations)

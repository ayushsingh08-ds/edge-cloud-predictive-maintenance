from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class OperationState(str, Enum):
    PENDING = "pending"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"


@dataclass(slots=True)
class Operation:
    op_id: int
    candidate_machines: list[int]
    processing_time: float
    sequence_type: str = "serial"
    completed: bool = False
    state: OperationState = OperationState.PENDING
    assigned_machine: int | None = None
    start_time: float | None = None
    completion_time: float | None = None
    reroute_count: int = 0


@dataclass(slots=True)
class Job:
    job_id: int
    arrival_time: float
    processing_time: float
    due_date: float
    start_time: float | None = None
    completion_time: float | None = None
    operations: list["Operation"] = field(default_factory=list)
    sequencing_mode: str = "serial"
    current_operation_index: int = 0
    rerouting_history: list[dict[str, object]] = field(default_factory=list)

    @property
    def current_op_index(self) -> int:
        return self.current_operation_index

    @current_op_index.setter
    def current_op_index(self, value: int) -> None:
        self.current_operation_index = value

    def __post_init__(self) -> None:
        # Backward compatibility: legacy jobs still pass a single processing_time.
        if not self.operations:
            self.operations = [
                Operation(
                    op_id=0,
                    candidate_machines=[],
                    processing_time=self.processing_time,
                    state=OperationState.READY,
                )
            ]

    def current_operation(self) -> Operation | None:
        if 0 <= self.current_operation_index < len(self.operations):
            return self.operations[self.current_operation_index]
        return None

    def advance_operation(self) -> None:
        operation = self.current_operation()
        if operation is not None:
            operation.completed = True
            operation.state = OperationState.COMPLETED
        self.current_operation_index += 1

    def has_remaining_operations(self) -> bool:
        return self.current_operation_index < len(self.operations)


@dataclass(slots=True)
class Machine:
    machine_id: int
    processed_jobs: int = 0
    busy_time: float = 0.0
    downtime: float = 0.0
    failure_count: int = 0
    preventive_maintenance_count: int = 0
    last_state_change: float = 0.0
    state: str = "idle"
    processing_started_at: float | None = None
    current_job: Job | None = None
    current_operation_index: int | None = None
    busy_time_since_maintenance: float = 0.0
    queue_depth_samples: list[int] = field(default_factory=list)

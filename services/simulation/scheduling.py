from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from random import Random

from services.scheduler.health_aware import HealthAwareWeights, compute_priority_scores

from .entities import Job, Machine


class SchedulingPolicy(str, Enum):
    RANDOM = "random"
    SPT = "spt"
    QUEUE_BASED = "queue_based"
    HEALTH_AWARE = "health_aware"


@dataclass(slots=True)
class SchedulerContext:
    machines: list[Machine]
    queue_lengths: list[int]
    queue_workload_hours: list[float]
    machine_health: list[float]
    due_date_urgency: float


class BaselineScheduler:
    def __init__(
        self,
        policy: SchedulingPolicy,
        rng: Random,
        health_weights: HealthAwareWeights | None = None,
    ) -> None:
        self.policy = policy
        self.rng = rng
        self.health_weights = health_weights or HealthAwareWeights()

    def select_machine(self, job: Job, context: SchedulerContext) -> int:
        return self.select_from_candidates(
            job=job,
            context=context,
            candidate_machines=[m.machine_id for m in context.machines],
        )

    def select_from_candidates(
        self,
        *,
        job: Job,
        context: SchedulerContext,
        candidate_machines: list[int],
    ) -> int:
        return self.select_machine_from_subset(
            job=job,
            context=context,
            candidate_machines=candidate_machines,
        )

    def select_machine_from_subset(
        self,
        *,
        job: Job,
        context: SchedulerContext,
        candidate_machines: list[int],
    ) -> int:
        if not candidate_machines:
            raise ValueError("candidate_machines cannot be empty")

        if self.policy == SchedulingPolicy.RANDOM:
            return self.rng.choice(candidate_machines)

        if self.policy == SchedulingPolicy.SPT:
            # SPT proxy on subset: route to lightest candidate queue + short-job preference.
            weighted_scores = {
                machine_id: (
                    context.queue_workload_hours[machine_id]
                    + (0.6 * context.queue_lengths[machine_id])
                    + (0.4 * job.processing_time)
                )
                for machine_id in candidate_machines
            }
            return min(weighted_scores, key=weighted_scores.get)

        if self.policy == SchedulingPolicy.HEALTH_AWARE:
            subset_health = [context.machine_health[machine_id] for machine_id in candidate_machines]
            subset_queues = [context.queue_lengths[machine_id] for machine_id in candidate_machines]
            subset_scores = compute_priority_scores(
                processing_time=job.processing_time,
                machine_health=subset_health,
                queue_lengths=subset_queues,
                due_date_urgency=context.due_date_urgency,
                weights=self.health_weights,
            )
            scores = {
                machine_id: score
                for machine_id, score in zip(candidate_machines, subset_scores)
            }
            return max(scores, key=scores.get)

        # Queue-based baseline on subset: dispatch to least occupied candidate queue.
        return min(candidate_machines, key=lambda machine_id: context.queue_lengths[machine_id])

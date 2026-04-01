from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class HealthAwareWeights:
    w1: float = 0.35
    w2: float = 0.30
    w3: float = 0.20
    w4: float = 0.15


def compute_priority_scores(
    *,
    processing_time: float,
    machine_health: list[float],
    queue_lengths: list[int],
    due_date_urgency: float,
    weights: HealthAwareWeights | None = None,
) -> list[float]:
    w = weights or HealthAwareWeights()

    inv_processing = 1.0 / max(processing_time, 1e-6)
    inv_queues = [1.0 / max(float(q), 1.0) for q in queue_lengths]

    return [
        (w.w1 * inv_processing)
        + (w.w2 * float(health))
        + (w.w3 * inv_queue)
        + (w.w4 * due_date_urgency)
        for health, inv_queue in zip(machine_health, inv_queues)
    ]


def select_from_candidates(
    *,
    processing_time: float,
    machine_health: list[float],
    queue_lengths: list[int],
    due_date_urgency: float,
    candidate_machines: list[int],
    weights: HealthAwareWeights | None = None,
) -> int:
    if not candidate_machines:
        raise ValueError("candidate_machines cannot be empty")

    subset_health = [machine_health[machine_id] for machine_id in candidate_machines]
    subset_queues = [queue_lengths[machine_id] for machine_id in candidate_machines]
    scores = compute_priority_scores(
        processing_time=processing_time,
        machine_health=subset_health,
        queue_lengths=subset_queues,
        due_date_urgency=due_date_urgency,
        weights=weights,
    )

    best_index = max(range(len(candidate_machines)), key=lambda idx: scores[idx])
    return candidate_machines[best_index]

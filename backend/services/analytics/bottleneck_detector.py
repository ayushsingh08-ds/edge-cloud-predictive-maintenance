"""Bottleneck detection helpers for production analytics."""

from __future__ import annotations


def find_highest_queue_machine(queue_by_machine: dict[int, int]) -> int | None:
    if not queue_by_machine:
        return None
    return max(queue_by_machine, key=lambda machine_id: queue_by_machine[machine_id])


def find_slowest_machine(avg_processing_time_by_machine: dict[int, float]) -> int | None:
    if not avg_processing_time_by_machine:
        return None
    return max(
        avg_processing_time_by_machine,
        key=lambda machine_id: avg_processing_time_by_machine[machine_id],
    )


def find_most_utilized_machine(utilization_by_machine: dict[int, float]) -> int | None:
    if not utilization_by_machine:
        return None
    return max(utilization_by_machine, key=lambda machine_id: utilization_by_machine[machine_id])


def detect_bottleneck_machine(
    queue_by_machine: dict[int, int],
    avg_processing_time_by_machine: dict[int, float],
    utilization_by_machine: dict[int, float],
    downtime_by_machine: dict[int, float] | None = None,
) -> dict:
    highest_queue_machine = find_highest_queue_machine(queue_by_machine)
    slowest_machine = find_slowest_machine(avg_processing_time_by_machine)
    most_utilized_machine = find_most_utilized_machine(utilization_by_machine)

    downtime_by_machine = downtime_by_machine or {}
    most_downtime_machine = (
        max(downtime_by_machine, key=lambda machine_id: downtime_by_machine[machine_id])
        if downtime_by_machine
        else None
    )

    score: dict[int, int] = {}
    for machine_id in [
        highest_queue_machine,
        slowest_machine,
        most_utilized_machine,
        most_downtime_machine,
    ]:
        if machine_id is None:
            continue
        score[machine_id] = score.get(machine_id, 0) + 1

    selected_machine = max(score, key=lambda machine_id: score[machine_id]) if score else None

    return {
        "machine_id": selected_machine,
        "highest_queue_machine": highest_queue_machine,
        "slowest_machine": slowest_machine,
        "most_utilized_machine": most_utilized_machine,
        "most_downtime_machine": most_downtime_machine,
    }

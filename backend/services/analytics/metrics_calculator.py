"""Metric calculators for Smart Factory analytics KPIs."""

from __future__ import annotations


def calculate_throughput(completed_count: int, hours: float) -> float:
    if hours <= 0:
        return 0.0
    return round(float(completed_count) / float(hours), 4)


def calculate_machine_utilization(active_time: float, total_time: float) -> float:
    if total_time <= 0:
        return 0.0
    return round(max(0.0, min(1.0, float(active_time) / float(total_time))), 4)


def calculate_downtime(downtime_events: list[float]) -> float:
    return round(sum(max(0.0, float(item)) for item in downtime_events), 4)


def calculate_mtbf(total_operating_time: float, number_of_failures: int) -> float:
    if number_of_failures <= 0:
        return round(float(total_operating_time), 4)
    return round(float(total_operating_time) / float(number_of_failures), 4)


def calculate_mttr(total_repair_time: float, number_of_repairs: int) -> float:
    if number_of_repairs <= 0:
        return 0.0
    return round(float(total_repair_time) / float(number_of_repairs), 4)


def calculate_oee(
    availability: float,
    performance: float,
    quality: float,
) -> float:
    availability = max(0.0, min(1.0, float(availability)))
    performance = max(0.0, min(1.0, float(performance)))
    quality = max(0.0, min(1.0, float(quality)))
    return round(availability * performance * quality, 4)

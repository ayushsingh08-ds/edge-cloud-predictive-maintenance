"""Routing analytics for flexible job-shop simulations."""

from __future__ import annotations

from collections import Counter
from typing import Any


def routing_efficiency(job_record: dict[str, Any]) -> float:
    operations = job_record.get("operations", [])
    if not operations:
        return 1.0

    direct_ops = len(operations)
    actual_hops = sum(1 + int(op.get("reroute_count", 0)) for op in operations)
    return round(direct_ops / max(actual_hops, 1), 4)


def rerouting_stats(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    total_reroutes = 0
    affected_jobs = 0
    for job in jobs:
        reroutes = sum(int(op.get("reroute_count", 0)) for op in job.get("operations", []))
        total_reroutes += reroutes
        if reroutes > 0:
            affected_jobs += 1

    avg_delay_proxy = total_reroutes * 0.05 / max(len(jobs), 1)

    return {
        "jobs_count": len(jobs),
        "total_reroutes": total_reroutes,
        "affected_jobs": affected_jobs,
        "avg_rerouting_delay_hours": round(avg_delay_proxy, 4),
        "routing_success_rate": round(1.0 - (affected_jobs / max(len(jobs), 1)), 4),
    }


def bottleneck_ops(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for job in jobs:
        for op in job.get("operations", []):
            if int(op.get("reroute_count", 0)) > 0:
                key = f"op_{op.get('op_id', 'unknown')}"
                counter[key] += int(op.get("reroute_count", 0))

    most_common = counter.most_common(10)
    return [{"operation": op, "reroutes": count} for op, count in most_common]


def analyze_routing(
    jobs: list[dict[str, Any]],
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    aggregate = rerouting_stats(jobs)
    efficiencies = [routing_efficiency(job) for job in jobs]
    mean_efficiency = round(sum(efficiencies) / max(len(efficiencies), 1), 4)

    event_counts: Counter[str] = Counter()
    if events:
        for event in events:
            event_counts[str(event.get("event", "unknown"))] += 1

    # Baseline assumes direct routing without reroute (efficiency=1.0).
    baseline_efficiency = 1.0
    efficiency_gap_vs_baseline = round(baseline_efficiency - mean_efficiency, 4)

    return {
        "jobs_count": aggregate["jobs_count"],
        "total_reroutes": aggregate["total_reroutes"],
        "affected_jobs": aggregate["affected_jobs"],
        "avg_rerouting_delay_hours": aggregate["avg_rerouting_delay_hours"],
        "routing_success_rate": aggregate["routing_success_rate"],
        "mean_routing_efficiency": mean_efficiency,
        "baseline_efficiency": baseline_efficiency,
        "efficiency_gap_vs_baseline": efficiency_gap_vs_baseline,
        "bottleneck_operations": bottleneck_ops(jobs),
        "event_counts": dict(event_counts),
    }

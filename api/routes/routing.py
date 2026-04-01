"""Routing analytics and graph endpoints backed by persisted history."""

from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from db.database import get_db, fetch_recent_jobs_with_details, fetch_routing_history
from services.simulation.routing_analytics import analyze_routing


router = APIRouter()


@router.get("/factory-graph")
async def get_factory_routing_graph(limit: int = Query(default=1000, ge=1, le=10000)) -> dict[str, Any]:
    """Build a simple routing graph from machine-to-machine transitions."""
    try:
        with get_db() as db:
            events = fetch_routing_history(db, limit=limit)
            nodes: set[int] = set()
            edge_counter: Counter[tuple[int, int]] = Counter()
            latest_machine_by_op: dict[tuple[int, int], int] = {}

            for event in events:
                if event.machine_id is not None:
                    nodes.add(event.machine_id)
                if event.from_machine_id is not None:
                    nodes.add(event.from_machine_id)
                if event.to_machine_id is not None:
                    nodes.add(event.to_machine_id)
                if event.from_machine_id is not None and event.to_machine_id is not None:
                    edge_counter[(event.from_machine_id, event.to_machine_id)] += 1

                # Derive transitions for records without explicit from/to machine IDs.
                if event.machine_id is not None:
                    op_key = (event.job_fk, event.operation_id)
                    previous_machine = latest_machine_by_op.get(op_key)
                    if previous_machine is not None and previous_machine != event.machine_id:
                        edge_counter[(previous_machine, event.machine_id)] += 1
                    latest_machine_by_op[op_key] = event.machine_id

            return {
                "nodes": [{"id": n} for n in sorted(nodes)],
                "edges": [
                    {
                        "source": src,
                        "target": dst,
                        "count": count,
                    }
                    for (src, dst), count in edge_counter.items()
                ],
                "events_considered": len(events),
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_routing_history(
    job_id: int | None = None,
    operation_id: int | None = None,
    limit: int = Query(default=500, ge=1, le=5000),
) -> dict[str, Any]:
    """Query routing history with optional filters."""
    try:
        with get_db() as db:
            events = fetch_routing_history(db, job_id=job_id, operation_id=operation_id, limit=limit)
            return {
                "count": len(events),
                "events": [
                    {
                        "job_fk": event.job_fk,
                        "operation_id": event.operation_id,
                        "event_time": event.event_time,
                        "event_type": event.event_type,
                        "from_machine_id": event.from_machine_id,
                        "to_machine_id": event.to_machine_id,
                        "machine_id": event.machine_id,
                        "candidate_machines": event.candidate_machines,
                        "policy": event.policy,
                        "metadata": event.event_metadata,
                    }
                    for event in events
                ],
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bottlenecks")
async def get_routing_bottlenecks(limit_jobs: int = Query(default=200, ge=1, le=5000)) -> dict[str, Any]:
    """Compute bottleneck and efficiency analytics from persisted job routing."""
    try:
        with get_db() as db:
            jobs = fetch_recent_jobs_with_details(db, limit=limit_jobs)
            events: list[dict[str, Any]] = []
            for job in jobs:
                events.extend(job.get("routing_events", []))

            stats = analyze_routing(jobs, events)
            return {
                "jobs_analyzed": stats["jobs_count"],
                "total_reroutes": stats["total_reroutes"],
                "mean_routing_efficiency": stats["mean_routing_efficiency"],
                "baseline_efficiency": stats["baseline_efficiency"],
                "efficiency_gap_vs_baseline": stats["efficiency_gap_vs_baseline"],
                "bottleneck_operations": stats["bottleneck_operations"],
                "event_counts": stats["event_counts"],
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]

"""Operation-level query endpoints backed by routing persistence."""

from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import APIRouter, HTTPException

from db.database import get_db, fetch_operations, fetch_routing_history


router = APIRouter()


def _serialize_operation(record: Any) -> dict[str, Any]:
    return {
        "job_fk": record.job_fk,
        "op_id": record.op_id,
        "sequence_type": record.sequence_type,
        "candidate_machines": record.candidate_machines,
        "assigned_machine": record.assigned_machine,
        "processing_time": record.processing_time,
        "status": record.status,
        "completed": record.completed,
        "start_time": record.start_time,
        "completion_time": record.completion_time,
        "reroute_count": record.reroute_count,
    }


@router.get("/")
async def get_operations(job_id: int | None = None, op_id: int | None = None, limit: int = 200):
    """List operations with optional filtering by job_id and op_id."""
    try:
        with get_db() as db:
            operations = fetch_operations(db, job_id=job_id, op_id=op_id, limit=limit)
            return {
                "count": len(operations),
                "operations": [_serialize_operation(op) for op in operations],
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}/{op_id}/machines")
async def get_operation_machine_history(job_id: int, op_id: int):
    """Get machines that executed/routed a specific operation."""
    try:
        with get_db() as db:
            events = fetch_routing_history(db, job_id=job_id, operation_id=op_id, limit=1000)
            machine_ids = [
                event.machine_id
                for event in events
                if event.machine_id is not None
            ]
            unique_machines = sorted(set(machine_ids))

            return {
                "job_id": job_id,
                "op_id": op_id,
                "machines": unique_machines,
                "machine_count": len(unique_machines),
                "event_count": len(events),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}/{op_id}/failure-analysis")
async def get_operation_failure_analysis(job_id: int, op_id: int):
    """Analyze failure/interrupt patterns for a specific operation."""
    try:
        with get_db() as db:
            events = fetch_routing_history(db, job_id=job_id, operation_id=op_id, limit=2000)
            if not events:
                raise HTTPException(status_code=404, detail="No routing/failure history found for operation")

            event_counts: Counter[str] = Counter(event.event_type for event in events)
            interruptions = [e for e in events if e.event_type == "operation_interrupted"]
            machine_failures = [e for e in events if e.event_type in {"machine_failed", "machine_failure"}]
            reroutes = [e for e in events if e.event_type == "job_rerouted"]

            return {
                "job_id": job_id,
                "op_id": op_id,
                "events_total": len(events),
                "interruptions": len(interruptions),
                "machine_failures": len(machine_failures),
                "reroutes": len(reroutes),
                "event_breakdown": dict(event_counts),
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]

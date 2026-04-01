"""
Job endpoints - Get job queue, status, and history
"""

from fastapi import APIRouter, HTTPException
from typing import List
from datetime import datetime, timedelta
import logging

from api.models import (
    JobStatus,
    JobQueueResponse,
    JobSubmissionSchema,
    OperationSchema,
    RoutingEventSchema,
)
from db.database import get_db, fetch_job_with_operations, serialize_job_record

router = APIRouter()
logger = logging.getLogger(__name__)

_submitted_jobs: dict[int, JobSubmissionSchema] = {}


@router.get("/queue", response_model=JobQueueResponse)
async def get_job_queue():
    """
    Get current job queue status.
    
    Returns:
        List of waiting jobs and queue statistics.
    """
    try:
        queue_jobs = []
        
        for i in range(5):
            queue_jobs.append(JobStatus(
                job_id=100 + i,
                arrival_time=datetime.now() - timedelta(hours=i*0.5),
                due_date=datetime.now() + timedelta(hours=8),
                processing_time_hours=0.5 + (i * 0.1),
                assigned_machine=None,
                status="waiting",
            ))
        
        return JobQueueResponse(
            total_jobs_waiting=12,
            total_jobs_processing=3,
            total_jobs_completed=87,
            queue=queue_jobs,
            average_wait_time=30.0,  # minutes
        )
    
    except Exception as e:
        logger.error(f"Error getting job queue: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}")
async def get_job_status(job_id: int):
    """
    Get status of a specific job.
    
    Args:
        job_id: Job ID
    
    Returns:
        Job status, assigned machine, progress.
    """
    try:
        with get_db() as db:
            persisted = fetch_job_with_operations(db, job_id)
            if persisted is not None:
                job_payload = serialize_job_record(persisted)
                return {
                    "job_id": job_payload["job_id"],
                    "arrival_time": job_payload["arrival_time"],
                    "due_date": job_payload["due_date"],
                    "start_time": job_payload["start_time"],
                    "completion_time": job_payload["completion_time"],
                    "status": "completed" if job_payload["completion_time"] is not None else "in_progress",
                    "current_operation_index": sum(1 for op in job_payload["operations"] if op["completed"]),
                    "operations": job_payload["operations"],
                }

        if job_id in _submitted_jobs:
            submitted = _submitted_jobs[job_id]
            return {
                "job_id": submitted.job_id,
                "arrival_time": submitted.arrival_time,
                "due_date": submitted.due_date,
                "status": "waiting",
                "current_operation_index": 0,
                "operations": [op.model_dump() for op in submitted.operations],
            }

        if job_id < 100 or job_id > 120:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        return JobStatus(
            job_id=job_id,
            arrival_time=datetime.now() - timedelta(minutes=15),
            due_date=datetime.now() + timedelta(hours=8),
            processing_time_hours=0.5,
            status="waiting",
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/submit")
async def submit_job(job: JobSubmissionSchema):
    """Submit a flexible multi-operation job definition."""
    try:
        if any(len(op.candidate_machines) == 0 for op in job.operations):
            raise HTTPException(status_code=400, detail="Each operation must have at least one candidate machine")

        _submitted_jobs[job.job_id] = job
        return {
            "status": "accepted",
            "job_id": job.job_id,
            "operations_count": len(job.operations),
            "sequencing_mode": job.sequencing_mode,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting job: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}/operations")
async def get_job_operations(job_id: int):
    """Return operation-level plan and status for a job."""
    try:
        with get_db() as db:
            persisted = fetch_job_with_operations(db, job_id)
            if persisted is not None:
                job_payload = serialize_job_record(persisted)
                return {
                    "job_id": job_id,
                    "operations": job_payload["operations"],
                    "current_operation_index": sum(1 for op in job_payload["operations"] if op["completed"]),
                    "source": "database",
                }

        if job_id in _submitted_jobs:
            submitted = _submitted_jobs[job_id]
            return {
                "job_id": job_id,
                "operations": [op.model_dump() for op in submitted.operations],
                "current_operation_index": 0,
            }

        # Fallback mock operations for demo data.
        return {
            "job_id": job_id,
            "operations": [
                OperationSchema(op_id=0, candidate_machines=[0, 1], processing_time=0.4, status="completed").model_dump(),
                OperationSchema(op_id=1, candidate_machines=[1, 2], processing_time=0.6, status="in_progress", assigned_machine=2).model_dump(),
                OperationSchema(op_id=2, candidate_machines=[2], processing_time=0.3, status="pending").model_dump(),
            ],
            "current_operation_index": 1,
        }
    except Exception as e:
        logger.error(f"Error getting job operations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}/routing-chain")
async def get_job_routing_chain(job_id: int):
    """Return operation routing/re-routing chain for visualization."""
    try:
        with get_db() as db:
            persisted = fetch_job_with_operations(db, job_id)
            if persisted is not None:
                job_payload = serialize_job_record(persisted)
                return {
                    "job_id": job_id,
                    "total_events": len(job_payload["routing_events"]),
                    "events": job_payload["routing_events"],
                    "source": "database",
                }

        events = [
            RoutingEventSchema(
                time=12.4,
                event="job_routed",
                job_id=job_id,
                operation=1,
                machine_id=1,
                candidate_machines=[0, 1],
                policy="health_aware",
            ).model_dump(),
            RoutingEventSchema(
                time=12.9,
                event="machine_failed",
                job_id=job_id,
                operation=1,
                machine_id=1,
                from_machine_id=1,
                candidate_machines=[0, 1],
            ).model_dump(),
            RoutingEventSchema(
                time=13.0,
                event="job_routed",
                job_id=job_id,
                operation=1,
                machine_id=2,
                to_machine_id=2,
                candidate_machines=[1, 2],
                policy="health_aware",
            ).model_dump(),
        ]
        return {
            "job_id": job_id,
            "total_events": len(events),
            "events": events,
        }
    except Exception as e:
        logger.error(f"Error getting job routing chain: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/completed/recent")
async def get_recent_completed_jobs(limit: int = 50):
    """
    Get recently completed jobs.
    
    Args:
        limit: Maximum number of jobs to return
    
    Returns:
        List of recently completed jobs with metrics.
    """
    try:
        completed = []
        for i in range(min(10, limit)):
            completed.append({
                "job_id": 50 + i,
                "assigned_machine": i % 3,
                "processing_time_hours": 0.5,
                "completion_time": (datetime.now() - timedelta(minutes=i*10)).isoformat(),
                "tardiness_hours": 0.0,
            })
        
        return {
            "total": 87,
            "recent": completed,
        }
    
    except Exception as e:
        logger.error(f"Error getting completed jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_job_statistics():
    """
    Get statistics about job processing.
    
    Returns:
        Throughput, wait times, tardiness metrics.
    """
    try:
        return {
            "total_jobs_processed": 87,
            "average_processing_time": 0.5,  # hours
            "average_wait_time": 0.25,  # hours
            "average_tardiness": 0.05,  # hours
            "on_time_percentage": 95.0,
            "throughput_jobs_per_hour": 5.5,
        }
    
    except Exception as e:
        logger.error(f"Error getting job statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]

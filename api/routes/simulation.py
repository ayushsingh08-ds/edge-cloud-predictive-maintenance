"""
Simulation endpoints - Run simulations with different policies, compare results
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, List
from datetime import datetime
from uuid import uuid4
import logging
import json
from pathlib import Path

from api.models import SimulationParams, SimulationResponse, PolicyComparisonResponse
from api.ws_manager import ws_manager
from db.database import get_db, save_job_record, save_operation_record, save_routing_event
from services.simulation.engine import FactorySimulation, FactoryConfig, SchedulingPolicy
from services.simulation.routing_analytics import routing_efficiency, rerouting_stats, bottleneck_ops, analyze_routing

router = APIRouter()
logger = logging.getLogger(__name__)


# In-memory simulation storage
_active_simulations: Dict[str, Dict] = {}
_completed_simulations: Dict[str, Dict] = {}


def get_completed_simulation(simulation_id: str) -> Dict | None:
    return _completed_simulations.get(simulation_id)


def list_completed_simulations() -> Dict[str, Dict]:
    return _completed_simulations


def _persist_simulation_data(simulation_result: Dict) -> None:
    jobs = simulation_result.get("jobs", [])
    events = simulation_result.get("events", [])

    with get_db() as db:
        for job in jobs:
            job_record = save_job_record(db, job)
            for op in job.get("operations", []):
                save_operation_record(db, job_record.id, op)

            for ev in events:
                if ev.get("job_id") != job.get("job_id"):
                    continue
                save_routing_event(
                    db,
                    job_record.id,
                    {
                        "operation_id": ev.get("operation", 0),
                        "event_time": ev.get("time", 0.0),
                        "event_type": ev.get("event", "operation_routed"),
                        "from_machine_id": ev.get("from_machine_id"),
                        "to_machine_id": ev.get("to_machine_id"),
                        "machine_id": ev.get("machine_id"),
                        "candidate_machines": ev.get("candidate_machines", []),
                        "policy": ev.get("policy"),
                        "event_metadata": ev.get("metadata", {}),
                    },
                )


def _serialize_jobs(sim: FactorySimulation) -> list[dict]:
    serialized = []
    for job in sim.jobs:
        serialized.append(
            {
                "job_id": job.job_id,
                "arrival_time": job.arrival_time,
                "due_date": job.due_date,
                "start_time": job.start_time,
                "completion_time": job.completion_time,
                "current_operation_index": job.current_operation_index,
                "operations": [
                    {
                        "op_id": op.op_id,
                        "candidate_machines": op.candidate_machines,
                        "processing_time": op.processing_time,
                        "completed": op.completed,
                        "status": str(op.state),
                        "assigned_machine": op.assigned_machine,
                        "reroute_count": op.reroute_count,
                    }
                    for op in job.operations
                ],
                "rerouting_history": job.rerouting_history,
            }
        )
    return serialized


@router.post("/run", response_model=Dict)
async def run_simulation(
    params: SimulationParams,
    background_tasks: BackgroundTasks,
):
    """
    Run a simulation with specified policy and duration.
    
    Args:
        params: Simulation parameters (policy, duration, machines, etc.)
        background_tasks: For async execution
    
    Returns:
        Simulation ID and initial status.
    """
    try:
        sim_id = str(uuid4())[:8]
        
        # Create config
        config = FactoryConfig(
            num_machines=params.num_machines,
            arrival_rate_per_hour=params.arrival_rate,
            enable_failures=params.enable_failures,
            scheduling_policy=SchedulingPolicy[params.policy.upper()],
            random_seed=params.random_seed or 42,
        )
        
        # Run simulation synchronously (can be async in production)
        sim = FactorySimulation(config)
        results = sim.run(until_hours=params.duration_hours)
        
        # Store results
        simulation_result = {
            "simulation_id": sim_id,
            "timestamp": datetime.now(),
            "parameters": params.dict(),
            "metrics": {
                "policy": params.policy.value,
                "duration_hours": params.duration_hours,
                "jobs_completed": results["jobs_completed"],
                "jobs_failed": 0,
                "average_tardiness_hours": results["avg_tardiness_hours"],
                "total_downtime_hours": results["downtime_hours"],
                "total_failures": results["failures"],
                "utilization": results["utilization"],
                "throughput_jobs_per_hour": results["throughput_jobs_per_hour"],
                "average_wait_time": 0.25,
            },
            "events": sim.event_log,
            "jobs": _serialize_jobs(sim),
        }
        simulation_result["routing_stats"] = analyze_routing(
            simulation_result["jobs"],
            simulation_result["events"],
        )
        
        _completed_simulations[sim_id] = simulation_result
        _persist_simulation_data(simulation_result)

        await ws_manager.broadcast_json(
            {
                "event_type": "simulation_completed",
                "simulation_id": sim_id,
                "timestamp": datetime.now().isoformat(),
                "metrics": simulation_result["metrics"],
            }
        )
        
        logger.info(f"Simulation {sim_id} completed with policy {params.policy}")
        
        return {
            "simulation_id": sim_id,
            "status": "completed",
            "message": f"Simulation completed in {params.duration_hours}h",
        }
    
    except Exception as e:
        logger.error(f"Error running simulation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{simulation_id}")
async def get_simulation_results(simulation_id: str):
    """
    Get results of a completed simulation.
    
    Args:
        simulation_id: Simulation ID
    
    Returns:
        Full simulation results and metrics.
    """
    try:
        if simulation_id in _completed_simulations:
            result = _completed_simulations[simulation_id]
            return {
                "simulation_id": simulation_id,
                "status": "completed",
                "timestamp": result["timestamp"].isoformat(),
                "parameters": result["parameters"],
                "metrics": result["metrics"],
                "routing_stats": result.get("routing_stats", {}),
                "jobs": result.get("jobs", []),
            }
        
        elif simulation_id in _active_simulations:
            return {
                "simulation_id": simulation_id,
                "status": "running",
                "progress_percent": 50,
            }
        
        else:
            raise HTTPException(status_code=404, detail=f"Simulation {simulation_id} not found")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting simulation results: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{simulation_id}/routing-events")
async def get_simulation_routing_events(simulation_id: str):
    """Get operation routing/re-routing events from a completed simulation."""
    try:
        result = _completed_simulations.get(simulation_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Simulation {simulation_id} not found")

        events = [
            ev
            for ev in result.get("events", [])
            if ev.get("event")
            in {
                "operation_routed",
                "operation_started",
                "operation_completed",
                "operation_interrupted",
                "job_rerouted",
                "machine_failed",
                "machine_repaired",
            }
        ]
        return {
            "simulation_id": simulation_id,
            "count": len(events),
            "events": events,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting routing events: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{simulation_id}/operations")
async def get_simulation_operations(simulation_id: str):
    """Get operation-level details for all jobs in a simulation."""
    try:
        result = _completed_simulations.get(simulation_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Simulation {simulation_id} not found")

        operations: list[dict] = []
        for job in result.get("jobs", []):
            for operation in job.get("operations", []):
                operations.append(
                    {
                        "job_id": job.get("job_id"),
                        "operation": operation,
                    }
                )

        return {
            "simulation_id": simulation_id,
            "count": len(operations),
            "operations": operations,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting simulation operations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{simulation_id}/efficiency-report")
async def get_simulation_efficiency_report(simulation_id: str):
    """Get simple routing efficiency report for completed simulation."""
    try:
        result = _completed_simulations.get(simulation_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Simulation {simulation_id} not found")

        jobs = result.get("jobs", [])
        aggregate = analyze_routing(jobs, result.get("events", []))

        return {
            "simulation_id": simulation_id,
            "jobs_count": aggregate["jobs_count"],
            "total_reroutes": aggregate["total_reroutes"],
            "affected_jobs": aggregate["affected_jobs"],
            "avg_rerouting_delay_hours": aggregate["avg_rerouting_delay_hours"],
            "routing_success_rate": aggregate["routing_success_rate"],
            "mean_routing_efficiency": aggregate["mean_routing_efficiency"],
            "baseline_efficiency": aggregate["baseline_efficiency"],
            "efficiency_gap_vs_baseline": aggregate["efficiency_gap_vs_baseline"],
            "bottleneck_operations": aggregate["bottleneck_operations"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error building efficiency report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare-policies")
async def compare_policies(
    policies: List[str] = None,
    duration_hours: float = 8.0,
    num_machines: int = 3,
):
    """
    Compare multiple scheduling policies on same problem instance.
    
    Args:
        policies: List of policies to compare (random, queue_based, health_aware, rl)
        duration_hours: Simulation duration
        num_machines: Number of machines
    
    Returns:
        Comparison ID and results.
    """
    try:
        if policies is None:
            policies = ["random", "queue_based", "health_aware"]
        
        comparison_id = str(uuid4())[:8]
        results = {}
        
        for policy_name in policies:
            try:
                policy = SchedulingPolicy[policy_name.upper()]
                
                config = FactoryConfig(
                    num_machines=num_machines,
                    scheduling_policy=policy,
                    enable_failures=True,
                )
                
                sim = FactorySimulation(config)
                sim_results = sim.run(until_hours=duration_hours)
                
                results[policy_name.upper()] = {
                    "policy": policy_name.upper(),
                    "duration_hours": duration_hours,
                    "jobs_completed": sim_results["jobs_completed"],
                    "jobs_failed": 0,
                    "average_tardiness_hours": sim_results["avg_tardiness_hours"],
                    "total_downtime_hours": sim_results["downtime_hours"],
                    "total_failures": sim_results["failures"],
                    "utilization": sim_results["utilization"],
                    "throughput_jobs_per_hour": sim_results["throughput_jobs_per_hour"],
                    "average_wait_time": 0.25,
                }
            
            except Exception as e:
                logger.error(f"Error simulating policy {policy_name}: {str(e)}")
                results[policy_name.upper()] = {"error": str(e)}
        
        return {
            "comparison_id": comparison_id,
            "timestamp": datetime.now().isoformat(),
            "results": results,
            "best_policy": max(
                results.items(),
                key=lambda x: x[1].get("throughput_jobs_per_hour", 0) - x[1].get("average_tardiness_hours", 999),
            )[0],
        }
    
    except Exception as e:
        logger.error(f"Error comparing policies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/recent")
async def get_recent_simulations(limit: int = 20):
    """
    Get recently completed simulations.
    
    Args:
        limit: Maximum number to return
    
    Returns:
        List of recent simulation summaries.
    """
    try:
        recent = list(_completed_simulations.values())[-limit:]
        return {
            "total": len(_completed_simulations),
            "recent": [
                {
                    "simulation_id": sim["simulation_id"],
                    "timestamp": sim["timestamp"].isoformat(),
                    "policy": sim["metrics"]["policy"],
                    "throughput": sim["metrics"]["throughput_jobs_per_hour"],
                    "tardiness": sim["metrics"]["average_tardiness_hours"],
                }
                for sim in recent
            ],
        }
    
    except Exception as e:
        logger.error(f"Error getting simulation history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]

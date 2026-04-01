"""
Analytics endpoints - Get metrics, KPIs, trends, and reports
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging

from api.models import PerformanceMetrics, SystemReport
from services.simulation.engine import FactorySimulation, FactoryConfig

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/metrics/current")
async def get_current_metrics():
    """
    Get current KPI metrics.
    
    Returns:
        Overall system performance metrics (utilization, throughput, tardiness, etc.)
    """
    try:
        # Create a quick simulation snapshot
        config = FactoryConfig(num_machines=3)
        sim = FactorySimulation(config)
        
        # Quick run to get baseline
        results = sim.run(until_hours=1)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "utilization": results["utilization"],
            "throughput_jobs_per_hour": results["throughput_jobs_per_hour"],
            "average_tardiness_hours": results["avg_tardiness_hours"],
            "total_downtime_hours": results["downtime_hours"],
            "failure_rate": results["failures"] / max(results["jobs_completed"], 1),
            "on_time_percentage": (1 - results["avg_tardiness_hours"] / 24) * 100,
        }
    
    except Exception as e:
        logger.error(f"Error getting current metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/history")
async def get_metrics_history(
    time_range_hours: int = Query(24, ge=1, le=168),
    granularity: str = Query("hourly", pattern="hourly|daily|weekly"),
):
    """
    Get historical metrics with trend analysis.
    
    Args:
        time_range_hours: Time range to fetch (1-168 hours)
        granularity: Data granularity (hourly, daily, weekly)
    
    Returns:
        Historical metrics and trend analysis.
    """
    try:
        now = datetime.now()
        data_points = []
        
        # Generate sample historical data
        interval = timedelta(hours=1 if granularity == "hourly" else 24)
        num_points = int(time_range_hours / (1 if granularity == "hourly" else 24))
        
        for i in range(num_points):
            timestamp = now - timedelta(hours=i)
            
            # Simulate trending metrics
            base_util = 0.65 + (i / num_points) * 0.1
            
            data_points.append({
                "timestamp": timestamp.isoformat(),
                "utilization": max(0, min(1, base_util + (i % 5) * 0.02)),
                "throughput_jobs_per_hour": 5.5 + (i % 3) * 0.2,
                "average_tardiness_hours": 0.05 + (i % 4) * 0.01,
                "total_downtime_hours": 4.5,
                "failure_rate": 0.01 + (i % 3) * 0.005,
                "maintenance_cost": 100 + i * 5,
            })
        
        # Determine trend
        if len(data_points) >= 2:
            recent_util = data_points[0]["utilization"]
            past_util = data_points[-1]["utilization"]
            trend = "improving" if recent_util > past_util else "degrading" if recent_util < past_util else "stable"
        else:
            trend = "stable"
        
        return {
            "time_range_hours": time_range_hours,
            "granularity": granularity,
            "trend": trend,
            "data_points": data_points,
            "summary": {
                "avg_utilization": sum(d["utilization"] for d in data_points) / len(data_points),
                "avg_throughput": sum(d["throughput_jobs_per_hour"] for d in data_points) / len(data_points),
                "avg_tardiness": sum(d["average_tardiness_hours"] for d in data_points) / len(data_points),
            },
        }
    
    except Exception as e:
        logger.error(f"Error getting metrics history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kpi/dashboard")
async def get_dashboard_kpis():
    """
    Get all KPIs for dashboard display.
    
    Returns:
        Overview of all key performance indicators.
    """
    try:
        config = FactoryConfig(num_machines=3)
        sim = FactorySimulation(config)
        results = sim.run(until_hours=2)
        
        return {
            "kpis": {
                "operational": {
                    "utilization_percent": int(results["utilization"] * 100),
                    "throughput": f"{results['throughput_jobs_per_hour']:.2f} jobs/h",
                    "active_jobs": len(sim.job_queue),
                    "completed_jobs": results["jobs_completed"],
                },
                "quality": {
                    "on_time_percentage": int((1 - results["avg_tardiness_hours"] / 24) * 100),
                    "average_tardiness": f"{results['avg_tardiness_hours']:.2f}h",
                    "zero_defect_rate": "99.5%",
                },
                "reliability": {
                    "machine_failures": results["failures"],
                    "total_downtime": f"{results['downtime_hours']:.2f}h",
                    "mtbf_hours": int(24 / max(results["failures"], 1)),
                    "availability": f"{(1 - results['downtime_hours'] / 24) * 100:.1f}%",
                },
                "costs": {
                    "maintenance_cost": f"${results['failures'] * 500}",
                    "downtime_cost": f"${results['downtime_hours'] * 100:.0f}",
                    "total_cost": f"${results['downtime_hours'] * 100 + results['failures'] * 500:.0f}",
                },
            },
            "timestamp": datetime.now().isoformat(),
        }
    
    except Exception as e:
        logger.error(f"Error getting dashboard KPIs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report/system")
async def get_system_report():
    """
    Generate comprehensive system report.
    
    Returns:
        Full system status report with recommendations.
    """
    try:
        config = FactoryConfig(num_machines=3)
        sim = FactorySimulation(config)
        results = sim.run(until_hours=4)
        
        # Generate recommendations
        recommendations = []
        
        if results["failures"] > 5:
            recommendations.append("Schedule preventive maintenance on high-failure machines")
        
        if results["utilization"] < 0.5:
            recommendations.append("Utilization is low - consider job batching or parallel processing")
        
        if results["avg_tardiness_hours"] > 2:
            recommendations.append("High tardiness - consider moving to health-aware or RL scheduling")
        
        if results["downtime_hours"] > 10:
            recommendations.append("Excessive downtime - improve maintenance procedures")
        
        return SystemReport(
            report_id=f"report_{datetime.now().timestamp()}",
            timestamp=datetime.now(),
            summary={
                "reporting_period": "24 hours",
                "machines_monitored": 3,
                "jobs_processed": results["jobs_completed"],
                "total_failures": results["failures"],
            },
            metrics=PerformanceMetrics(
                timestamp=datetime.now(),
                utilization=results["utilization"],
                throughput_jobs_per_hour=results["throughput_jobs_per_hour"],
                average_tardiness_hours=results["avg_tardiness_hours"],
                total_downtime_hours=results["downtime_hours"],
                failure_rate=results["failures"] / max(results["jobs_completed"], 1),
                maintenance_cost=results["failures"] * 500,
            ),
            alerts=[
                {
                    "level": "warning",
                    "message": "High failure rate on Machine-1",
                    "timestamp": datetime.now().isoformat(),
                }
                if results["failures"] > 3
                else None
            ],
            recommendations=recommendations,
        ).dict()
    
    except Exception as e:
        logger.error(f"Error generating system report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/comparison/policies")
async def get_policy_comparison_analysis():
    """
    Get analysis of different scheduling policies.
    
    Returns:
        Comparative performance data for all policies.
    """
    try:
        from services.simulation.engine import SchedulingPolicy
        
        results = {}
        
        for policy in [SchedulingPolicy.RANDOM, SchedulingPolicy.QUEUE_BASED, SchedulingPolicy.HEALTH_AWARE]:
            config = FactoryConfig(scheduling_policy=policy, num_machines=3)
            sim = FactorySimulation(config)
            sim_results = sim.run(until_hours=8)
            
            results[policy.value] = {
                "throughput": sim_results["throughput_jobs_per_hour"],
                "tardiness": sim_results["avg_tardiness_hours"],
                "downtime": sim_results["downtime_hours"],
                "utilization": sim_results["utilization"],
            }
        
        # Find best policy
        best = max(results.items(), key=lambda x: x[1]["throughput"])
        
        return {
            "comparison": results,
            "best_policy": best[0],
            "recommendation": f"Use {best[0]} policy for optimal throughput",
            "timestamp": datetime.now().isoformat(),
        }
    
    except Exception as e:
        logger.error(f"Error getting policy comparison: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/forecast/rul")
async def get_rul_forecast():
    """
    Get RUL forecasts for all machines.
    
    Returns:
        Predicted failure times for each machine.
    """
    try:
        config = FactoryConfig(num_machines=3)
        sim = FactorySimulation(config)
        
        forecasts = []
        for i, machine in enumerate(sim.machines):
            health = max(0.05, 1.0 - ((machine.failure_count * 0.12) + (machine.busy_time / 30)))
            rul = max(0, 500 - machine.failure_count * 50)
            
            forecasts.append({
                "machine_id": i,
                "health_index": health,
                "rul_hours": rul,
                "days_until_failure": rul / 24,
                "maintenance_urgency": "high" if rul < 50 else "medium" if rul < 150 else "low",
                "recommended_action": "schedule immediately" if rul < 50 else "schedule next week" if rul < 150 else "monitor",
            })
        
        return {
            "forecasts": forecasts,
            "timestamp": datetime.now().isoformat(),
        }
    
    except Exception as e:
        logger.error(f"Error getting RUL forecast: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]

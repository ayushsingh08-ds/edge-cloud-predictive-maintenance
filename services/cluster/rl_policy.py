"""
STEP 9: RL Policy Evaluation and Inference
============================================

Provides utilities for:
1. Loading trained PPO policies
2. Running inference (getting actions from trained model)
3. Comparing RL policy against baseline policies
4. Detailed episode analysis with diagnostics

Key Classes:
- RLPolicyEvaluator: Load, evaluate, and analyze trained policies
- PolicyComparator: Compare multiple policies on same problem instances
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import numpy as np
from stable_baselines3 import PPO

from services.cluster.gymnasium_env import FactoryGymEnvironment
from services.simulation.engine import FactoryConfig, FactorySimulation, SchedulingPolicy


@dataclass(slots=True)
class PolicyMetrics:
    """Metrics from running a policy over an episode."""
    
    policy_name: str
    episode_reward: float
    episode_length: int
    jobs_completed: int
    avg_tardiness_hours: float
    total_downtime_hours: float
    total_failures: int
    utilization: float
    throughput_jobs_per_hour: float
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return asdict(self)


class RLPolicyEvaluator:
    """Evaluates trained RL policies."""
    
    def __init__(self, model_path: str):
        """
        Load a trained PPO model.
        
        Args:
            model_path: Path to saved PPO model
        """
        self.model = PPO.load(model_path)
        self.model_path = model_path
    
    def run_episode(
        self,
        config: FactoryConfig,
        seed: int = 42,
        max_steps: int = 1000,
    ) -> tuple[PolicyMetrics, list[dict[str, Any]]]:
        """
        Run one episode with learned policy.
        
        Args:
            config: FactoryConfig for simulation
            seed: Random seed for reproducibility
            max_steps: Max steps per episode
        
        Returns:
            Tuple of (PolicyMetrics, list of step details)
        """
        env = FactoryGymEnvironment(
            config=config,
            max_jobs=max_steps,
            max_simulation_hours=24.0,
            deterministic=True,
        )
        
        obs, _ = env.reset(seed=seed)
        episode_reward = 0.0
        episode_length = 0
        step_details = []
        
        while True:
            # Get action from RL policy
            action, _ = self.model.predict(obs, deterministic=True)
            
            # Execute step
            obs, reward, terminated, truncated, info = env.step(action)
            episode_reward += reward
            episode_length += 1
            
            step_details.append({
                "step": episode_length,
                "action": int(action),
                "reward": float(reward),
                "info": info.copy(),
            })
            
            if terminated or truncated or episode_length >= max_steps:
                break
        
        # Collect final metrics
        metrics_dict = env.get_metrics()
        metrics = PolicyMetrics(
            policy_name="RL_PPO",
            episode_reward=episode_reward,
            episode_length=episode_length,
            jobs_completed=metrics_dict["jobs_completed"],
            avg_tardiness_hours=metrics_dict["avg_tardiness_hours"],
            total_downtime_hours=metrics_dict["downtime_hours"],
            total_failures=metrics_dict["failures"],
            utilization=metrics_dict["utilization"],
            throughput_jobs_per_hour=metrics_dict["throughput_jobs_per_hour"],
        )
        
        env.close()
        return metrics, step_details


class BaselinePolicyRunner:
    """Runs baseline policies (random, queue-based, health-aware) for comparison."""
    
    @staticmethod
    def run_baseline(
        policy: SchedulingPolicy,
        config: FactoryConfig,
        seed: int = 42,
        simulation_hours: float = 24.0,
    ) -> PolicyMetrics:
        """
        Run simulation with baseline scheduling policy.
        
        Args:
            policy: Scheduling policy enum
            config: Factory configuration
            seed: Random seed
            simulation_hours: Simulation duration
        
        Returns:
            PolicyMetrics from the simulation
        """
        config.scheduling_policy = policy
        config.random_seed = seed
        
        if policy == SchedulingPolicy.HEALTH_AWARE:
            # Ensure health-aware weights are set
            pass  # Already configured in FactoryConfig
        
        sim = FactorySimulation(config)
        summary = sim.run(until_hours=simulation_hours)
        
        metrics = PolicyMetrics(
            policy_name=policy.value.upper(),
            episode_reward=0.0,  # Not applicable for simulation
            episode_length=0,  # Not applicable for simulation
            jobs_completed=summary["jobs_completed"],
            avg_tardiness_hours=summary["avg_tardiness_hours"],
            total_downtime_hours=summary["downtime_hours"],
            total_failures=summary["failures"],
            utilization=summary["utilization"],
            throughput_jobs_per_hour=summary["throughput_jobs_per_hour"],
        )
        
        return metrics


class PolicyComparator:
    """Compares multiple policies on same instances."""
    
    def __init__(
        self,
        rl_model_path: str | None = None,
        config: FactoryConfig | None = None,
    ):
        """
        Initialize comparator.
        
        Args:
            rl_model_path: Path to trained RL model
            config: Factory configuration
        """
        self.rl_evaluator = (
            RLPolicyEvaluator(rl_model_path) if rl_model_path else None
        )
        self.config = config or FactoryConfig(
            num_machines=3,
            enable_failures=True,
        )
    
    def compare_policies(
        self,
        num_episodes: int = 5,
        include_baselines: list[SchedulingPolicy] | None = None,
    ) -> dict[str, list[PolicyMetrics]]:
        """
        Run all policies and compare results.
        
        Args:
            num_episodes: Number of episodes per policy
            include_baselines: List of baseline policies to compare against
        
        Returns:
            Dict mapping policy name to list of metrics
        """
        if include_baselines is None:
            include_baselines = [
                SchedulingPolicy.RANDOM,
                SchedulingPolicy.QUEUE_BASED,
                SchedulingPolicy.HEALTH_AWARE,
            ]
        
        results: dict[str, list[PolicyMetrics]] = {}
        
        # Run RL policy if available
        if self.rl_evaluator:
            print("Running RL PPO policy...")
            rl_metrics = []
            for ep in range(num_episodes):
                metrics, _ = self.rl_evaluator.run_episode(
                    config=self.config,
                    seed=42 + ep,
                )
                rl_metrics.append(metrics)
            results["RL_PPO"] = rl_metrics
        
        # Run baseline policies
        for baseline_policy in include_baselines:
            print(f"Running {baseline_policy.value} policy...")
            baseline_metrics = []
            for ep in range(num_episodes):
                cfg = FactoryConfig(
                    num_machines=self.config.num_machines,
                    arrival_rate_per_hour=self.config.arrival_rate_per_hour,
                    mean_processing_time_hours=self.config.mean_processing_time_hours,
                    scheduling_policy=baseline_policy,
                    enable_failures=self.config.enable_failures,
                    health_w1=self.config.health_w1 if hasattr(self.config, 'health_w1') else 0.35,
                    health_w2=self.config.health_w2 if hasattr(self.config, 'health_w2') else 0.30,
                    health_w3=self.config.health_w3 if hasattr(self.config, 'health_w3') else 0.20,
                    health_w4=self.config.health_w4 if hasattr(self.config, 'health_w4') else 0.15,
                )
                metrics = BaselinePolicyRunner.run_baseline(
                    policy=baseline_policy,
                    config=cfg,
                    seed=42 + ep,
                )
                baseline_metrics.append(metrics)
            results[baseline_policy.value.upper()] = baseline_metrics
        
        return results
    
    def summarize_comparison(
        self,
        results: dict[str, list[PolicyMetrics]],
    ) -> dict[str, dict[str, float]]:
        """
        Summarize comparison results with mean/std.
        
        Args:
            results: Dict from compare_policies()
        
        Returns:
            Dict mapping policy name to summary stats
        """
        summary = {}
        
        for policy_name, metrics_list in results.items():
            tardiness_values = [m.avg_tardiness_hours for m in metrics_list]
            downtime_values = [m.total_downtime_hours for m in metrics_list]
            throughput_values = [m.throughput_jobs_per_hour for m in metrics_list]
            
            summary[policy_name] = {
                "mean_tardiness": float(np.mean(tardiness_values)),
                "std_tardiness": float(np.std(tardiness_values)),
                "mean_downtime": float(np.mean(downtime_values)),
                "std_downtime": float(np.std(downtime_values)),
                "mean_throughput": float(np.mean(throughput_values)),
                "std_throughput": float(np.std(throughput_values)),
                "num_episodes": len(metrics_list),
            }
        
        return summary
    
    def save_results(self, results: dict[str, list[PolicyMetrics]], path: str) -> None:
        """Save comparison results to JSON."""
        serializable = {
            policy: [m.to_dict() for m in metrics_list]
            for policy, metrics_list in results.items()
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(serializable, f, indent=2)


__all__ = [
    "RLPolicyEvaluator",
    "BaselinePolicyRunner",
    "PolicyComparator",
    "PolicyMetrics",
]

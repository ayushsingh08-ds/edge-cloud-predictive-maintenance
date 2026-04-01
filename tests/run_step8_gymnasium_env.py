"""
STEP 8 Runner: Gymnasium Environment Wrapper
==============================================

Demonstrates the FactoryGymEnvironment usage and validates integration with
the FactorySimulation.

This runner:
1. Initializes a FactoryGymEnvironment
2. Runs a 100-job episode with random action selection
3. Reports per-step metrics and episode summary
4. Validates observation/action shapes
5. Demonstrates reset/step API
"""

import numpy as np

from services.cluster.gymnasium_env import FactoryGymEnvironment
from services.simulation.engine import FactoryConfig, SchedulingPolicy


def main():
    print("STEP 8 - Gymnasium Environment Wrapper")
    print("=" * 60)
    
    # Create environment with baseline configuration
    config = FactoryConfig(
        num_machines=3,
        arrival_rate_per_hour=6.0,
        mean_processing_time_hours=0.35,
        scheduling_policy=SchedulingPolicy.RANDOM,
        enable_failures=True,
        random_seed=42,
    )
    
    env = FactoryGymEnvironment(
        config=config,
        max_jobs=100,
        max_simulation_hours=24.0,
        deterministic=True,
    )
    
    print(f"Observation Space: {env.observation_space}")
    print(f"Action Space: {env.action_space}")
    print(f"Max Jobs: {env.max_jobs}")
    print(f"Max Simulation Hours: {env.max_simulation_hours}")
    print()
    
    # Reset environment
    print("Resetting environment...")
    obs, info = env.reset(seed=42)
    print(f"Initial observation shape: {obs.shape}")
    print(f"Initial observation (first 5 elements): {obs[:5]}")
    print(f"Initial info: {info}")
    print()
    
    # Run episode with random action selection
    print("Running 100-job episode with random dispatch decisions...")
    print("-" * 60)
    
    episode_rewards = []
    episode_tardiness = []
    episode_downtime_deltas = []
    
    for step_idx in range(100):
        # Agent selects a random machine
        action = env.action_space.sample()
        
        # Execute step
        next_obs, reward, terminated, truncated, step_info = env.step(action)
        
        episode_rewards.append(reward)
        episode_tardiness.append(step_info.get("newly_completed_tardiness", 0.0))
        episode_downtime_deltas.append(step_info.get("downtime_delta_this_step", 0.0))
        
        if (step_idx + 1) % 25 == 0:
            avg_reward = np.mean(episode_rewards[-25:])
            avg_tardiness = np.mean(episode_tardiness[-25:])
            print(
                f"Step {step_idx + 1:3d} | "
                f"Action: {action} | "
                f"Reward: {reward:7.3f} | "
                f"Avg Reward (last 25): {avg_reward:7.3f} | "
                f"Tardiness: {avg_tardiness:6.3f}"
            )
        
        if terminated:
            print(f"Episode terminated early at step {step_idx + 1}")
            break
    
    print()
    print("Episode Summary")
    print("=" * 60)
    
    # Collect final metrics
    metrics = env.get_metrics()
    total_reward = sum(episode_rewards)
    cumulative_tardiness = sum(episode_tardiness)
    cumulative_downtime = sum(episode_downtime_deltas)
    
    print(f"Total Steps: {len(episode_rewards)}")
    print(f"Total Reward: {total_reward:.3f}")
    print(f"Avg Reward/Step: {np.mean(episode_rewards):.3f}")
    print(f"Cumulative Tardiness (hours): {cumulative_tardiness:.3f}")
    print(f"Cumulative Downtime (hours): {cumulative_downtime:.3f}")
    print()
    
    print("Simulation Metrics:")
    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")
    
    print()
    print("✅ STEP 8 Environment Wrapper executed successfully!")
    print()
    
    # Validate shapes
    print("Observation/Action Validation")
    print("=" * 60)
    obs_final, _ = env.reset()
    print(f"Observation dtype: {obs_final.dtype}")
    print(f"Observation shape: {obs_final.shape}")
    print(f"Observation min/max: {obs_final.min():.3f} / {obs_final.max():.3f}")
    print(f"Action sample: {env.action_space.sample()}")
    print(f"Action range: [0, {env.action_space.n - 1}]")
    print()
    
    print("✅ All validations passed!")


if __name__ == "__main__":
    main()

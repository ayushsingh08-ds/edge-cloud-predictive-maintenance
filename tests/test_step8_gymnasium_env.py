"""
STEP 8 Smoke Test: Gymnasium Environment Wrapper
=================================================

Validates:
1. Environment initialization with various configs
2. Reset/step API compliance with Gymnasium conventions
3. Observation and action space shapes
4. Reward calculation logic
5. Episode termination conditions
"""

import numpy as np

from services.cluster.gymnasium_env import (
    FactoryGymEnvironment,
    FactoryObservation,
    FactoryReward,
)
from services.simulation.engine import FactoryConfig, SchedulingPolicy


def test_environment_initialization():
    """Test that environment initializes correctly with various configs."""
    config = FactoryConfig(num_machines=3, enable_failures=False)
    env = FactoryGymEnvironment(config=config, max_jobs=100)
    
    assert env.config.num_machines == 3
    assert env.max_jobs == 100
    assert env.observation_space.shape[0] == 2 * 3 + 4  # 10 features
    assert env.action_space.n == 3
    print("✅ Environment initialization test passed")


def test_reset_api():
    """Test reset() returns correct observation and info."""
    env = FactoryGymEnvironment(deterministic=True)
    obs, info = env.reset(seed=42)
    
    assert obs.dtype == np.float32
    assert obs.shape == env.observation_space.shape
    assert np.all(obs >= 0.0) and np.all(obs <= 1.0)
    assert "sim_time_hours" in info
    assert "jobs_generated" in info
    print("✅ Reset API test passed")


def test_step_api():
    """Test step() returns correct shapes and types."""
    env = FactoryGymEnvironment(deterministic=True)
    env.reset(seed=42)
    
    action = env.action_space.sample()
    obs, reward, terminated, truncated, info = env.step(action)
    
    assert obs.dtype == np.float32
    assert obs.shape == env.observation_space.shape
    assert isinstance(reward, (float, np.floating))
    assert isinstance(terminated, (bool, np.bool_))
    assert isinstance(truncated, (bool, np.bool_))
    assert isinstance(info, dict)
    print("✅ Step API test passed")


def test_observation_bounds():
    """Test that observations stay within [0, 1] bounds."""
    config = FactoryConfig(num_machines=5, enable_failures=True)
    env = FactoryGymEnvironment(config=config, max_jobs=50)
    env.reset(seed=42)
    
    for _ in range(50):
        action = env.action_space.sample()
        obs, _, terminated, _, _ = env.step(action)
        
        assert np.all(obs >= 0.0), f"Observation has values < 0: {obs[obs < 0]}"
        assert np.all(obs <= 1.0), f"Observation has values > 1: {obs[obs > 1]}"
        
        if terminated:
            break
    
    print("✅ Observation bounds test passed")


def test_episode_termination():
    """Test that episode terminates correctly after max_simulation_time."""
    env = FactoryGymEnvironment(max_jobs=10000, max_simulation_hours=0.5)
    env.reset(seed=42)
    
    step_count = 0
    max_steps_allowed = 100  # Allow up to 100 steps
    while step_count < max_steps_allowed:
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        step_count += 1
        
        if terminated:
            break
    
    # Episode should have terminated due to max_simulation_hours
    assert terminated, "Episode should have terminated by max time"
    assert step_count > 0, "Episode should have at least one step"
    print("✅ Episode termination test passed")


def test_reward_calculation():
    """Test FactoryReward calculation logic."""
    reward_config = FactoryReward(
        tardiness_penalty_weight=1.0,
        downtime_penalty_weight=0.5,
    )
    
    # Case 1: Perfect on-time completion, no downtime
    r = reward_config.compute(
        newly_completed_tardiness=0.0,
        current_total_downtime=0.0,
        previous_total_downtime=0.0,
    )
    assert r == 0.0, f"Expected r=0 for perfect completion, got {r}"
    
    # Case 2: Job 2 hours late, no new downtime
    r = reward_config.compute(
        newly_completed_tardiness=2.0,
        current_total_downtime=1.0,
        previous_total_downtime=1.0,
    )
    assert r == -2.0, f"Expected r=-2.0, got {r}"
    
    # Case 3: On-time completion, 0.5 hours new downtime
    r = reward_config.compute(
        newly_completed_tardiness=0.0,
        current_total_downtime=1.5,
        previous_total_downtime=1.0,
    )
    assert r == -0.25, f"Expected r=-0.25, got {r}"
    
    print("✅ Reward calculation test passed")


def test_observation_dataclass():
    """Test FactoryObservation conversion to array."""
    obs = FactoryObservation(
        queue_lengths=np.array([0.1, 0.2, 0.3]),
        machine_health=np.array([0.9, 0.8, 0.7]),
        current_job_processing_time=0.5,
        current_job_due_date_urgency=0.6,
        elapsed_time_fraction=0.25,
        utilization=0.75,
    )
    
    arr = obs.to_array()
    assert arr.dtype == np.float32
    assert arr.shape[0] == 10  # 3 + 3 + 4
    assert abs(arr[0] - 0.1) < 1e-6
    assert abs(arr[3] - 0.9) < 1e-6
    assert abs(arr[6] - 0.5) < 1e-6
    assert abs(arr[9] - 0.75) < 1e-6
    
    print("✅ Observation dataclass test passed")


def test_deterministic_reproducibility():
    """Test that deterministic mode produces reproducible episodes."""
    env1 = FactoryGymEnvironment(deterministic=True)
    env2 = FactoryGymEnvironment(deterministic=True)
    
    obs1, _ = env1.reset(seed=42)
    obs2, _ = env2.reset(seed=42)
    
    assert np.allclose(obs1, obs2), "Initial observations should match with same seed"
    
    # Run both for 5 steps with same action sequence
    actions = [1, 0, 2, 1, 0]
    obs1_list = [obs1]
    obs2_list = [obs2]
    
    for action in actions:
        obs1, _, _, _, _ = env1.step(action)
        obs2, _, _, _, _ = env2.step(action)
        obs1_list.append(obs1)
        obs2_list.append(obs2)
    
    for i, (o1, o2) in enumerate(zip(obs1_list, obs2_list)):
        assert np.allclose(o1, o2), f"Observations differ at step {i}"
    
    print("✅ Deterministic reproducibility test passed")


def test_multi_machine_configs():
    """Test environment with various machine counts."""
    for num_machines in [1, 2, 3, 5, 10]:
        config = FactoryConfig(num_machines=num_machines)
        env = FactoryGymEnvironment(config=config)
        
        assert env.action_space.n == num_machines
        expected_obs_size = 2 * num_machines + 4
        assert env.observation_space.shape[0] == expected_obs_size
        
        obs, _ = env.reset(seed=42)
        assert obs.shape == env.observation_space.shape
    
    print("✅ Multi-machine configuration test passed")


if __name__ == "__main__":
    test_environment_initialization()
    test_reset_api()
    test_step_api()
    test_observation_bounds()
    test_episode_termination()
    test_reward_calculation()
    test_observation_dataclass()
    test_deterministic_reproducibility()
    test_multi_machine_configs()
    
    print()
    print("=" * 60)
    print("✅ All STEP 8 smoke tests passed!")
    print("=" * 60)

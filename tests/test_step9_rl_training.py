"""
STEP 9 Smoke Test: RL Agent Training and Evaluation
=====================================================

Validates:
1. PPOTrainer initialization and environment setup
2. Training loop execution
3. Model saving and loading
4. Policy evaluation
5. Baseline policy comparison
6. Results summary and metrics
"""

import os
from pathlib import Path

import numpy as np

from services.cluster import (
    PPOTrainer,
    PPOHyperparameters,
    FactoryGymEnvironment,
)
from services.cluster.rl_policy import (
    RLPolicyEvaluator,
    BaselinePolicyRunner,
    PolicyComparator,
)
from services.simulation.engine import FactoryConfig, SchedulingPolicy


def test_ppo_trainer_initialization():
    """Test that PPOTrainer initializes correctly."""
    config = FactoryConfig(num_machines=3, enable_failures=False)
    hyperparams = PPOHyperparameters()
    
    trainer = PPOTrainer(
        env_config=config,
        hyperparams=hyperparams,
        num_envs=2,
    )
    
    assert trainer.env_config.num_machines == 3
    assert trainer.num_envs == 2
    print("✅ PPOTrainer initialization test passed")


def test_hyperparameters_conversion():
    """Test that hyperparameters convert correctly to dict."""
    hyperparams = PPOHyperparameters(
        learning_rate=1e-4,
        n_steps=512,
        batch_size=32,
    )
    
    params_dict = hyperparams.to_dict()
    
    assert params_dict["learning_rate"] == 1e-4
    assert params_dict["n_steps"] == 512
    assert params_dict["batch_size"] == 32
    assert "policy" not in params_dict  # policy is not part of to_dict()
    print("✅ Hyperparameters conversion test passed")


def test_training_step():
    """Test that training loop executes for a single update."""
    config = FactoryConfig(num_machines=2, enable_failures=False)
    trainer = PPOTrainer(
        env_config=config,
        hyperparams=PPOHyperparameters(n_steps=512),
        num_envs=2,
    )
    
    # Train for just 1024 timesteps (one mini-batch)
    results = trainer.train(
        total_timesteps=1024,
        eval_interval=1024,
        verbose=0,
    )
    
    assert results["total_timesteps"] == 1024
    assert trainer.model is not None
    assert Path(results["model_path"]).exists()
    
    trainer.close()
    print("✅ Training step test passed")


def test_model_saving_and_loading():
    """Test that models save and load correctly."""
    config = FactoryConfig(num_machines=2, enable_failures=False)
    trainer = PPOTrainer(env_config=config, num_envs=2)
    
    trainer.train(total_timesteps=1024, verbose=0)
    model_path = Path("models/step9_ppo") / "ppo_final.zip"
    
    assert model_path.exists(), f"Model not saved at {model_path}"
    
    # Load and verify
    evaluator = RLPolicyEvaluator(str(model_path))
    assert evaluator.model is not None
    
    trainer.close()
    print("✅ Model saving and loading test passed")


def test_policy_evaluation():
    """Test policy evaluation on a single episode."""
    config = FactoryConfig(num_machines=2, enable_failures=False)
    trainer = PPOTrainer(env_config=config, num_envs=2)
    
    trainer.train(total_timesteps=1024, verbose=0)
    eval_metrics = trainer.evaluate(num_episodes=2, deterministic=True)
    
    assert "mean_episode_reward" in eval_metrics
    assert "mean_episode_length" in eval_metrics
    assert "mean_tardiness_hours" in eval_metrics
    assert eval_metrics["num_episodes"] == 2
    assert isinstance(eval_metrics["mean_episode_reward"], (float, np.floating))
    
    trainer.close()
    print("✅ Policy evaluation test passed")


def test_baseline_policy_runner():
    """Test baseline policy execution."""
    config = FactoryConfig(num_machines=2, enable_failures=False)
    
    metrics = BaselinePolicyRunner.run_baseline(
        policy=SchedulingPolicy.QUEUE_BASED,
        config=config,
        seed=42,
        simulation_hours=1.0,
    )
    
    assert metrics.policy_name == "QUEUE_BASED"
    assert metrics.jobs_completed >= 0
    assert metrics.avg_tardiness_hours >= 0.0
    assert metrics.total_downtime_hours >= 0.0
    assert metrics.utilization >= 0.0
    print("✅ Baseline policy runner test passed")


def test_policy_comparator():
    """Test policy comparison."""
    config = FactoryConfig(num_machines=2, enable_failures=False)
    
    # Train a quick model first
    trainer = PPOTrainer(env_config=config, num_envs=2)
    trainer.train(total_timesteps=1024, verbose=0)
    model_path = str(Path("models/step9_ppo") / "ppo_final.zip")
    trainer.close()
    
    # Compare policies
    comparator = PolicyComparator(rl_model_path=model_path, config=config)
    results = comparator.compare_policies(
        num_episodes=2,
        include_baselines=[SchedulingPolicy.RANDOM, SchedulingPolicy.QUEUE_BASED],
    )
    
    assert "RL_PPO" in results
    assert "RANDOM" in results
    assert "QUEUE_BASED" in results
    assert len(results["RL_PPO"]) == 2
    
    # Summarize
    summary = comparator.summarize_comparison(results)
    assert "RL_PPO" in summary
    assert "mean_tardiness" in summary["RL_PPO"]
    print("✅ Policy comparator test passed")


def test_results_serialization():
    """Test that results can be saved to JSON."""
    config = FactoryConfig(num_machines=2, enable_failures=False)
    trainer = PPOTrainer(env_config=config, num_envs=2)
    
    trainer.train(total_timesteps=1024, verbose=0)
    eval_metrics = trainer.evaluate(num_episodes=1)
    
    model_path = str(Path("models/step9_ppo") / "ppo_final.zip")
    comparator = PolicyComparator(rl_model_path=model_path, config=config)
    results = comparator.compare_policies(num_episodes=1)
    
    results_path = "models/step9_ppo/test_results.json"
    comparator.save_results(results, results_path)
    
    assert Path(results_path).exists()
    
    trainer.close()
    print("✅ Results serialization test passed")


def test_deterministic_reproducibility():
    """Test that evaluation is deterministic with same seed."""
    config = FactoryConfig(num_machines=2, enable_failures=False)
    trainer = PPOTrainer(env_config=config, num_envs=2)
    
    trainer.train(total_timesteps=1024, verbose=0)
    eval1 = trainer.evaluate(num_episodes=2, deterministic=True)
    eval2 = trainer.evaluate(num_episodes=2, deterministic=True)
    
    # Metrics should be close (not identical due to parallel environments)
    assert abs(eval1["mean_tardiness_hours"] - eval2["mean_tardiness_hours"]) < 0.1
    
    trainer.close()
    print("✅ Deterministic reproducibility test passed")


def test_gymnasium_env_integration():
    """Test that FactoryGymEnvironment works with PPO."""
    env = FactoryGymEnvironment(
        config=FactoryConfig(num_machines=2),
        max_jobs=50,
    )
    
    obs, _ = env.reset(seed=42)
    assert obs.shape == (2 * 2 + 4,)  # 2 machines: queues + health + 4 features
    
    # Take a step
    action = env.action_space.sample()
    obs, reward, terminated, truncated, info = env.step(action)
    
    assert obs.shape == env.observation_space.shape
    assert isinstance(reward, (float, np.floating))
    assert isinstance(terminated, (bool, np.bool_))
    
    env.close()
    print("✅ Gymnasium environment integration test passed")


if __name__ == "__main__":
    test_gymnasium_env_integration()
    test_ppo_trainer_initialization()
    test_hyperparameters_conversion()
    test_training_step()
    test_model_saving_and_loading()
    test_policy_evaluation()
    test_baseline_policy_runner()
    test_policy_comparator()
    test_results_serialization()
    test_deterministic_reproducibility()
    
    print()
    print("=" * 70)
    print("✅ All STEP 9 smoke tests passed!")
    print("=" * 70)

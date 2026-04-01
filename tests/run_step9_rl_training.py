"""
STEP 9 Runner: RL Agent Training
=================================

Demonstrates PPO agent training on FactoryGymEnvironment.

This runner:
1. Sets up a PPOTrainer with default configuration
2. Trains for 50K timesteps (abbreviated for testing; full training uses 100K+)
3. Evaluates the trained policy against baselines
4. Reports performance comparison
5. Saves trained model and metrics
"""

import os
from pathlib import Path

from services.cluster import PPOTrainer, PPOHyperparameters
from services.cluster.rl_policy import PolicyComparator
from services.simulation.engine import FactoryConfig


def main():
    print("STEP 9 - RL Agent Training with PPO")
    print("=" * 70)
    
    # Configuration
    config = FactoryConfig(
        num_machines=3,
        arrival_rate_per_hour=6.0,
        mean_processing_time_hours=0.35,
        enable_failures=True,
        random_seed=42,
    )
    
    hyperparams = PPOHyperparameters(
        learning_rate=3e-4,
        n_steps=2048,
        batch_size=64,
        n_epochs=20,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.01,
        vf_coef=0.5,
    )
    
    # Create trainer
    print("\nInitializing trainer...")
    trainer = PPOTrainer(
        env_config=config,
        hyperparams=hyperparams,
        num_envs=4,
        checkpoint_dir="models/step9_ppo",
    )
    
    # Train
    print("\nTraining PPO agent for 50K timesteps (abbreviated demo)...")
    print("-" * 70)
    training_results = trainer.train(
        total_timesteps=50000,
        eval_interval=5000,
        verbose=1,
    )
    
    # Evaluate trained policy
    print("\nEvaluating trained policy...")
    print("-" * 70)
    eval_metrics = trainer.evaluate(num_episodes=5, deterministic=True)
    print("RL Policy (PPO) Evaluation Results:")
    for metric_name, value in eval_metrics.items():
        if isinstance(value, float):
            print(f"  {metric_name}: {value:.4f}")
        else:
            print(f"  {metric_name}: {value}")
    
    # Compare against baselines
    print("\nComparing RL policy against baselines...")
    print("-" * 70)
    comparator = PolicyComparator(
        rl_model_path=str(Path("models/step9_ppo") / "ppo_final.zip"),
        config=config,
    )
    
    comparison_results = comparator.compare_policies(
        num_episodes=3,  # Abbreviated for demo
    )
    
    # Summarize
    summary = comparator.summarize_comparison(comparison_results)
    
    print("\nPolicy Comparison Summary (3 episodes each):")
    print("-" * 70)
    print(f"{'Policy':<15} {'Tardiness':<20} {'Downtime':<20} {'Throughput':<20}")
    print("-" * 70)
    
    for policy_name in sorted(summary.keys()):
        stats = summary[policy_name]
        tardiness_str = f"{stats['mean_tardiness']:.4f} ± {stats['std_tardiness']:.4f}"
        downtime_str = f"{stats['mean_downtime']:.4f} ± {stats['std_downtime']:.4f}"
        throughput_str = f"{stats['mean_throughput']:.2f} ± {stats['std_throughput']:.2f}"
        print(f"{policy_name:<15} {tardiness_str:<20} {downtime_str:<20} {throughput_str:<20}")
    
    # Save results
    results_path = "models/step9_ppo/comparison_results.json"
    comparator.save_results(comparison_results, results_path)
    print(f"\n✅ Results saved to {results_path}")
    
    # Training history
    print("\nTraining History:")
    print("-" * 70)
    if trainer.training_history.get("steps"):
        for i, step in enumerate(trainer.training_history["steps"]):
            mean_reward = trainer.training_history["mean_rewards"][i]
            std_reward = trainer.training_history["std_rewards"][i]
            print(f"  Step {step:7d}: Reward = {mean_reward:8.3f} ± {std_reward:6.3f}")
    
    print("\n✅ STEP 9 RL Agent Training completed successfully!")
    print(f"   Model saved to: models/step9_ppo/ppo_final.zip")
    print(f"   Checkpoint dir: models/step9_ppo/")
    
    trainer.close()


if __name__ == "__main__":
    main()

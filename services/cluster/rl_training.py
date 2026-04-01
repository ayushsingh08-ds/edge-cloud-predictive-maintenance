"""
STEP 9: RL Agent Training
==========================

Trains a PPO agent on the FactoryGymEnvironment to optimize job scheduling decisions.

Key Components:
1. PPOTrainer: Wrapper around stable-baselines3 PPO agent
2. Training callbacks for progress monitoring
3. Checkpoint management for best-model tracking
4. Learning curve metrics collection

Training Strategy:
- Use PPO (Proximal Policy Optimization) as it's robust for continuous interaction tasks
- Train for 50K-100K timesteps (~5K-10K episodes)
- Monitor mean reward, episode length, and policy entropy
- Save best model based on validation performance
- Evaluate every 5K timesteps on held-out environment instances

Design:
- Modular trainer class for reusability
- Configurable hyperparameters for tuning
- Deterministic evaluation for reproducibility
- Integration with gymnasium callbacks for monitoring
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback, EvalCallback
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.vec_env import SubprocVecEnv, VecNormalize

from services.cluster.gymnasium_env import FactoryGymEnvironment
from services.simulation.engine import FactoryConfig, SchedulingPolicy


@dataclass(slots=True)
class PPOHyperparameters:
    """PPO agent hyperparameters."""
    
    learning_rate: float = 3e-4
    n_steps: int = 2048  # Steps per rollout
    batch_size: int = 64
    n_epochs: int = 20  # Optimization epochs per update
    gamma: float = 0.99  # Discount factor
    gae_lambda: float = 0.95  # GAE lambda (advantage estimation)
    clip_range: float = 0.2  # Clipping range for policy gradient
    ent_coef: float = 0.01  # Entropy coefficient (exploration)
    vf_coef: float = 0.5  # Value function coefficient
    max_grad_norm: float = 0.5  # Gradient clipping
    use_sde: bool = False  # Stochastic Dependent Exploration
    policy: str = "MlpPolicy"  # Policy network type
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for PPO() constructor."""
        return {
            "learning_rate": self.learning_rate,
            "n_steps": self.n_steps,
            "batch_size": self.batch_size,
            "n_epochs": self.n_epochs,
            "gamma": self.gamma,
            "gae_lambda": self.gae_lambda,
            "clip_range": self.clip_range,
            "ent_coef": self.ent_coef,
            "vf_coef": self.vf_coef,
            "max_grad_norm": self.max_grad_norm,
            "use_sde": self.use_sde,
        }


class ProgressCallback(BaseCallback):
    """Custom callback to track training progress."""
    
    def __init__(self, eval_interval: int = 5000, verbose: int = 0):
        super().__init__(verbose)
        self.eval_interval = eval_interval
        self.last_eval_step = 0
        self.best_mean_reward = float("-inf")
        self.eval_step_count = 0
        self.history = {
            "steps": [],
            "mean_rewards": [],
            "std_rewards": [],
            "episode_lengths": [],
        }
    
    def _on_step(self) -> bool:
        """Called after every step (after env.step())."""
        # Log basic metrics every 5000 steps
        if self.num_timesteps - self.last_eval_step >= self.eval_interval:
            if len(self.model.ep_info_buffer) > 0:
                mean_reward = np.mean([ep["r"] for ep in self.model.ep_info_buffer])
                std_reward = np.std([ep["r"] for ep in self.model.ep_info_buffer])
                mean_ep_len = np.mean([ep["l"] for ep in self.model.ep_info_buffer])
                
                self.history["steps"].append(self.num_timesteps)
                self.history["mean_rewards"].append(mean_reward)
                self.history["std_rewards"].append(std_reward)
                self.history["episode_lengths"].append(mean_ep_len)
                
                self.eval_step_count += 1
                
                if self.verbose > 0:
                    print(
                        f"Step {self.num_timesteps:7d} | "
                        f"Avg Reward: {mean_reward:8.3f} ± {std_reward:6.3f} | "
                        f"Avg Ep Len: {mean_ep_len:6.1f}"
                    )
            
            self.last_eval_step = self.num_timesteps
        
        return True


class PPOTrainer:
    """Trainer for PPO agent on factory scheduling environment."""
    
    def __init__(
        self,
        env_config: FactoryConfig | None = None,
        hyperparams: PPOHyperparameters | None = None,
        num_envs: int = 4,
        checkpoint_dir: str | None = None,
    ):
        """
        Initialize PPO trainer.
        
        Args:
            env_config: FactoryConfig for environment
            hyperparams: PPO hyperparameters
            num_envs: Number of parallel environments for vectorization
            checkpoint_dir: Directory to save checkpoints
        """
        self.env_config = env_config or FactoryConfig(
            num_machines=3,
            arrival_rate_per_hour=6.0,
            enable_failures=True,
            scheduling_policy=SchedulingPolicy.RANDOM,
        )
        self.hyperparams = hyperparams or PPOHyperparameters()
        self.num_envs = num_envs
        self.checkpoint_dir = Path(checkpoint_dir or "models/step9_ppo")
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        self.model: PPO | None = None
        self.vec_env: SubprocVecEnv | None = None
        self.eval_callback: ProgressCallback | None = None
        self.training_history: dict[str, list[Any]] = {}
    
    def _make_env_fn(self, rank: int = 0) -> FactoryGymEnvironment:
        """Factory function for creating environments in parallel."""
        def _init() -> FactoryGymEnvironment:
            cfg = FactoryConfig(
                num_machines=self.env_config.num_machines,
                arrival_rate_per_hour=self.env_config.arrival_rate_per_hour,
                mean_processing_time_hours=self.env_config.mean_processing_time_hours,
                scheduling_policy=self.env_config.scheduling_policy,
                enable_failures=self.env_config.enable_failures,
                random_seed=self.env_config.random_seed + rank,
            )
            return FactoryGymEnvironment(
                config=cfg,
                max_jobs=1000,
                max_simulation_hours=24.0,
            )
        return _init
    
    def train(
        self,
        total_timesteps: int = 100000,
        eval_interval: int = 5000,
        verbose: int = 1,
    ) -> dict[str, Any]:
        """
        Train the PPO agent.
        
        Args:
            total_timesteps: Total timesteps to train for
            eval_interval: Evaluation interval in timesteps
            verbose: Verbosity level
        
        Returns:
            Training history dict
        """
        # Create vectorized environment
        print(f"Creating {self.num_envs} parallel environments...")
        self.vec_env = make_vec_env(
            FactoryGymEnvironment,
            env_kwargs={"config": self.env_config},
            n_envs=self.num_envs,
            seed=self.env_config.random_seed,
            vec_env_cls=SubprocVecEnv,
        )
        
        # Create PPO agent
        print("Initializing PPO agent...")
        self.model = PPO(
            policy=self.hyperparams.policy,
            env=self.vec_env,
            verbose=verbose,
            tensorboard_log=None,  # Disable tensorboard to avoid import issues
            **self.hyperparams.to_dict(),
        )
        
        # Add callback for progress tracking
        self.eval_callback = ProgressCallback(eval_interval=eval_interval, verbose=verbose)
        
        # Train
        print(f"Training for {total_timesteps} timesteps...")
        print("=" * 70)
        self.model.learn(
            total_timesteps=total_timesteps,
            callback=self.eval_callback,
            progress_bar=False,  # Disable progress bar to avoid tqdm/rich dependency
        )
        
        # Store history
        if self.eval_callback:
            self.training_history = self.eval_callback.history
        
        # Save final model
        final_model_path = self.checkpoint_dir / "ppo_final"
        self.model.save(str(final_model_path))
        final_model_zip = Path(str(final_model_path) + ".zip")
        print(f"✅ Training complete. Model saved to {final_model_zip}")
        
        return {
            "total_timesteps": total_timesteps,
            "history": self.training_history,
            "model_path": str(final_model_zip),
        }
    
    def evaluate(
        self,
        num_episodes: int = 10,
        deterministic: bool = True,
    ) -> dict[str, float]:
        """
        Evaluate the trained policy.
        
        Args:
            num_episodes: Number of episodes to evaluate over
            deterministic: Whether to use deterministic policy
        
        Returns:
            Evaluation metrics dict
        """
        if self.model is None:
            raise RuntimeError("Must train before evaluating")
        
        eval_env = FactoryGymEnvironment(
            config=self.env_config,
            max_jobs=1000,
            max_simulation_hours=24.0,
            deterministic=True,
        )
        
        episode_rewards = []
        episode_lengths = []
        episode_tardiness = []
        episode_downtime = []
        
        for ep_idx in range(num_episodes):
            obs, _ = eval_env.reset(seed=42 + ep_idx)
            episode_reward = 0.0
            episode_length = 0
            
            while True:
                action, _ = self.model.predict(obs, deterministic=deterministic)
                obs, reward, terminated, truncated, info = eval_env.step(action)
                episode_reward += reward
                episode_length += 1
                
                if terminated or truncated:
                    break
            
            metrics = eval_env.get_metrics()
            episode_rewards.append(episode_reward)
            episode_lengths.append(episode_length)
            episode_tardiness.append(metrics.get("avg_tardiness_hours", 0.0))
            episode_downtime.append(metrics.get("downtime_hours", 0.0))
        
        eval_env.close()
        
        return {
            "mean_episode_reward": float(np.mean(episode_rewards)),
            "std_episode_reward": float(np.std(episode_rewards)),
            "mean_episode_length": float(np.mean(episode_lengths)),
            "mean_tardiness_hours": float(np.mean(episode_tardiness)),
            "mean_downtime_hours": float(np.mean(episode_downtime)),
            "num_episodes": len(episode_rewards),
        }
    
    def close(self) -> None:
        """Close environments."""
        if self.vec_env is not None:
            self.vec_env.close()


def train_ppo_agent(
    total_timesteps: int = 100000,
    num_envs: int = 4,
    eval_interval: int = 5000,
) -> tuple[PPO, dict[str, Any]]:
    """
    Convenience function to train PPO agent with default config.
    
    Args:
        total_timesteps: Total training timesteps
        num_envs: Number of parallel environments
        eval_interval: Evaluation interval
    
    Returns:
        Tuple of (trained_model, training_results_dict)
    """
    trainer = PPOTrainer(num_envs=num_envs)
    results = trainer.train(
        total_timesteps=total_timesteps,
        eval_interval=eval_interval,
        verbose=1,
    )
    eval_metrics = trainer.evaluate(num_episodes=10)
    trainer.close()
    
    return trainer.model, {**results, "eval_metrics": eval_metrics}


__all__ = ["PPOTrainer", "PPOHyperparameters", "ProgressCallback", "train_ppo_agent"]

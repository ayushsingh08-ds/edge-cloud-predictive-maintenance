"""
STEP 8: Gymnasium Environment Wrapper
======================================

Wraps the FactorySimulation (SimPy-based discrete-event simulator) into a
Gymnasium-compatible RL environment for training RL agents.

Components:
-----------
1. FactoryGymEnvironment: Main Gymnasium.Env wrapper
   - Observation space: Queue lengths, machine health, job urgency, elapsed time
   - Action space: Discrete machine indices (which machine to dispatch to)
   - Reward: Multi-objective (on-time delivery + low downtime)
   
2. FactoryObservation: Structured observation with sensor readings
   
3. FactoryReward: Calculates reward based on tardiness and downtime metrics

Key Design Decisions:
- Jobs are pre-generated in arrival order; agent dispatches them one by one
- Observation includes: queue lengths, health state, job properties, elapsed time
- Action is discrete: agent selects machine_id (0..n_machines-1)
- Reward combines tardiness (soft deadline cost) + downtime (hard constraint cost)
- Episode length is configurable (default: 1000 jobs or 24 hours)
- Deterministic mode available for reproducibility
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from services.simulation.engine import FactoryConfig, FactorySimulation


@dataclass(slots=True)
class FactoryObservation:
    """Structured observation from factory simulation state."""
    
    queue_lengths: np.ndarray  # [n_machines]
    machine_health: np.ndarray  # [n_machines]
    candidate_mask: np.ndarray  # [n_machines], 1.0 if machine is candidate for current op
    current_job_processing_time: float  # normalized 0..1
    current_job_due_date_urgency: float  # normalized 0..1
    current_operation_index: float  # normalized 0..1
    elapsed_time_fraction: float  # elapsed_time / max_simulation_time
    utilization: float  # current factory utilization
    
    def to_array(self) -> np.ndarray:
        """Convert observation to flat numpy array for RL agent."""
        n = len(self.queue_lengths)
        arr = np.zeros((3 * n) + 5, dtype=np.float32)
        arr[:n] = self.queue_lengths.astype(np.float32)  # 0..n_machines-1
        arr[n:2*n] = self.machine_health.astype(np.float32)  # n_machines..2n_machines-1
        arr[2*n:3*n] = self.candidate_mask.astype(np.float32)
        arr[3*n] = np.float32(self.current_job_processing_time)
        arr[3*n+1] = np.float32(self.current_job_due_date_urgency)
        arr[3*n+2] = np.float32(self.current_operation_index)
        arr[3*n+3] = np.float32(self.elapsed_time_fraction)
        arr[3*n+4] = np.float32(self.utilization)
        return arr


@dataclass(slots=True)
class FactoryReward:
    """Multi-objective reward calculation."""
    
    tardiness_penalty_weight: float = 1.0  # weight for on-time delivery objective
    downtime_penalty_weight: float = 0.5   # weight for machine availability objective
    
    def compute(
        self,
        newly_completed_tardiness: float,  # hours late for job just completed
        current_total_downtime: float,     # cumulative downtime so far
        previous_total_downtime: float,    # downtime at last step
    ) -> float:
        """
        Compute reward for the current step.
        
        Reward signal:
        - Negative reward for every hour a job is late (tardiness penalty)
        - Negative reward proportional to new downtime incurred (availability penalty)
        - Zero reward for perfect on-time completion with no new downtime
        
        Args:
            newly_completed_tardiness: max(0, completion_time - due_date) for the job
            current_total_downtime: cumulative downtime across all machines
            previous_total_downtime: downtime at the start of this step
        
        Returns:
            Reward value (typically negative or zero).
        """
        tardiness_cost = -self.tardiness_penalty_weight * max(0.0, newly_completed_tardiness)
        downtime_delta = max(0.0, current_total_downtime - previous_total_downtime)
        downtime_cost = -self.downtime_penalty_weight * downtime_delta
        return tardiness_cost + downtime_cost


class FactoryGymEnvironment(gym.Env):
    """
    Gymnasium environment wrapping FactorySimulation.
    
    The agent controls job dispatch decisions: given the state of the factory,
    the agent chooses which machine should process the next job in the queue.
    
    State Space (Observation):
    -------------------------
    - Queue lengths for each machine (normalized 0..1)
    - Health state for each machine (0..1, with 1.0 = perfect, 0.05 = critical)
    - Current job processing time (normalized 0..1)
    - Current job due date urgency (inverse days_until_due, normalized)
    - Elapsed simulation time (0..1 across full episode)
    - Current factory utilization (0..1)
    
    Action Space:
    ---------------
    - Discrete(n_machines): agent selects which machine to dispatch next job to
    
    Reward:
    --------
    - Negative tardiness penalty: -tardiness_hours
    - Negative downtime penalty: -downtime_delta_hours
    - Shaped reward encourages on-time completion and high availability
    
    Episode Termination:
    --------------------
    - max_jobs reached (~1000 jobs worth of work)
    - max_simulation_time reached (24 hours)
    - truncated if either limit was artificial (Gymnasium API)
    """
    
    metadata = {"render_modes": []}  # No rendering for this environment
    
    def __init__(
        self,
        config: FactoryConfig | None = None,
        max_jobs: int = 1000,
        max_simulation_hours: float = 24.0,
        deterministic: bool = False,
        reward_config: FactoryReward | None = None,
    ):
        """
        Initialize the Gymnasium environment.
        
        Args:
            config: FactoryConfig for simulation parameters. If None, uses defaults.
            max_jobs: Maximum number of jobs to dispatch before episode termination.
            max_simulation_hours: Maximum simulated time before episode termination.
            deterministic: If True, use fixed random seed for reproducibility.
            reward_config: FactoryReward config for reward calculation.
        """
        super().__init__()
        
        self.config = config or FactoryConfig()
        if deterministic:
            self.config.random_seed = 42
        
        self.max_jobs = max_jobs
        self.max_simulation_hours = max_simulation_hours
        self.reward_config = reward_config or FactoryReward()
        
        self.simulation: FactorySimulation | None = None
        self._episode_job_count = 0
        self._previous_total_downtime = 0.0
        self._max_queue_length = 10  # for observation normalization
        self._max_processing_time = self.config.mean_processing_time_hours * 2.0
        self._max_urgency = 10.0
        
        # Observation space: [queue_lengths (n), health (n), candidates (n), proc_time, urgency, op_idx, elapsed, util]
        n_machines = self.config.num_machines
        obs_size = 3 * n_machines + 5
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(obs_size,), dtype=np.float32
        )
        
        # Action space: candidate index into current operation candidate list (bounded by n_machines)
        self.action_space = spaces.Discrete(n_machines)
    
    def reset(self, seed: int | None = None, options: dict[str, Any] | None = None) -> tuple[np.ndarray, dict[str, Any]]:
        """
        Reset the environment for a new episode.
        
        Returns:
            observation: Initial state observation as flat numpy array
            info: Dictionary with metadata (simulation time, jobs dispatched, etc.)
        """
        super().reset(seed=seed)
        
        if seed is not None:
            self.config.random_seed = seed
        
        self.simulation = FactorySimulation(self.config)
        self._episode_job_count = 0
        self._previous_total_downtime = 0.0
        
        # Initialize simulation processes
        # Start job arrivals and dispatcher processes that run continuously
        self.simulation.env.process(self.simulation.job_arrivals())
        self.simulation.env.process(self.simulation.operation_dispatcher())
        
        # Start machine worker processes
        for machine in self.simulation.machines:
            worker = self.simulation.env.process(self.simulation.machine_worker(machine))
            self.simulation.worker_processes[machine.machine_id] = worker
            if self.config.enable_failures:
                self.simulation.env.process(self.simulation.machine_failure_process(machine))
                self.simulation.env.process(self.simulation.preventive_maintenance_process(machine))
        
        # Run initial warmup to generate first job
        try:
            self.simulation.env.run(until=0.001)
        except StopIteration:
            pass
        
        obs = self._build_observation()
        info = self._build_info()
        
        return obs, info
    
    def step(self, action: int) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        """
        Execute one step of the environment.
        
        The agent chooses a machine to dispatch the next job to.
        The simulation runs until the next job completes or a time window elapses.
        
        Args:
            action: Machine index (0..n_machines-1) to dispatch the current job to.
        
        Returns:
            observation: New state after step
            reward: Reward signal for this step
            terminated: Whether episode ended (max_jobs or max_time reached)
            truncated: Whether episode was cut short (Gymnasium convention)
            info: Metadata dict with metrics
        """
        assert self.simulation is not None, "Must call reset() before step()"
        assert self.action_space.contains(action), f"Invalid action {action}"
        
        # Wait for a job to arrive in the incoming queue
        # Run simulation until a job arrives (if none present) or for a small time increment
        max_wait_iterations = 100
        iteration = 0
        while len(self.simulation.incoming_queue.items) == 0 and iteration < max_wait_iterations:
            try:
                self.simulation.env.run(until=self.simulation.env.now + 0.001)
            except StopIteration:
                break
            iteration += 1
        
        invalid_action_penalty = 0.0

        # If a job is waiting, provide dispatcher with preferred candidate index hint.
        if len(self.simulation.incoming_queue.items) > 0:
            job = self.simulation.incoming_queue.items[0]
            op = job.current_operation()
            candidates = (
                op.candidate_machines
                if op is not None and len(op.candidate_machines) > 0
                else [m.machine_id for m in self.simulation.machines]
            )

            if int(action) < len(candidates):
                self.simulation.preferred_candidate_index_by_job_id[job.job_id] = int(action)
            else:
                invalid_action_penalty = -0.2

            self._episode_job_count += 1
            self._record_dispatch_event(job, int(action))
        
        # Collect downtime before step
        downtime_before = sum(m.downtime for m in self.simulation.machines)
        
        # Run simulation for a fixed time delta to allow job processing
        sim_time_delta = 0.05  # 3 hours in factory time
        try:
            self.simulation.env.run(until=self.simulation.env.now + sim_time_delta)
        except StopIteration:
            pass  # Simulation ended
        
        # Collect metrics after step
        downtime_after = sum(m.downtime for m in self.simulation.machines)
        
        # Calculate reward based on recently completed jobs
        newly_completed_tardiness = 0.0
        completed_count = 0
        for job in self.simulation.jobs:
            if job.completion_time is not None and job.completion_time > self.simulation.env.now - sim_time_delta:
                tardiness = max(0.0, (job.completion_time or 0.0) - job.due_date)
                newly_completed_tardiness = max(newly_completed_tardiness, tardiness)
                completed_count += 1
        
        reward = self.reward_config.compute(
            newly_completed_tardiness,
            downtime_after,
            downtime_before,
        )
        reward += invalid_action_penalty
        
        # Check termination conditions
        terminated = (
            self._episode_job_count >= self.max_jobs or
            self.simulation.env.now >= self.max_simulation_hours
        )
        truncated = False  # No artificial truncation; only natural termination
        
        obs = self._build_observation()
        info = self._build_info()
        info.update({
            "jobs_dispatched_this_episode": self._episode_job_count,
            "newly_completed_tardiness": newly_completed_tardiness,
            "downtime_delta_this_step": downtime_after - downtime_before,
            "jobs_completed_this_step": completed_count,
            "invalid_action_penalty": invalid_action_penalty,
        })
        
        self._previous_total_downtime = downtime_after
        
        return obs, float(reward), terminated, truncated, info
    
    def _build_observation(self) -> np.ndarray:
        """Construct the observation from current simulation state."""
        assert self.simulation is not None
        
        # Queue lengths: count jobs in each machine queue
        queue_lengths = np.array(
            [len(q.items) for q in self.simulation.machine_queues],
            dtype=np.float32
        ) / self._max_queue_length
        queue_lengths = np.clip(queue_lengths, 0.0, 1.0)
        
        # Machine health: computed as in health-aware scheduler
        machine_health = np.array([
            max(0.05, 1.0 - ((m.failure_count * 0.12) + (m.busy_time_since_maintenance / 30.0)))
            for m in self.simulation.machines
        ], dtype=np.float32)
        
        # Current job properties
        current_job_processing_time = 0.0
        current_job_urgency = 0.0
        current_operation_index = 0.0
        candidate_mask = np.zeros(len(self.simulation.machines), dtype=np.float32)
        if len(self.simulation.incoming_queue.items) > 0:
            job = self.simulation.incoming_queue.items[0]
            op = job.current_operation()
            op_processing_time = op.processing_time if op is not None else job.processing_time
            current_job_processing_time = min(
                1.0, op_processing_time / self._max_processing_time
            )
            time_until_due = max(job.due_date - self.simulation.env.now, 1e-6)
            current_job_urgency = min(1.0, 1.0 / time_until_due)
            total_ops = max(len(job.operations), 1)
            current_operation_index = min(1.0, job.current_operation_index / total_ops)

            candidates = (
                op.candidate_machines
                if op is not None and len(op.candidate_machines) > 0
                else [m.machine_id for m in self.simulation.machines]
            )
            for machine_id in candidates:
                if 0 <= machine_id < len(candidate_mask):
                    candidate_mask[machine_id] = 1.0
        
        # Elapsed time fraction
        elapsed_fraction = min(
            1.0, self.simulation.env.now / max(self.max_simulation_hours, 1e-6)
        )
        
        # Utilization
        total_busy_time = sum(m.busy_time for m in self.simulation.machines)
        capacity_window = max(self.simulation.env.now, 1e-9) * len(self.simulation.machines)
        utilization = min(1.0, total_busy_time / capacity_window)
        
        obs = FactoryObservation(
            queue_lengths=queue_lengths,
            machine_health=machine_health,
            candidate_mask=candidate_mask,
            current_job_processing_time=float(current_job_processing_time),
            current_job_due_date_urgency=float(current_job_urgency),
            current_operation_index=float(current_operation_index),
            elapsed_time_fraction=float(elapsed_fraction),
            utilization=float(utilization),
        )
        
        return obs.to_array()
    
    def _build_info(self) -> dict[str, Any]:
        """Build info dictionary with current simulation metrics."""
        assert self.simulation is not None
        
        return {
            "sim_time_hours": round(self.simulation.env.now, 4),
            "jobs_generated": len(self.simulation.jobs),
            "jobs_completed": self.simulation._throughput,
            "total_downtime_hours": round(sum(m.downtime for m in self.simulation.machines), 4),
            "total_failures": sum(m.failure_count for m in self.simulation.machines),
        }
    
    def _record_dispatch_event(self, job: Any, machine_id: int) -> None:
        """Record candidate-index dispatch event in simulation log."""
        assert self.simulation is not None
        self.simulation._record_event(
            "operation_dispatched_by_rl_agent",
            job_id=job.job_id,
            candidate_index=machine_id,
        )
    
    def get_metrics(self) -> dict[str, float | int]:
        """
        Get comprehensive metrics for the current episode.
        
        Returns:
            Dictionary with all simulation metrics (tardiness, downtime, etc.)
        """
        if self.simulation is None:
            return {}
        return self.simulation.summary()


# Export for use in RL training pipelines
__all__ = ["FactoryGymEnvironment", "FactoryObservation", "FactoryReward"]

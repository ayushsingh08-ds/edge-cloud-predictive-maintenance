# Research README: Real-Time Metrics and Model Evaluation

## 1. Scope

This document is a research-focused guide for reporting real-time and aggregate performance of all implemented decision models in this project.

It is designed for:

- Experiment execution
- Reproducible evaluation
- Paper-quality metric definitions
- Baseline vs RL comparison

## 2. Implemented Models and Algorithms

### 2.1 Scheduling Baselines

Implemented in the simulation scheduler:

- `RANDOM`
- `SPT` (short-processing-time proxy)
- `QUEUE_BASED`
- `HEALTH_AWARE` (multi-factor weighted scoring)

### 2.2 Reinforcement Learning Model

- Algorithm: `PPO` (Proximal Policy Optimization)
- Library: `stable-baselines3`
- Policy: `MlpPolicy`
- Environment: custom Gymnasium wrapper over factory simulator
- Action: candidate-machine selection for current operation

### 2.3 Routing Analytics Layer

Not a separate predictive model, but a derived analytics module that computes:

- Routing efficiency
- Rerouting statistics
- Bottleneck operations
- Efficiency gap versus ideal baseline

## 3. Real-Time Metrics Available Now

## 3.1 Live WebSocket Metrics

### Global dashboard stream

- Endpoint: `ws://<host>:<port>/ws/events`
- Event type: `dashboard_snapshot`
- Fields:
  - `completed_simulations`
  - `latest_simulation`
  - `timestamp`

### Simulation snapshot stream

- Endpoint: `ws://<host>:<port>/ws/events/{simulation_id}`
- Event type: `simulation_snapshot`
- Fields:
  - `status`
  - `events` (recent event window)
  - `timestamp`

### High-frequency live simulation stream

- Endpoint: `ws://<host>:<port>/ws/simulation/{simulation_id}`
- Event types:
  - `stream_started`
  - `operation_routed`
  - `operation_started`
  - `operation_interrupted`
  - `operation_completed`
  - `job_rerouted`
  - `machine_failed`
  - `machine_repaired`
  - `stream_completed`
  - `stream_error`
  - `heartbeat`

## 3.2 REST Metrics During/After Runs

- `POST /api/streaming/run-and-stream`
  - Starts a streaming simulation and returns `simulation_id`.
- `GET /api/streaming/stream-status/{simulation_id}`
  - Real-time state of run, includes latest stream state payload.
- `POST /api/simulation/run`
  - Runs a simulation with selected policy.
- `GET /api/simulation/{simulation_id}`
  - Returns simulation metrics plus `routing_stats`.
- `GET /api/simulation/{simulation_id}/efficiency-report`
  - Routing efficiency and reroute analytics.
- `POST /api/simulation/compare-policies`
  - Baseline policy comparison.
- `GET /api/analytics/metrics/current`
  - System KPI snapshot.
- `GET /api/analytics/comparison/policies`
  - Policy-level comparison view.
- `GET /api/rl-training/{training_id}/status`
  - RL training progress and reward indicators.
- `POST /api/rl-training/{model_id}/evaluate`
  - RL policy evaluation on episodes.
- `POST /api/rl-training/compare-with-baselines`
  - RL versus baseline comparison (when comparison artifact exists).

## 4. Core Paper Metrics

Use these as primary quantitative outcomes:

- Throughput (`throughput_jobs_per_hour`)
- Utilization (`utilization`)
- Average tardiness (`avg_tardiness_hours`)
- Total downtime (`downtime_hours`)
- Failure count (`failures`)
- Jobs completed (`jobs_completed`)
- RL episode reward (`episode_reward`)
- Mean routing efficiency (`mean_routing_efficiency`)
- Total reroutes (`total_reroutes`)
- Routing success rate (`routing_success_rate`)

## 5. Metric Definitions (Recommended in Paper)

For consistency, use the following equations.

Routing efficiency:

$$
\text{routing\_efficiency} = \frac{\text{direct operations}}{\max(\text{actual hops}, 1)}
$$

Routing success rate:

$$
\text{routing\_success\_rate} = 1 - \frac{\text{affected jobs}}{\max(\text{jobs count}, 1)}
$$

Relative improvement for lower-is-better metrics (tardiness, downtime):

$$
\Delta\% = \frac{\text{baseline} - \text{candidate}}{\max(|\text{baseline}|, \epsilon)} \times 100
$$

Relative improvement for higher-is-better metrics (throughput, utilization):

$$
\Delta\% = \frac{\text{candidate} - \text{baseline}}{\max(|\text{baseline}|, \epsilon)} \times 100
$$

## 6. Experimental Protocol (Reproducible)

1. Fix random seeds for each trial.
2. Evaluate each policy/model on identical scenario settings.
3. Use at least 10 seeds for robust estimates.
4. Report mean and standard deviation per metric.
5. Include both aggregate outcomes and event-level analysis.

Suggested seed set:

- `42, 43, 44, 45, 46, 47, 48, 49, 50, 51`

## 7. Standard Evaluation Config Template

Keep these fixed across policy comparisons:

- `num_machines`
- `arrival_rate`
- `duration_hours`
- `enable_failures`
- `mean_processing_time_hours` (if configured)

Change only:

- Scheduling policy or model
- Seed

## 8. Real-Time Logging Schema for Research

For each event from `ws/simulation/{simulation_id}`, log:

- `simulation_id`
- `event_type`
- `timestamp`
- `payload.time` (sim-time if present)
- `payload.job_id`
- `payload.operation`
- `payload.machine_id`
- `payload.from_machine_id`
- `payload.to_machine_id`
- `payload.policy`

This supports timeline plots, hazard analysis, and reroute-chain reconstruction.

## 9. Paper-Ready Result Tables (Templates)

### Table A: Policy Comparison

| Policy       | Throughput (jobs/h) | Tardiness (h) | Downtime (h) | Utilization | Failures | Reroutes |
| ------------ | ------------------: | ------------: | -----------: | ----------: | -------: | -------: |
| RANDOM       |                     |               |              |             |          |          |
| SPT          |                     |               |              |             |          |          |
| QUEUE_BASED  |                     |               |              |             |          |          |
| HEALTH_AWARE |                     |               |              |             |          |          |
| RL_PPO       |                     |               |              |             |          |          |

### Table B: Relative Improvement vs Baseline (RANDOM)

| Policy       | Throughput Δ% | Tardiness Δ% | Downtime Δ% | Utilization Δ% |
| ------------ | ------------: | -----------: | ----------: | -------------: |
| SPT          |               |              |             |                |
| QUEUE_BASED  |               |              |             |                |
| HEALTH_AWARE |               |              |             |                |
| RL_PPO       |               |              |             |                |

### Table C: RL Training/Evaluation

| Model     | Timesteps | Mean Reward | Mean Tardiness (h) | Mean Downtime (h) | Mean Throughput |
| --------- | --------: | ----------: | -----------------: | ----------------: | --------------: |
| PPO Final |           |             |                    |                   |                 |

## 10. Statistical Reporting Recommendations

For publication:

- Report `mean ± std` over seeds.
- Add 95% confidence intervals if possible.
- Use paired tests for policy comparisons on identical seeds.
- Include effect size, not only p-values.

## 11. Important Notes on Current Implementation

- Operational and routing metrics are generated from simulation/evaluation flows and are suitable for comparative experiments.
- Some anomaly endpoint fields are currently demo placeholders (for example `detection_rate`, `false_positive_rate`) and should not be reported as validated model accuracy.
- If you need classification metrics (accuracy, precision, recall, F1, AUC), first wire a supervised anomaly model evaluation pipeline with labeled data.

## 12. Minimal Run Commands

Run backend:

```powershell
& "C:/Users/AYUSH SINGH/anaconda3/python.exe" -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Run dependency check in project interpreter:

```powershell
& "C:/Users/AYUSH SINGH/anaconda3/python.exe" -m pip check
```

## 13. Suggested Figure Set for Paper

- Figure 1: System architecture (Simulator + RL + API + Frontend)
- Figure 2: Real-time event timeline (operation/machine events)
- Figure 3: Policy comparison bar charts (throughput, tardiness, downtime)
- Figure 4: Routing bottleneck heatmap
- Figure 5: RL training reward progression
- Figure 6: Ablation of `HEALTH_AWARE` weights

---

## 14. Automated Benchmark Runner (CSV Export)

A ready-to-use benchmark script is available at:

- `experiments/benchmark_runner.py`

It executes baseline policies (and RL PPO if model file exists), then exports paper-ready CSVs.

### Run Command

```powershell
& "C:/Users/AYUSH SINGH/anaconda3/python.exe" experiments/benchmark_runner.py --episodes 10 --output-dir experiments/results
```

Optional flags:

- `--num-machines 3`
- `--arrival-rate 6.0`
- `--disable-failures`
- `--rl-model-path models/step9_ppo/ppo_final.zip`

### Generated Files

- `experiments/results/policy_episode_metrics.csv`
  - Raw per-episode metrics by policy/model
- `experiments/results/policy_summary.csv`
  - Mean/std summary table for paper reporting
- `experiments/results/improvements_vs_random.csv`
  - Relative performance deltas vs RANDOM baseline
- `experiments/results/run_manifest.csv`
  - Reproducibility metadata (episodes/config/model path)

### Recommended Paper Workflow

1. Run benchmark with fixed seeds/config.
2. Use `policy_summary.csv` for main result tables.
3. Use `improvements_vs_random.csv` for percentage gain table.
4. Use `policy_episode_metrics.csv` for statistical tests and confidence intervals.

## 15. Current Benchmark Snapshot

The following results were obtained from the retrained PPO model and the current simulator configuration:

- Episodes per policy: `5`
- Duration: `8.0` hours
- Machines: `3`
- Arrival rate: `6.0`
- Failures enabled: `True`
- PPO model path: `models/step9_ppo/ppo_final.zip`

### Summary Metrics

| Policy       | Mean Reward | Throughput (jobs/h) | Tardiness (h) | Downtime (h) | Utilization | Failures |
| ------------ | ----------: | ------------------: | ------------: | -----------: | ----------: | -------: |
| RANDOM       |    0.000000 |            5.466680 |      0.154820 |     7.627420 |    0.612940 |      4.6 |
| SPT          |    0.000000 |            5.791660 |      0.030460 |     4.637060 |    0.663940 |      4.2 |
| QUEUE_BASED  |    0.000000 |            5.725020 |      0.029960 |     4.850260 |    0.651840 |      4.4 |
| HEALTH_AWARE |    0.000000 |            5.758340 |      0.079760 |     5.219840 |    0.659980 |      4.6 |
| RL_PPO       |   -2.275308 |            5.724760 |      0.029960 |     4.850260 |    0.651840 |      4.4 |

### Relative Improvement vs RANDOM

| Policy       | Throughput Δ% | Tardiness Δ% | Downtime Δ% | Utilization Δ% |
| ------------ | ------------: | -----------: | ----------: | -------------: |
| SPT          |        5.9447 |      80.3255 |     39.2054 |         8.3206 |
| QUEUE_BASED  |        4.7257 |      80.6485 |     36.4102 |         6.3465 |
| HEALTH_AWARE |        5.3352 |      48.4821 |     31.5648 |         7.6745 |
| RL_PPO       |        4.7210 |      80.6485 |     36.4102 |         6.3465 |

### Interpretation

- `SPT` performed best on throughput among the baseline policies in this snapshot.
- `QUEUE_BASED` and `RL_PPO` were tied on tardiness and downtime in this 5-episode run.
- `HEALTH_AWARE` improved over `RANDOM`, but was below `SPT` for this configuration.
- `RL_PPO` produced a negative mean reward, which is expected because the current reward function is penalty-based.

Use these numbers as a **current experimental snapshot**, not final publication values. For the paper, rerun the benchmark with a larger episode count and report `mean ± std`.

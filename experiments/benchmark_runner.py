"""Run reproducible policy/model benchmarks and export paper-ready CSV tables.

Usage:
    python experiments/benchmark_runner.py --episodes 10 --duration-hours 8 --output-dir experiments/results
"""

from __future__ import annotations

import argparse
import csv
import statistics
from pathlib import Path
from typing import Any
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.cluster.rl_policy import PolicyComparator
from services.simulation.engine import FactoryConfig, SchedulingPolicy


def _mean(values: list[float]) -> float:
    return float(statistics.fmean(values)) if values else 0.0


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return float(statistics.pstdev(values))


def _write_csv(path: Path, rows: list[dict[str, Any]], headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _safe_rel_improvement(baseline: float, candidate: float, higher_is_better: bool) -> float:
    eps = 1e-9
    denom = max(abs(baseline), eps)
    if higher_is_better:
        return ((candidate - baseline) / denom) * 100.0
    return ((baseline - candidate) / denom) * 100.0


def run_benchmark(
    episodes: int,
    duration_hours: float,
    num_machines: int,
    arrival_rate: float,
    enable_failures: bool,
    output_dir: Path,
    rl_model_path: str | None,
) -> None:
    config = FactoryConfig(
        num_machines=num_machines,
        arrival_rate_per_hour=arrival_rate,
        enable_failures=enable_failures,
        random_seed=42,
    )

    comparator = PolicyComparator(rl_model_path=rl_model_path, config=config)
    include_baselines = [
        SchedulingPolicy.RANDOM,
        SchedulingPolicy.SPT,
        SchedulingPolicy.QUEUE_BASED,
        SchedulingPolicy.HEALTH_AWARE,
    ]

    # Compare policies over identical seeds
    try:
        results = comparator.compare_policies(
            num_episodes=episodes,
            include_baselines=include_baselines,
        )
    except Exception as exc:
        if rl_model_path:
            print(
                "RL evaluation failed; continuing with baselines only. "
                f"Details: {exc}"
            )
            comparator = PolicyComparator(rl_model_path=None, config=config)
            results = comparator.compare_policies(
                num_episodes=episodes,
                include_baselines=include_baselines,
            )
        else:
            raise

    # Save raw episode-level rows
    episode_rows: list[dict[str, Any]] = []
    for policy_name, metrics_list in results.items():
        for idx, m in enumerate(metrics_list, start=1):
            episode_rows.append(
                {
                    "policy": policy_name,
                    "episode": idx,
                    "episode_reward": round(float(m.episode_reward), 6),
                    "jobs_completed": int(m.jobs_completed),
                    "avg_tardiness_hours": round(float(m.avg_tardiness_hours), 6),
                    "total_downtime_hours": round(float(m.total_downtime_hours), 6),
                    "total_failures": int(m.total_failures),
                    "utilization": round(float(m.utilization), 6),
                    "throughput_jobs_per_hour": round(float(m.throughput_jobs_per_hour), 6),
                }
            )

    _write_csv(
        output_dir / "policy_episode_metrics.csv",
        episode_rows,
        headers=[
            "policy",
            "episode",
            "episode_reward",
            "jobs_completed",
            "avg_tardiness_hours",
            "total_downtime_hours",
            "total_failures",
            "utilization",
            "throughput_jobs_per_hour",
        ],
    )

    # Build policy summary table (mean/std)
    summary_rows: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in episode_rows:
        grouped.setdefault(str(row["policy"]), []).append(row)

    for policy_name, rows in grouped.items():
        rewards = [float(r["episode_reward"]) for r in rows]
        throughput = [float(r["throughput_jobs_per_hour"]) for r in rows]
        tardiness = [float(r["avg_tardiness_hours"]) for r in rows]
        downtime = [float(r["total_downtime_hours"]) for r in rows]
        utilization = [float(r["utilization"]) for r in rows]
        failures = [float(r["total_failures"]) for r in rows]

        summary_rows.append(
            {
                "policy": policy_name,
                "episodes": len(rows),
                "mean_reward": round(_mean(rewards), 6),
                "std_reward": round(_std(rewards), 6),
                "mean_throughput_jobs_per_hour": round(_mean(throughput), 6),
                "std_throughput_jobs_per_hour": round(_std(throughput), 6),
                "mean_tardiness_hours": round(_mean(tardiness), 6),
                "std_tardiness_hours": round(_std(tardiness), 6),
                "mean_downtime_hours": round(_mean(downtime), 6),
                "std_downtime_hours": round(_std(downtime), 6),
                "mean_utilization": round(_mean(utilization), 6),
                "std_utilization": round(_std(utilization), 6),
                "mean_failures": round(_mean(failures), 6),
                "std_failures": round(_std(failures), 6),
            }
        )

    # Keep a deterministic policy order for paper tables
    order = {
        "RANDOM": 0,
        "SPT": 1,
        "QUEUE_BASED": 2,
        "HEALTH_AWARE": 3,
        "RL_PPO": 4,
    }
    summary_rows.sort(key=lambda r: order.get(str(r["policy"]), 99))

    _write_csv(
        output_dir / "policy_summary.csv",
        summary_rows,
        headers=[
            "policy",
            "episodes",
            "mean_reward",
            "std_reward",
            "mean_throughput_jobs_per_hour",
            "std_throughput_jobs_per_hour",
            "mean_tardiness_hours",
            "std_tardiness_hours",
            "mean_downtime_hours",
            "std_downtime_hours",
            "mean_utilization",
            "std_utilization",
            "mean_failures",
            "std_failures",
        ],
    )

    # Relative improvements vs RANDOM baseline
    baseline = next((r for r in summary_rows if r["policy"] == "RANDOM"), None)
    improvement_rows: list[dict[str, Any]] = []
    if baseline is not None:
        base_tput = float(baseline["mean_throughput_jobs_per_hour"])
        base_tardiness = float(baseline["mean_tardiness_hours"])
        base_downtime = float(baseline["mean_downtime_hours"])
        base_util = float(baseline["mean_utilization"])

        for row in summary_rows:
            policy = str(row["policy"])
            if policy == "RANDOM":
                continue
            cand_tput = float(row["mean_throughput_jobs_per_hour"])
            cand_tardiness = float(row["mean_tardiness_hours"])
            cand_downtime = float(row["mean_downtime_hours"])
            cand_util = float(row["mean_utilization"])

            improvement_rows.append(
                {
                    "policy": policy,
                    "throughput_delta_percent": round(
                        _safe_rel_improvement(base_tput, cand_tput, higher_is_better=True), 4
                    ),
                    "tardiness_delta_percent": round(
                        _safe_rel_improvement(base_tardiness, cand_tardiness, higher_is_better=False), 4
                    ),
                    "downtime_delta_percent": round(
                        _safe_rel_improvement(base_downtime, cand_downtime, higher_is_better=False), 4
                    ),
                    "utilization_delta_percent": round(
                        _safe_rel_improvement(base_util, cand_util, higher_is_better=True), 4
                    ),
                }
            )

    _write_csv(
        output_dir / "improvements_vs_random.csv",
        improvement_rows,
        headers=[
            "policy",
            "throughput_delta_percent",
            "tardiness_delta_percent",
            "downtime_delta_percent",
            "utilization_delta_percent",
        ],
    )

    # Save a short run manifest for reproducibility
    manifest_rows = [
        {"key": "episodes", "value": episodes},
        {"key": "duration_hours", "value": duration_hours},
        {"key": "num_machines", "value": num_machines},
        {"key": "arrival_rate", "value": arrival_rate},
        {"key": "enable_failures", "value": enable_failures},
        {"key": "rl_model_path", "value": rl_model_path or ""},
    ]
    _write_csv(output_dir / "run_manifest.csv", manifest_rows, headers=["key", "value"])

    print(f"Benchmark complete. CSV outputs written to: {output_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run policy/model benchmarks and export CSVs.")
    parser.add_argument("--episodes", type=int, default=10, help="Number of episodes/seeds per policy.")
    parser.add_argument("--duration-hours", type=float, default=8.0, help="Reserved for compatibility.")
    parser.add_argument("--num-machines", type=int, default=3)
    parser.add_argument("--arrival-rate", type=float, default=6.0)
    parser.add_argument("--enable-failures", action="store_true", default=True)
    parser.add_argument("--disable-failures", action="store_true", help="Override and disable failures.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("experiments/results"),
        help="Directory for CSV artifacts.",
    )
    parser.add_argument(
        "--rl-model-path",
        type=str,
        default="models/step9_ppo/ppo_final.zip",
        help="Path to PPO model zip. If missing, RL row is skipped.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    rl_path = Path(args.rl_model_path)
    rl_model_path = str(rl_path) if rl_path.exists() else None

    enable_failures = bool(args.enable_failures)
    if args.disable_failures:
        enable_failures = False

    run_benchmark(
        episodes=args.episodes,
        duration_hours=args.duration_hours,
        num_machines=args.num_machines,
        arrival_rate=args.arrival_rate,
        enable_failures=enable_failures,
        output_dir=args.output_dir,
        rl_model_path=rl_model_path,
    )


if __name__ == "__main__":
    main()

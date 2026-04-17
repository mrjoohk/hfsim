"""Benchmark and profiling utilities for 60x time-acceleration regression tracking.

REQ-004: 4-agent reference scenario must achieve >= 60x simulation time acceleration.

Design:
- BenchmarkConfig holds the reference scenario parameters.
- run_benchmark() runs N sequential LocalEnvWorker instances (N=4 by default).
- BenchmarkResult exposes per-worker and aggregate metrics.
- passes_60x is True when every worker's acceleration >= 60.0.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from hf_sim.env import HFSimEnv


@dataclass
class BenchmarkConfig:
    """Configuration for the reference 60x benchmark (REQ-004).

    Attributes:
        n_workers:       Number of environment workers to run sequentially.
                         Default = 4 (REQ-004 reference: 4-agent baseline).
        sim_duration_s:  Simulated time per worker in seconds.
                         Default = 600 s (REQ-004 acceptance criterion).
        n_substeps:      Physics substeps per env step (5 × 0.01 s = 0.05 s/step).
        seed:            Base random seed; worker i uses seed + i.
    """

    n_workers: int = 4
    sim_duration_s: float = 600.0
    n_substeps: int = 5
    seed: int = 42


@dataclass
class WorkerBenchmarkResult:
    """Per-worker timing and accuracy metrics."""

    worker_id: int
    wall_time_s: float
    sim_time_s: float
    n_steps: int
    acceleration: float
    n_nonfinite: int


@dataclass
class BenchmarkResult:
    """Aggregate benchmark result for the full N-worker run."""

    config: BenchmarkConfig
    workers: list[WorkerBenchmarkResult] = field(default_factory=list)

    @property
    def mean_acceleration(self) -> float:
        """Mean time-acceleration ratio across all workers."""
        if not self.workers:
            return 0.0
        return float(np.mean([w.acceleration for w in self.workers]))

    @property
    def min_acceleration(self) -> float:
        """Worst-case (minimum) time-acceleration ratio across all workers."""
        if not self.workers:
            return 0.0
        return float(np.min([w.acceleration for w in self.workers]))

    @property
    def passes_60x(self) -> bool:
        """True when every worker achieves >= 60x acceleration (REQ-004 criterion)."""
        return bool(self.workers) and self.min_acceleration >= 60.0

    def to_dict(self) -> dict[str, Any]:
        """Serialisable summary suitable for JSON export or test assertions."""
        return {
            "n_workers": self.config.n_workers,
            "sim_duration_target_s": self.config.sim_duration_s,
            "mean_acceleration": round(self.mean_acceleration, 2),
            "min_acceleration": round(self.min_acceleration, 2),
            "passes_60x": self.passes_60x,
            "workers": [
                {
                    "worker_id": w.worker_id,
                    "wall_time_s": round(w.wall_time_s, 4),
                    "sim_time_s": round(w.sim_time_s, 3),
                    "acceleration": round(w.acceleration, 2),
                    "n_steps": w.n_steps,
                    "n_nonfinite": w.n_nonfinite,
                }
                for w in self.workers
            ],
        }


def _run_single_worker(worker_id: int, config: BenchmarkConfig) -> WorkerBenchmarkResult:
    """Execute one benchmark worker and return its timing result.

    Uses a constant throttle=0.5 action (no rotation) to avoid early
    termination from out-of-bounds state while still exercising the full
    dynamics+observation+termination-check stack.
    """
    step_dt_s = config.n_substeps * 0.01  # simulated seconds per env.step()
    target_steps = max(1, int(config.sim_duration_s / step_dt_s))

    env = HFSimEnv(
        curriculum_level=0,
        max_steps=target_steps + 1,
        n_substeps=config.n_substeps,
        seed=config.seed + worker_id,
    )
    env.reset(seed=config.seed + worker_id)

    # Constant cruise action: mid throttle, level flight
    action = np.array([0.5, 0.0, 0.0, 0.0, 1.0], dtype=np.float32)

    n_steps = 0
    n_nonfinite = 0

    t_start = time.perf_counter()
    for _ in range(target_steps):
        _, _, terminated, truncated, info = env.step(action)
        n_steps += 1
        if info.get("event_flags", {}).get("nonfinite", False):
            n_nonfinite += 1
        if terminated or truncated:
            env.reset()
    wall_time_s = time.perf_counter() - t_start

    # sim_time is accumulated as n_steps × step_dt so episode resets don't
    # reset the clock — we measure total simulated throughput, not episode time.
    sim_time_s = n_steps * step_dt_s

    env.close()

    safe_wall = max(wall_time_s, 1e-9)
    return WorkerBenchmarkResult(
        worker_id=worker_id,
        wall_time_s=safe_wall,
        sim_time_s=sim_time_s,
        n_steps=n_steps,
        acceleration=sim_time_s / safe_wall,
        n_nonfinite=n_nonfinite,
    )


def run_benchmark(config: BenchmarkConfig | None = None) -> BenchmarkResult:
    """Run the reference 60x benchmark scenario (REQ-004).

    Executes ``config.n_workers`` sequential HFSimEnv instances, each for
    ``config.sim_duration_s`` of simulated time, measuring wall-clock time.

    Returns a :class:`BenchmarkResult` with per-worker metrics and the
    aggregate ``passes_60x`` flag.

    Example::

        result = run_benchmark(BenchmarkConfig(n_workers=4, sim_duration_s=600))
        assert result.passes_60x, result.to_dict()
    """
    if config is None:
        config = BenchmarkConfig()

    result = BenchmarkResult(config=config)
    for worker_id in range(config.n_workers):
        result.workers.append(_run_single_worker(worker_id, config))
    return result

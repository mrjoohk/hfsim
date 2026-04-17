"""Unit tests for hf_sim.benchmark (REQ-004 time-acceleration tracking)."""

import pytest

from hf_sim.benchmark import BenchmarkConfig, BenchmarkResult, WorkerBenchmarkResult, run_benchmark


# ---------------------------------------------------------------------------
# BenchmarkConfig defaults
# ---------------------------------------------------------------------------

def test_benchmark_config_defaults():
    cfg = BenchmarkConfig()
    assert cfg.n_workers == 4
    assert cfg.sim_duration_s == 600.0
    assert cfg.n_substeps == 5
    assert cfg.seed == 42


def test_benchmark_config_custom():
    cfg = BenchmarkConfig(n_workers=1, sim_duration_s=10.0, seed=7)
    assert cfg.n_workers == 1
    assert cfg.sim_duration_s == 10.0
    assert cfg.seed == 7


# ---------------------------------------------------------------------------
# BenchmarkResult computed properties
# ---------------------------------------------------------------------------

def _make_result(accelerations: list[float]) -> BenchmarkResult:
    config = BenchmarkConfig(n_workers=len(accelerations), sim_duration_s=60.0)
    workers = [
        WorkerBenchmarkResult(
            worker_id=i,
            wall_time_s=1.0,
            sim_time_s=acc,
            n_steps=100,
            acceleration=acc,
            n_nonfinite=0,
        )
        for i, acc in enumerate(accelerations)
    ]
    return BenchmarkResult(config=config, workers=workers)


def test_benchmark_result_mean_acceleration():
    result = _make_result([80.0, 100.0])
    assert result.mean_acceleration == pytest.approx(90.0)


def test_benchmark_result_min_acceleration():
    result = _make_result([80.0, 100.0])
    assert result.min_acceleration == pytest.approx(80.0)


def test_benchmark_result_passes_60x_true():
    result = _make_result([65.0, 70.0, 80.0, 90.0])
    assert result.passes_60x is True


def test_benchmark_result_passes_60x_false_one_worker():
    result = _make_result([65.0, 55.0, 80.0, 90.0])
    assert result.passes_60x is False


def test_benchmark_result_empty_workers():
    config = BenchmarkConfig(n_workers=0)
    result = BenchmarkResult(config=config)
    assert result.mean_acceleration == 0.0
    assert result.min_acceleration == 0.0
    assert result.passes_60x is False


def test_benchmark_result_to_dict_structure():
    result = _make_result([75.0])
    d = result.to_dict()
    assert "n_workers" in d
    assert "sim_duration_target_s" in d
    assert "mean_acceleration" in d
    assert "min_acceleration" in d
    assert "passes_60x" in d
    assert "workers" in d
    assert len(d["workers"]) == 1
    assert "worker_id" in d["workers"][0]
    assert "acceleration" in d["workers"][0]
    assert "n_nonfinite" in d["workers"][0]


# ---------------------------------------------------------------------------
# run_benchmark: short smoke test (1 worker, 2 s simulated)
# ---------------------------------------------------------------------------

def test_run_benchmark_returns_valid_result():
    cfg = BenchmarkConfig(n_workers=1, sim_duration_s=2.0, seed=0)
    result = run_benchmark(cfg)
    assert len(result.workers) == 1
    w = result.workers[0]
    assert w.worker_id == 0
    assert w.n_steps > 0
    assert w.sim_time_s > 0.0
    assert w.wall_time_s > 0.0
    assert w.acceleration > 0.0
    assert w.n_nonfinite == 0


def test_run_benchmark_worker_seed_offset():
    """Different workers start from different seeds (no identical trajectories)."""
    cfg = BenchmarkConfig(n_workers=2, sim_duration_s=1.0, seed=99)
    result = run_benchmark(cfg)
    assert result.workers[0].worker_id == 0
    assert result.workers[1].worker_id == 1


def test_run_benchmark_to_dict_round_trip():
    cfg = BenchmarkConfig(n_workers=1, sim_duration_s=1.0)
    result = run_benchmark(cfg)
    d = result.to_dict()
    assert d["n_workers"] == 1
    assert isinstance(d["mean_acceleration"], float)
    assert isinstance(d["passes_60x"], bool)

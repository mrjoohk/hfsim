"""Integration tests for 60x time-acceleration benchmark (REQ-004).

Runs a short (60 s simulated, 1 worker) benchmark and asserts:
- Result structure is valid.
- Acceleration >= 60x (REQ-004 acceptance criterion).

The reference scenario (600 s, 4 workers) is a longer run intended for
manual profiling or CI regression jobs; use run_benchmark() with default
BenchmarkConfig() for that.
"""

from hf_sim.benchmark import BenchmarkConfig, run_benchmark


def test_benchmark_60x_acceptance():
    """REQ-004: 60 s simulated / 1 worker must achieve >= 60x acceleration."""
    cfg = BenchmarkConfig(n_workers=1, sim_duration_s=60.0, seed=0)
    result = run_benchmark(cfg)

    assert len(result.workers) == 1
    w = result.workers[0]

    assert w.sim_time_s >= 59.0, f"sim_time_s too short: {w.sim_time_s}"
    assert w.n_nonfinite == 0, f"nonfinite states: {w.n_nonfinite}"
    assert w.acceleration >= 60.0, (
        f"REQ-004 FAIL: acceleration={w.acceleration:.1f}x < 60x "
        f"(wall={w.wall_time_s:.3f}s, sim={w.sim_time_s:.1f}s)"
    )


def test_benchmark_result_dict_valid_schema():
    """Benchmark result dict has all required keys."""
    cfg = BenchmarkConfig(n_workers=1, sim_duration_s=10.0)
    result = run_benchmark(cfg)
    d = result.to_dict()

    required_keys = {"n_workers", "sim_duration_target_s", "mean_acceleration",
                     "min_acceleration", "passes_60x", "workers"}
    assert required_keys.issubset(d.keys())

    worker_keys = {"worker_id", "wall_time_s", "sim_time_s", "acceleration",
                   "n_steps", "n_nonfinite"}
    assert worker_keys.issubset(d["workers"][0].keys())


def test_benchmark_4workers_all_pass_60x():
    """REQ-004 reference: 4 workers × 60 s simulated — all must hit >= 60x."""
    cfg = BenchmarkConfig(n_workers=4, sim_duration_s=60.0, seed=1)
    result = run_benchmark(cfg)

    assert len(result.workers) == 4
    for w in result.workers:
        assert w.n_nonfinite == 0, f"worker {w.worker_id}: nonfinite={w.n_nonfinite}"
        assert w.acceleration >= 60.0, (
            f"REQ-004 FAIL worker {w.worker_id}: {w.acceleration:.1f}x < 60x"
        )
    assert result.passes_60x

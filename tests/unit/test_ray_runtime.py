from __future__ import annotations

from pathlib import Path

import numpy as np

from hf_sim.dataset import SequenceBuffer
from hf_sim.env import HFSimEnv
from hf_sim.ray_runtime import (
    LocalCollector,
    LocalEnvWorker,
    LocalLoggerWorker,
    create_ray_actor_classes,
)


def _actions(n: int) -> list[np.ndarray]:
    return [
        np.array([0.6, 0.05, -0.02, 0.0, 1.0], dtype=np.float32)
        for _ in range(n)
    ]


def _policy(obs: np.ndarray) -> np.ndarray:
    del obs
    return np.array([0.55, 0.0, 0.05, 0.0, 1.0], dtype=np.float32)


def test_local_env_worker_chunk_matches_direct_env():
    env = HFSimEnv(seed=21, max_steps=50)
    direct_obs, _ = env.reset(seed=21)

    worker = LocalEnvWorker({"seed": 21, "max_steps": 50})
    worker_obs, _ = worker.reset(seed=21)
    np.testing.assert_array_equal(direct_obs, worker_obs)

    actions = _actions(4)
    direct_rewards: list[float] = []
    for action in actions:
        direct_obs, reward, terminated, truncated, _ = env.step(action)
        direct_rewards.append(float(reward))
        assert not (terminated or truncated)

    worker_result = worker.step_chunk(actions, auto_reset=False)
    np.testing.assert_allclose(worker_result.final_obs, direct_obs, atol=1e-6)
    assert [round(t.reward, 8) for t in worker_result.transitions] == [round(r, 8) for r in direct_rewards]


def test_local_env_worker_branch_rollout_returns_result():
    worker = LocalEnvWorker({"seed": 7, "max_steps": 50})
    worker.reset(seed=7)
    worker.step_chunk(_actions(2), auto_reset=False)

    result = worker.branch_rollout(
        runtime_source_spec={"source": "current", "k": 0},
        branch_mode="single_action_set",
        branch_controls=[
            {"throttle": 0.8, "roll": 0.1, "pitch": 0.0},
            {"throttle": 0.2, "roll": -0.1, "pitch": 0.0},
        ],
        horizon=3,
    )
    assert result.branch_count == 2
    assert result.validation_report.branch_isolated


def test_local_collector_fills_sequence_buffer():
    worker = LocalEnvWorker({"seed": 5, "max_steps": 20})
    buffer = SequenceBuffer(capacity=512)
    collector = LocalCollector(buffer)
    summary = collector.collect_worker_episodes(worker, _policy, n_episodes=2)
    assert len(buffer) > 0
    assert summary.episodes == 2
    assert summary.mean_length > 0.0


def test_local_logger_exports_runtime_logs():
    worker = LocalEnvWorker({"seed": 9, "max_steps": 20})
    worker.reset(seed=9)
    logger = LocalLoggerWorker()
    entry = logger.build_runtime_entry(worker, {"throttle": 0.4, "roll": 0.0, "pitch": 0.0}, step_index=0)

    jsonl_path = Path.cwd() / "test_ray_runtime_logs.jsonl"
    csv_path = Path.cwd() / "test_ray_runtime_logs.csv"
    try:
        outputs = logger.export_runtime_chunk_logs([entry], jsonl_path=str(jsonl_path), csv_path=str(csv_path))
        assert Path(outputs["jsonl_path"]).exists()
        assert Path(outputs["csv_path"]).exists()
    finally:
        jsonl_path.unlink(missing_ok=True)
        csv_path.unlink(missing_ok=True)


def test_create_ray_actor_classes_with_fake_ray():
    class FakeRay:
        @staticmethod
        def remote(cls):
            return {"remote_wrapped": cls.__name__}

    actors = create_ray_actor_classes(FakeRay())
    assert actors is not None
    assert actors["EnvWorker"]["remote_wrapped"] == "LocalEnvWorker"
    assert actors["LoggerWorker"]["remote_wrapped"] == "LocalLoggerWorker"

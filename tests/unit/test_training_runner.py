"""Unit tests for api.training_runner.

Covers:
- _check_anomaly() edge cases
- LocalTrainingRunner state machine
- create_runner() factory / env-var selection
- _broadcast() exception suppression
- RayTrainingRunner (skipped when ray not installed)
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure src/ is on the path (mirrors how uvicorn imports the module)
_SRC = Path(__file__).parent.parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from api.training_runner import (
    LocalTrainingRunner,
    _broadcast,
    _check_anomaly,
    create_runner,
)


# ---------------------------------------------------------------------------
# _check_anomaly
# ---------------------------------------------------------------------------

def test_check_anomaly_normal():
    assert _check_anomaly({"mean_return": 1.0, "mean_length": 10}) is None


def test_check_anomaly_missing_fields():
    assert _check_anomaly({}) is None


def test_check_anomaly_reward_exploded_positive():
    assert _check_anomaly({"mean_return": 1e5}) == "reward_exploded"


def test_check_anomaly_reward_exploded_negative():
    assert _check_anomaly({"mean_return": -2e4}) == "reward_exploded"


def test_check_anomaly_reward_boundary():
    assert _check_anomaly({"mean_return": 1e4}) is None   # exactly 1e4 is OK


def test_check_anomaly_episode_too_short():
    assert _check_anomaly({"mean_length": 1.9}) == "episode_too_short"


def test_check_anomaly_episode_length_ok():
    assert _check_anomaly({"mean_length": 2.0}) is None


# ---------------------------------------------------------------------------
# LocalTrainingRunner state machine
# ---------------------------------------------------------------------------

def test_local_runner_initial_state():
    r = LocalTrainingRunner()
    assert r.state == "IDLE"
    assert r.pid is None
    assert r.job_id is None


def test_local_runner_double_start_raises():
    r = LocalTrainingRunner()
    r.state = "RUNNING"
    with pytest.raises(RuntimeError, match="already running"):
        r.start(MagicMock(), MagicMock())


def test_local_runner_stop_when_idle():
    r = LocalTrainingRunner()
    r.stop()  # must not raise even with no process
    assert r.state == "STOPPED"


def test_local_runner_status_shape():
    r = LocalTrainingRunner()
    s = r.status()
    assert "state" in s
    assert "pid" in s
    assert s["job_id"] is None


# ---------------------------------------------------------------------------
# create_runner() factory
# ---------------------------------------------------------------------------

def test_create_runner_default(monkeypatch):
    monkeypatch.delenv("HFSIM_RUNNER", raising=False)
    from api.training_runner import create_runner as cr
    runner = cr()
    assert isinstance(runner, LocalTrainingRunner)


def test_create_runner_local(monkeypatch):
    monkeypatch.setenv("HFSIM_RUNNER", "local")
    from api.training_runner import create_runner as cr
    runner = cr()
    assert isinstance(runner, LocalTrainingRunner)


def test_create_runner_local_uppercase(monkeypatch):
    monkeypatch.setenv("HFSIM_RUNNER", "LOCAL")
    from api.training_runner import create_runner as cr
    runner = cr()
    assert isinstance(runner, LocalTrainingRunner)


# ---------------------------------------------------------------------------
# _broadcast — exceptions must be swallowed
# ---------------------------------------------------------------------------

def test_broadcast_swallows_timeout():
    loop = asyncio.new_event_loop()
    ws_manager = MagicMock()
    # Make broadcast() raise so run_coroutine_threadsafe.result() raises
    ws_manager.broadcast = MagicMock(side_effect=Exception("boom"))
    # Should not propagate
    _broadcast(ws_manager, {"x": 1}, loop)
    loop.close()


def test_broadcast_with_bad_loop():
    _broadcast(MagicMock(), {"x": 1}, None)   # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# RayTrainingRunner — skip when ray not installed
# ---------------------------------------------------------------------------

ray = pytest.importorskip("ray", reason="ray not installed — skipping Ray runner tests")


def test_ray_runner_no_cluster():
    from api.training_runner import RayTrainingRunner
    from ray.job_submission import JobSubmissionClient

    with patch.object(JobSubmissionClient, "__init__", return_value=None):
        r = RayTrainingRunner(dashboard_url="http://127.0.0.1:8265")
        assert r.state == "IDLE"
        assert r.pid is None


def test_ray_runner_double_start_raises():
    from api.training_runner import RayTrainingRunner
    from ray.job_submission import JobSubmissionClient

    with patch.object(JobSubmissionClient, "__init__", return_value=None):
        r = RayTrainingRunner()
        r.state = "RUNNING"
        with pytest.raises(RuntimeError, match="already running"):
            r.start(MagicMock(), MagicMock())

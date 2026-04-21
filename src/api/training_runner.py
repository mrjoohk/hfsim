"""Training runners — subprocess (local) and Ray Jobs API.

Two backends
------------
LocalTrainingRunner
    Spawns ``src/train.py`` as a subprocess, reads stdout line-by-line
    (each line is a JSON metrics dict), and broadcasts to WebSocket clients.
    No external dependencies beyond the core project.

RayTrainingRunner
    Submits ``src/train.py`` as a Ray Job, tails its logs the same way.
    Requires ``pip install 'ray[default]>=2.10'`` and a running cluster
    (``ray start --head``).

Selection
---------
Set the ``HFSIM_RUNNER`` environment variable before starting uvicorn::

    HFSIM_RUNNER=local  (default)
    HFSIM_RUNNER=ray    RAY_DASHBOARD_URL=http://127.0.0.1:8265

State machine: IDLE → RUNNING → STOPPED | FAILED

Thread-safety note
------------------
Both runners' log-tail loops run in daemon threads.  Broadcasting to
WebSocket clients requires the uvicorn event loop, so we use
``asyncio.run_coroutine_threadsafe`` rather than ``asyncio.run`` to
schedule coroutines on the correct loop.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from api.ws_manager import WsManager

_ROOT = Path(__file__).parent.parent.parent  # repo root


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _check_anomaly(metric: dict[str, Any]) -> str | None:
    ret    = metric.get("mean_return")
    length = metric.get("mean_length")
    if ret    is not None and abs(float(ret))    > 1e4: return "reward_exploded"
    if length is not None and float(length) < 2:        return "episode_too_short"
    return None


def _broadcast(
    ws_manager: WsManager,
    data: Any,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """Thread-safe broadcast: schedules coroutine on the uvicorn event loop."""
    try:
        future = asyncio.run_coroutine_threadsafe(ws_manager.broadcast(data), loop)
        future.result(timeout=2)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Local (subprocess) runner
# ---------------------------------------------------------------------------

class LocalTrainingRunner:
    """subprocess-based training runner."""

    def __init__(self) -> None:
        self.state: str = "IDLE"
        self.pid:    int | None = None
        self.job_id: str | None = None          # always None for local runner
        self._last_metric: dict[str, Any] = {}
        self._proc:       subprocess.Popen | None = None  # type: ignore[type-arg]
        self._ws_manager: WsManager | None = None
        self._loop:       asyncio.AbstractEventLoop | None = None

    def start(
        self,
        ws_manager: WsManager,
        loop:       asyncio.AbstractEventLoop,
        config:     dict[str, Any] | None = None,
    ) -> None:
        if self.state == "RUNNING":
            raise RuntimeError("Training is already running.")
        self._ws_manager = ws_manager
        self._loop       = loop
        cmd = [sys.executable, str(_ROOT / "src" / "train.py")]
        if config:
            cmd += ["--config-json", json.dumps(config)]
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(_ROOT),
        )
        self.state = "RUNNING"
        self.pid   = self._proc.pid
        threading.Thread(target=self._pipe_loop, daemon=True).start()

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
        self.state = "STOPPED"

    def status(self) -> dict[str, Any]:
        return {"state": self.state, "pid": self.pid, "job_id": None,
                **self._last_metric}

    def _pipe_loop(self) -> None:
        assert self._proc is not None
        for raw in self._proc.stdout:  # type: ignore[union-attr]
            line = raw.strip()
            if not line:
                continue
            try:
                metric = json.loads(line)
                anomaly = _check_anomaly(metric)
                if anomaly:
                    metric["anomaly"] = anomaly
                self._last_metric = metric
                if self._ws_manager and self._loop:
                    _broadcast(self._ws_manager, metric, self._loop)
            except json.JSONDecodeError:
                pass
        rc         = self._proc.wait()
        self.state = "STOPPED" if rc == 0 else "FAILED"
        self.pid   = None


# ---------------------------------------------------------------------------
# Ray Jobs API runner
# ---------------------------------------------------------------------------

class RayTrainingRunner:
    """Ray Jobs API runner.

    Submits the training script as a Ray Job and tails its logs via
    ``JobSubmissionClient.tail_job_logs()``.  Metrics are parsed exactly
    the same way as the subprocess runner.

    Prerequisites
    -------------
    1. ``pip install 'ray[default]>=2.10'``
    2. ``ray start --head`` (or point to an existing cluster)
    3. Set ``HFSIM_RUNNER=ray`` before launching uvicorn.
       Optionally set ``RAY_DASHBOARD_URL`` (default: http://127.0.0.1:8265).
    """

    def __init__(self, dashboard_url: str = "http://127.0.0.1:8265") -> None:
        try:
            from ray.job_submission import JobSubmissionClient  # type: ignore[import-untyped]
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "ray is not installed — run: pip install 'ray[default]>=2.10'"
            ) from exc
        self._client     = JobSubmissionClient(dashboard_url)
        self._job_id:    str | None = None
        self._ws_manager: WsManager | None = None
        self._loop:       asyncio.AbstractEventLoop | None = None
        self._last_metric: dict[str, Any] = {}
        self.state:  str = "IDLE"
        self.pid:    int | None = None  # not applicable for Ray Jobs
        self.job_id: str | None = None

    def start(
        self,
        ws_manager: WsManager,
        loop:       asyncio.AbstractEventLoop,
        config:     dict[str, Any] | None = None,
    ) -> None:
        if self.state == "RUNNING":
            raise RuntimeError("Training is already running.")
        self._ws_manager = ws_manager
        self._loop       = loop

        cmd = f'"{sys.executable}" src/train.py'
        if config:
            # Single-quote the JSON to protect shell special characters
            safe = json.dumps(config).replace("'", "\\'")
            cmd += f" --config-json '{safe}'"

        self._job_id = self._client.submit_job(
            entrypoint=cmd,
            runtime_env={"working_dir": str(_ROOT)},
            metadata={"source": "hfsim-api"},
        )
        self.job_id  = self._job_id
        self.state   = "RUNNING"
        threading.Thread(target=self._log_tail_loop,   daemon=True).start()
        threading.Thread(target=self._status_poll_loop, daemon=True).start()

    def stop(self) -> None:
        if self._job_id:
            try:
                self._client.stop_job(self._job_id)
            except Exception:
                pass
        self.state = "STOPPED"

    def status(self) -> dict[str, Any]:
        return {"state": self.state, "pid": None, "job_id": self._job_id,
                **self._last_metric}

    # ------------------------------------------------------------------
    # Internal threads
    # ------------------------------------------------------------------

    def _log_tail_loop(self) -> None:
        assert self._job_id is not None
        try:
            for line in self._client.tail_job_logs(self._job_id):
                line = line.strip()
                if not line:
                    continue
                try:
                    metric = json.loads(line)
                    anomaly = _check_anomaly(metric)
                    if anomaly:
                        metric["anomaly"] = anomaly
                    self._last_metric = metric
                    if self._ws_manager and self._loop:
                        _broadcast(self._ws_manager, metric, self._loop)
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass

    def _status_poll_loop(self) -> None:
        """Poll Ray job status every 5 s to detect terminal states."""
        from ray.job_submission import JobStatus  # type: ignore[import-untyped]

        assert self._job_id is not None
        while self.state == "RUNNING":
            time.sleep(5)
            try:
                js = self._client.get_job_status(self._job_id)
                if js == JobStatus.SUCCEEDED:
                    self.state = "STOPPED"
                elif js == JobStatus.FAILED:
                    self.state = "FAILED"
                elif js == JobStatus.STOPPED:
                    self.state = "STOPPED"
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_runner() -> LocalTrainingRunner | RayTrainingRunner:
    """Return the appropriate runner based on the HFSIM_RUNNER env var.

    ``HFSIM_RUNNER=local`` (default) → :class:`LocalTrainingRunner`
    ``HFSIM_RUNNER=ray``            → :class:`RayTrainingRunner`
    """
    mode = os.environ.get("HFSIM_RUNNER", "local").lower()
    if mode == "ray":
        url = os.environ.get("RAY_DASHBOARD_URL", "http://127.0.0.1:8265")
        return RayTrainingRunner(dashboard_url=url)
    return LocalTrainingRunner()

"""Optuna hyperparameter sweep worker.

Runs ``src/train.py`` as a subprocess for each trial, parses stdout metrics,
and uses the mean of the last 5 episode returns as the objective value.

Requires ``pip install optuna``.  Falls back to random search if Optuna is
not installed (same search space, uniform sampling, no Bayesian update).

Search space (defaults)
-----------------------
train_steps      int   [5, 40]
batch_size       cat   [16, 32, 64]
seq_len          cat   [20, 50, 100]
collect_per_iter cat   [2, 4, 8]

State machine: IDLE → RUNNING → STOPPED | FAILED
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np

_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Trial result type
# ---------------------------------------------------------------------------

class TrialRecord:
    def __init__(self, number: int, params: dict[str, Any]) -> None:
        self.number  = number
        self.params  = params
        self.value:  float | None = None
        self.state:  str = "RUNNING"     # RUNNING | COMPLETE | PRUNED | FAILED

    def to_dict(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "params": self.params,
            "value":  self.value,
            "state":  self.state,
        }


# ---------------------------------------------------------------------------
# Subprocess trial runner
# ---------------------------------------------------------------------------

def _run_trial_subprocess(
    params: dict[str, Any],
    n_episodes: int,
    stop_event: threading.Event,
) -> float | None:
    """Run one trial of train.py; return mean of last-5 episode returns."""
    config = {**params, "episodes": n_episodes}
    cmd = [
        sys.executable,
        str(_ROOT / "src" / "train.py"),
        "--config-json", json.dumps(config),
    ]
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(_ROOT),
        )
    except Exception:
        return None

    returns: list[float] = []
    for raw in proc.stdout:  # type: ignore[union-attr]
        if stop_event.is_set():
            proc.terminate()
            break
        line = raw.strip()
        if not line:
            continue
        try:
            m = json.loads(line)
            if "mean_return" in m and m["mean_return"] is not None:
                returns.append(float(m["mean_return"]))
        except json.JSONDecodeError:
            pass

    proc.wait()
    if not returns:
        return None
    tail = returns[-5:]
    return float(np.mean(tail))


# ---------------------------------------------------------------------------
# SweepRunner
# ---------------------------------------------------------------------------

class SweepRunner:
    """Manages an Optuna (or random) hyperparameter sweep."""

    def __init__(self) -> None:
        self.state:       str = "IDLE"
        self.n_trials:    int = 0
        self.n_done:      int = 0
        self.best_value:  float | None = None
        self.best_params: dict[str, Any] | None = None
        self._trials:     list[TrialRecord] = []
        self._stop:       threading.Event = threading.Event()
        self._lock:       threading.Lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, config: dict[str, Any] | None = None) -> None:
        if self.state == "RUNNING":
            raise RuntimeError("Sweep is already running.")
        cfg = config or {}
        self._stop.clear()
        self.n_trials    = int(cfg.get("n_trials",             10))
        self.n_done      = 0
        self.best_value  = None
        self.best_params = None
        self._trials     = []
        self.state       = "RUNNING"
        threading.Thread(
            target=self._sweep_loop,
            args=(cfg,),
            daemon=True,
        ).start()

    def stop(self) -> None:
        self._stop.set()
        self.state = "STOPPED"

    def status(self) -> dict[str, Any]:
        return {
            "state":       self.state,
            "n_trials":    self.n_trials,
            "n_done":      self.n_done,
            "best_value":  self.best_value,
            "best_params": self.best_params,
        }

    def get_trials(self) -> list[dict[str, Any]]:
        with self._lock:
            return [t.to_dict() for t in self._trials]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _record_result(self, rec: TrialRecord) -> None:
        with self._lock:
            self._trials.append(rec)
        self.n_done += 1
        if rec.value is not None:
            if self.best_value is None or rec.value > self.best_value:
                self.best_value  = rec.value
                self.best_params = rec.params

    def _sweep_loop(self, cfg: dict[str, Any]) -> None:
        n_episodes = int(cfg.get("n_episodes_per_trial", 50))
        try:
            self._run_optuna(cfg, n_episodes)
        except ImportError:
            self._run_random(n_episodes)
        except Exception:
            self.state = "FAILED"
            return
        if not self._stop.is_set():
            self.state = "STOPPED"

    # -- Optuna path --

    def _run_optuna(self, cfg: dict[str, Any], n_episodes: int) -> None:
        import optuna  # type: ignore[import-untyped]
        optuna.logging.set_verbosity(optuna.logging.WARNING)

        study = optuna.create_study(direction="maximize")

        def objective(trial: Any) -> float:
            if self._stop.is_set():
                raise optuna.TrialPruned()
            params = _sample_optuna(trial)
            rec = TrialRecord(trial.number, params)
            val = _run_trial_subprocess(params, n_episodes, self._stop)
            if val is None:
                rec.state = "FAILED"
                self._record_result(rec)
                raise optuna.TrialPruned()
            rec.value = val
            rec.state = "COMPLETE"
            self._record_result(rec)
            return val

        study.optimize(objective, n_trials=self.n_trials)

    # -- Random fallback path --

    def _run_random(self, n_episodes: int) -> None:
        rng = np.random.default_rng()
        for i in range(self.n_trials):
            if self._stop.is_set():
                break
            params = _sample_random(rng)
            rec = TrialRecord(i, params)
            val = _run_trial_subprocess(params, n_episodes, self._stop)
            if val is None:
                rec.state = "FAILED"
            else:
                rec.value = val
                rec.state = "COMPLETE"
            self._record_result(rec)


# ---------------------------------------------------------------------------
# Search-space samplers
# ---------------------------------------------------------------------------

def _sample_optuna(trial: Any) -> dict[str, Any]:
    return {
        "train_steps":      trial.suggest_int("train_steps",       5,  40),
        "batch_size":       trial.suggest_categorical("batch_size", [16, 32, 64]),
        "seq_len":          trial.suggest_categorical("seq_len",    [20, 50, 100]),
        "collect_per_iter": trial.suggest_categorical("collect_per_iter", [2, 4, 8]),
    }


def _sample_random(rng: np.random.Generator) -> dict[str, Any]:
    return {
        "train_steps":      int(rng.integers(5, 41)),
        "batch_size":       int(rng.choice([16, 32, 64])),
        "seq_len":          int(rng.choice([20, 50, 100])),
        "collect_per_iter": int(rng.choice([2, 4, 8])),
    }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_sweep_runner() -> SweepRunner:
    return SweepRunner()

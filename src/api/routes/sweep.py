"""Hyperparameter sweep endpoints.

POST /api/sweep/start    — start a sweep (Optuna or random fallback)
POST /api/sweep/stop     — stop current sweep
GET  /api/sweep/status   — {state, n_trials, n_done, best_value, best_params}
GET  /api/sweep/trials   — list of all trial dicts
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

# Ensure src/ is on path when imported from routes/
_SRC = Path(__file__).parent.parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from sweep_worker import SweepRunner

router = APIRouter()
_runner = SweepRunner()


class SweepRequest(BaseModel):
    n_trials:             int = 10
    n_episodes_per_trial: int = 50


@router.post("/start")
def start_sweep(body: SweepRequest = SweepRequest()) -> dict[str, Any]:
    try:
        _runner.start({
            "n_trials":             body.n_trials,
            "n_episodes_per_trial": body.n_episodes_per_trial,
        })
    except RuntimeError as exc:
        return {"ok": False, "detail": str(exc)}
    return {"ok": True}


@router.post("/stop")
def stop_sweep() -> dict[str, Any]:
    _runner.stop()
    return {"ok": True, "state": _runner.state}


@router.get("/status")
def sweep_status() -> dict[str, Any]:
    return _runner.status()


@router.get("/trials")
def sweep_trials() -> list[dict[str, Any]]:
    return _runner.get_trials()

"""Log file endpoints.

GET /api/logs                       — list .jsonl / .parquet files in reports/
GET /api/logs/{path:path}/entries   — return log entries as JSON
GET /api/logs/{path:path}/branches  — return distinct branch_ids
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

# Ensure src/ is on path when imported by uvicorn
_SRC = Path(__file__).parent.parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from hf_sim.log_store import read_log

_REPORTS = Path(__file__).parent.parent.parent.parent / "reports"
_ALLOWED_SUFFIXES = {".jsonl", ".parquet"}

router = APIRouter()


def _list_files(base: Path) -> list[dict[str, Any]]:
    if not base.exists():
        return []
    return [
        {"name": f.name, "path": f.name, "size_bytes": f.stat().st_size}
        for f in sorted(base.iterdir())
        if f.suffix in _ALLOWED_SUFFIXES
    ]


def _load(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Log not found: {path.name}")
    try:
        return read_log(path)
    except RuntimeError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read log: {exc}") from exc


@router.get("")
def list_logs() -> list[dict[str, Any]]:
    return _list_files(_REPORTS)


@router.get("/{path:path}/branches")
def get_branches(path: str) -> list[str]:
    entries = _load(_REPORTS / path)
    seen: list[str] = []
    for e in entries:
        b = e.get("branch_id", "main")
        if b not in seen:
            seen.append(b)
    return seen


@router.get("/{path:path}/entries")
def get_entries(
    path: str,
    branch: str | None = Query(default=None),
    step_from: int = Query(default=0, ge=0),
    step_to: int = Query(default=99_999, ge=0),
) -> list[dict[str, Any]]:
    entries = _load(_REPORTS / path)
    if branch is not None:
        entries = [e for e in entries if e.get("branch_id") == branch]
    return entries[step_from : step_to + 1]

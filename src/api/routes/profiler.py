"""Profiler trace endpoints.

GET  /api/profiler/traces         — list Chrome trace files in reports/profiler/
GET  /api/profiler/traces/{name}  — download a single trace JSON
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

_PROF_DIR = Path(__file__).parent.parent.parent.parent / "reports" / "profiler"


@router.get("/traces")
def list_traces() -> list[dict]:
    if not _PROF_DIR.exists():
        return []
    return sorted(
        [
            {
                "name":       p.name,
                "size_bytes": p.stat().st_size,
                "mtime":      p.stat().st_mtime,
            }
            for p in _PROF_DIR.glob("trace_*.json")
        ],
        key=lambda x: x["mtime"],
        reverse=True,
    )


@router.get("/traces/{name}")
def get_trace(name: str) -> FileResponse:
    p = (_PROF_DIR / name).resolve()
    # Guard against path traversal
    if _PROF_DIR.resolve() not in p.parents:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="Trace not found")
    return FileResponse(p, media_type="application/json", filename=name)

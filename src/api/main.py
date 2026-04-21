"""HF_Sim FastAPI application.

Launch::

    uvicorn src.api.main:app --port 8000 --reload

Endpoints
---------
GET  /api/logs                        list replay log files
GET  /api/logs/{path}/entries         return log entries
GET  /api/logs/{path}/branches        return branch ids
POST /api/training/start              spawn training subprocess or Ray job
POST /api/training/stop               terminate training
GET  /api/training/status             current state dict
WS   /api/training/stream             live metrics JSON stream
GET  /api/profiler/traces             list Chrome trace files
GET  /api/profiler/traces/{name}      download a trace file
POST /api/sweep/start                 start Optuna hyperparameter sweep
POST /api/sweep/stop                  stop sweep
GET  /api/sweep/status                sweep state + best params
GET  /api/sweep/trials                all trial results
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is importable when the module is loaded by uvicorn directly
_SRC = Path(__file__).parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes import logs, profiler, sweep, training

app = FastAPI(title="HF_Sim API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(logs.router,     prefix="/api/logs",     tags=["logs"])
app.include_router(training.router, prefix="/api/training", tags=["training"])
app.include_router(profiler.router, prefix="/api/profiler", tags=["profiler"])
app.include_router(sweep.router,    prefix="/api/sweep",    tags=["sweep"])


@app.get("/healthz")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Serve the built React app (production).
# In dev, run `npm run dev` in frontend/ and visit http://localhost:3000.
_static = _SRC / "api" / "static"
if _static.exists():
    app.mount("/", StaticFiles(directory=_static, html=True), name="static")

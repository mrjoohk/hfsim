"""Training control endpoints + WebSocket stream.

POST /api/training/start   — spawn training subprocess or Ray job
POST /api/training/stop    — terminate training
GET  /api/training/status  — current state dict
WS   /api/training/stream  — live metrics JSON stream
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from api.training_runner import create_runner
from api.ws_manager import WsManager

router = APIRouter()

# Singletons shared across requests within the same server process
_runner = create_runner()
_ws_manager = WsManager()


class StartRequest(BaseModel):
    config: dict[str, Any] = {}


@router.post("/start")
async def start_training(body: StartRequest = StartRequest()) -> dict[str, Any]:
    loop = asyncio.get_event_loop()
    try:
        _runner.start(_ws_manager, loop, config=body.config or None)
    except RuntimeError as exc:
        return {"ok": False, "detail": str(exc)}
    return {"ok": True, "pid": _runner.pid, "job_id": _runner.job_id}


@router.post("/stop")
def stop_training() -> dict[str, Any]:
    _runner.stop()
    return {"ok": True, "state": _runner.state}


@router.get("/status")
def training_status() -> dict[str, Any]:
    return _runner.status()


@router.websocket("/stream")
async def training_stream(ws: WebSocket) -> None:
    await _ws_manager.connect(ws)
    try:
        while True:
            # Keep connection alive; actual pushes come from runner's pipe/log loop
            await ws.receive_text()
    except WebSocketDisconnect:
        await _ws_manager.disconnect(ws)

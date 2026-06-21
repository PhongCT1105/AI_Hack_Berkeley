"""Degradation monitor: manual trigger + read-only status for the demo.

POST /run does the real work (scan, auto-queue, retrain-if-ready).
GET /status is side-effect-free — just reports current findings/queue/model.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.config import settings
from app.ml import model_registry, retrain_queue
from app.ml import terac_auto_launch_store
from app.services import degradation, monitor

router = APIRouter(prefix="/api/monitor", tags=["monitor"])


@router.post("/run")
async def run(request: Request) -> dict:
    pipeline = request.app.state.pipeline
    history = request.app.state.score_history
    return await monitor.run_check(pipeline, history)


@router.get("/status")
async def status(request: Request) -> dict:
    history = request.app.state.score_history
    reports = degradation.scan_all_domains(history)
    return {
        "reports": [r.__dict__ for r in reports],
        "queue": retrain_queue.list_queue(),
        "model_loaded": model_registry.is_loaded(),
        "model_meta": model_registry.meta(),
        "terac_auto_launch": {
            "mode": settings.terac_auto_launch_mode,
            "max_total": settings.terac_auto_launch_max_total,
            "cooldown_hours": settings.terac_auto_launch_cooldown_hours,
            "launches": terac_auto_launch_store.list_launches(),
        },
    }

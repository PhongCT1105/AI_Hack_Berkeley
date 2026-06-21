"""POST /api/score-source, the core credibility endpoint a calling agent hits."""
from __future__ import annotations

import logging
import sys
import threading

from fastapi import APIRouter, BackgroundTasks, Request

from app.core.config import settings
from app.core.observability import capture_exception
from app.schemas.score import ScoreRequest, ScoreResponse
from app.services import monitor

router = APIRouter(prefix="/api", tags=["score"])
logger = logging.getLogger("captain_america.api.score")

_call_count = 0
_call_count_lock = threading.Lock()


def _should_check_now() -> bool:
    """Throttle the auto-monitor so it doesn't run on every single call."""
    global _call_count
    with _call_count_lock:
        _call_count += 1
        return _call_count % settings.monitor_check_every_n_calls == 0


async def _run_monitor_check(pipeline, history) -> None:
    try:
        await monitor.run_check(pipeline, history)
    except Exception as exc:  # pragma: no cover - best effort, never blocks scoring
        logger.warning("background monitor check failed: %s", exc)


@router.post("/score-source", response_model=ScoreResponse)
async def score_source(req: ScoreRequest, request: Request, background_tasks: BackgroundTasks) -> ScoreResponse:
    pipeline = request.app.state.pipeline
    # Keep the old header during the brand migration so existing integrations
    # retain their source history. New callers should use X-Captain-America-Caller.
    caller = (
        request.headers.get("x-captain-america-caller")
        or request.headers.get("x-agentshield-caller")
        or "api"
    )
    logger.info("score_source caller=%s url=%s task=%s", caller, req.url, req.task)
    print(
        f"[Captain America] score_source caller={caller} url={req.url} task={req.task}",
        file=sys.stderr,
        flush=True,
    )
    try:
        response = await pipeline.score_source(req)
        history = getattr(request.app.state, "score_history", None)
        if history is not None:
            history.record(
                caller=caller,
                request_url=req.url,
                request_task=req.task,
                response=response,
            )
            if _should_check_now():
                background_tasks.add_task(_run_monitor_check, pipeline, history)
        return response
    except Exception as exc:
        capture_exception(exc)
        raise

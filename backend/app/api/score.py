"""POST /api/score-source — the core credibility endpoint a calling agent hits."""
from __future__ import annotations

import logging
import sys

from fastapi import APIRouter, Request

from app.core.observability import capture_exception
from app.schemas.score import ScoreRequest, ScoreResponse

router = APIRouter(prefix="/api", tags=["score"])
logger = logging.getLogger("agentshield.api.score")


@router.post("/score-source", response_model=ScoreResponse)
async def score_source(req: ScoreRequest, request: Request) -> ScoreResponse:
    pipeline = request.app.state.pipeline
    caller = request.headers.get("x-agentshield-caller", "api")
    logger.info("score_source caller=%s url=%s task=%s", caller, req.url, req.task)
    print(
        f"[AgentShield] score_source caller={caller} url={req.url} task={req.task}",
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
        return response
    except Exception as exc:
        capture_exception(exc)
        raise

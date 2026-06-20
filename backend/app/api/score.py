"""POST /api/score-source — the core credibility endpoint a calling agent hits."""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.observability import capture_exception
from app.schemas.score import ScoreRequest, ScoreResponse

router = APIRouter(prefix="/api", tags=["score"])


@router.post("/score-source", response_model=ScoreResponse)
async def score_source(req: ScoreRequest, request: Request) -> ScoreResponse:
    pipeline = request.app.state.pipeline
    try:
        return await pipeline.score_source(req)
    except Exception as exc:
        capture_exception(exc)
        raise

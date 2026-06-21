"""SSE transcript for the side-by-side showcase: heuristic ranker + no
compression vs. our compressed pipeline + a freshly-fit candidate model.
GET (not POST) so the browser can use a plain EventSource."""
from __future__ import annotations

import json

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.services.comparison_demo import stream_comparison

router = APIRouter(prefix="/api/comparison", tags=["comparison"])


@router.get("/stream")
async def stream(
    request: Request,
    prompt: str = Query(..., min_length=3),
    max_sources: int = Query(6, ge=1, le=20),
) -> StreamingResponse:
    pipeline = request.app.state.pipeline

    async def gen():
        async for event in stream_comparison(pipeline, prompt, max_sources):
            yield f"data: {json.dumps(event, default=str)}\n\n"
        yield 'data: {"type": "done"}\n\n'

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

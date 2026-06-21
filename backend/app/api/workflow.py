"""SSE transcript of a real /api/research-equivalent run, for the showcase
page. GET (not POST) so the browser can use a plain EventSource."""
from __future__ import annotations

import json

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.services.workflow_demo import stream_workflow

router = APIRouter(prefix="/api/workflow", tags=["workflow"])


@router.get("/stream")
async def stream(
    request: Request,
    prompt: str = Query(..., min_length=3),
    max_sources: int = Query(6, ge=1, le=20),
) -> StreamingResponse:
    pipeline = request.app.state.pipeline
    history = request.app.state.score_history

    async def gen():
        async for event in stream_workflow(pipeline, history, prompt, max_sources):
            yield f"data: {json.dumps(event, default=str)}\n\n"
        yield 'data: {"type": "done"}\n\n'

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

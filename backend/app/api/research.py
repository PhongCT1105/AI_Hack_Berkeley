from fastapi import APIRouter, Request

from app.schemas.research import ResearchRequest, ResearchResponse
from app.services.research_agent import ResearchAgent

router = APIRouter(prefix="/api", tags=["research"])


@router.post("/research", response_model=ResearchResponse)
async def research(request_body: ResearchRequest, request: Request) -> ResearchResponse:
    return await ResearchAgent(request.app.state.pipeline).run(request_body)

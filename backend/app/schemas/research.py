from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.score import ScoreResponse


class ResearchRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    max_sources: int = Field(default=20, ge=1, le=100)


class ResearchResponse(BaseModel):
    prompt: str
    search_query: str
    discovered_count: int
    inspected_count: int
    agent_mode: str
    search_mode: str
    answer: str
    cited_sources: list[ScoreResponse] = Field(default_factory=list)
    rejected_sources: list[ScoreResponse] = Field(default_factory=list)

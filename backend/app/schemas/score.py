"""Pydantic schemas for the credibility-scoring engine.

`ScoreResponse` is the single contract shared by the FastAPI endpoint, the
FastMCP tool, and the frontend TS types.
"""
from enum import Enum

from pydantic import BaseModel, Field


class Recommendation(str, Enum):
    USE = "USE"
    CAUTION = "CAUTION"
    AVOID = "AVOID"


class ScoreRequest(BaseModel):
    # url is a plain str (not HttpUrl) so the fallback path can handle odd inputs
    # without a 422 — the collector decides what to do with a bad URL.
    url: str = Field(..., description="The web source to evaluate")
    task: str = Field(..., description="What the calling agent intends to do with this source")


class Claim(BaseModel):
    text: str
    supported: bool = Field(description="Backed by evidence present on the page?")
    evidence_snippet: str | None = None
    confidence: float = Field(default=0.5, ge=0, le=1)


class Verdict(BaseModel):
    dimension: str = Field(description='e.g. "authorship", "citations", "recency"')
    passed: bool = Field(description="Did the source pass this credibility dimension?")
    detail: str
    weight: float = Field(description="Contribution magnitude toward the score")


class SourceFeatures(BaseModel):
    https: bool = False
    has_author: bool = False
    has_citations: bool = False
    citation_count: int = 0
    ad_density: float = Field(default=0.0, ge=0, le=1)
    domain_reputation: float = Field(default=0.5, ge=0, le=1)
    domain_listed: str | None = None          # "allow" | "block" | None
    clickbait_score: float = Field(default=0.0, ge=0, le=1)
    recency_days: int | None = None
    word_count: int = 0
    outbound_link_count: int = 0
    collector_mode: str = "httpx_fallback"    # "firecrawl" | "httpx_fallback"
    extractor_mode: str = "heuristic_fallback"  # "claude" | "heuristic_fallback"


class FeatureContribution(BaseModel):
    feature: str
    value: float | bool | int | str | None
    points: float = Field(description="Signed contribution to the trust score")


class EvidenceCapsule(BaseModel):
    compressed_text: str
    key_reasons: list[str] = Field(default_factory=list)
    token_estimate_before: int = 0
    token_estimate_after: int = 0
    method: str = "extractive_fallback"       # "claude" | "extractive_fallback"


class CitationAssessment(BaseModel):
    """Claim/source citation-usability result from the optional trained model."""

    available: bool = False
    usable_probability: float | None = Field(default=None, ge=0, le=1)
    threshold: float | None = Field(default=None, ge=0, le=1)
    eligible: bool | None = None
    model_version: str | None = None
    error: str | None = None


class ScoreResponse(BaseModel):
    url: str
    task: str
    domain: str
    trust_score: int = Field(ge=0, le=100)
    recommendation: Recommendation
    risk_tags: list[str] = Field(default_factory=list)
    verdicts: list[Verdict] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    citation_assessment: CitationAssessment = Field(default_factory=CitationAssessment)
    evidence_capsule: EvidenceCapsule
    source_features: SourceFeatures
    contributions: list[FeatureContribution] = Field(default_factory=list)
    scorer_mode: str = "heuristic"            # "heuristic" | "logistic_model"
    degradations: list[str] = Field(default_factory=list)
    latency_ms: int = 0
    trace_id: str

"""Schemas for Browserbase crawl requests and Terac training data outputs."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CrawlRequest(BaseModel):
    urls: list[str] = Field(..., min_length=1, description="Absolute URLs to crawl")
    query: str | None = Field(default=None, description="Optional upstream query that produced the URLs")
    max_pages: int = Field(default=5, ge=1, le=25, description="Maximum pages to crawl from the input list")
    page_timeout_ms: int = Field(default=60000, ge=5000, le=180000, description="Per-page navigation timeout")
    text_limit: int = Field(default=12000, ge=1000, le=50000, description="Maximum visible text characters to keep per page")


class ClaimCandidate(BaseModel):
    claim_text: str
    evidence_snippet: str
    confidence: float = Field(ge=0.0, le=1.0)
    extracted_by: str = "heuristic"
    evidence_start: int | None = None
    evidence_end: int | None = None


class TrustSignal(BaseModel):
    kind: str
    detail: str


class SourceProfile(BaseModel):
    domain: str
    canonical_url: str | None = None
    content_length: int
    extracted_link_count: int
    outbound_link_count: int
    published_time: str | None = None


class TeracTrustEvaluationRequest(BaseModel):
    domain: str
    url: str


class TeracClaimFeature(BaseModel):
    claim: str
    context_snippet: str
    source_trust_score: float


class TeracExtractedFeaturesForLabeling(BaseModel):
    outbound_link_density_ratio: float
    has_verified_ssl: bool
    top_extracted_claims: list[TeracClaimFeature] = Field(default_factory=list)


class TeracTrainingPayload(BaseModel):
    trust_evaluation_request: TeracTrustEvaluationRequest
    extracted_features_for_labeling: TeracExtractedFeaturesForLabeling


class CredibilityCapsule(BaseModel):
    version: str = "capsule-v1"
    source_url: str
    title: str | None = None
    compact_summary: str
    claim_count: int
    evidence_count: int
    trust_signals: list[TrustSignal] = Field(default_factory=list)


class CrawlPageResult(BaseModel):
    requested_url: str
    final_url: str
    title: str | None = None
    meta_description: str | None = None
    author: str | None = None
    published_time: str | None = None
    source_profile: SourceProfile
    fetched_at: datetime
    text_excerpt: str
    links: list[dict[str, str]] = Field(default_factory=list)
    claim_candidates: list[ClaimCandidate] = Field(default_factory=list)
    trust_signals: list[TrustSignal] = Field(default_factory=list)
    credibility_capsule: CredibilityCapsule
    terac_payload: TeracTrainingPayload


class CrawlBatchResponse(BaseModel):
    session_id: str
    session_url: str
    query: str | None = None
    requested_urls: list[str]
    total_pages: int
    started_at: datetime
    finished_at: datetime
    pages: list[CrawlPageResult]
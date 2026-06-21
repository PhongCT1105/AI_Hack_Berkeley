"""Schemas for the Captain America demo pipeline (mocked-first build).

UI-ONLY THIS BUILD: /api/demo-results and /api/demo-run return deterministic,
synthetic data classified from `app/data/finance_domains.py` rather than running
the real collector/extractor/Browserbase pipeline — fast + reliable for live
demos. `app/services/pipeline.py` (Pipeline.score_source) already implements the
real thing; swap these endpoints to call it once latency/network are acceptable
for a judge-facing demo. See # TODO(real-pipeline) markers in app/api/demo.py.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class DemoRunRequest(BaseModel):
    task: str
    urls: list[str] = Field(default_factory=list)


class DemoSource(BaseModel):
    id: str
    url: str
    domain: str
    title: str
    sourceType: str
    trustScore: int = Field(ge=0, le=100)
    baseScore: int = Field(ge=0, le=100)
    trainedScore: int = Field(ge=0, le=100)
    recommendation: str  # "cite" | "use_with_caution" | "do_not_cite"
    riskTags: list[str] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)
    evidenceQuality: str  # "strong" | "medium" | "weak"
    citationQuality: str  # "strong" | "medium" | "weak"
    capsule: dict
    rawTokens: int
    capsuleTokens: int
    compressionPct: float


class EvalExample(BaseModel):
    task: str
    source_a: str
    source_b: str
    human_preferred: str  # "a" | "b"
    base_predicted: str  # "a" | "b"
    trained_predicted: str  # "a" | "b"
    result: str  # "base_wrong_trained_right" | "both_right" | "both_wrong" | ...


class EvalMetrics(BaseModel):
    base_accuracy: float
    trained_accuracy: float
    improvement_pct: float
    held_out_examples: int
    human_preference_match: float
    bad_source_filtering_precision: float
    cite_do_not_cite_accuracy: float
    avg_token_reduction_pct: float
    raw_tokens_example: int
    capsule_tokens_example: int
    examples: list[EvalExample]


class ArenaLabelRequest(BaseModel):
    pair_id: str
    task: str
    domain_a: str
    domain_b: str
    preferred: str  # "a" | "b" | "neither"
    checklist: dict = Field(default_factory=dict)
    free_text: str | None = None

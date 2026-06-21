"""Schemas for the Terac pairwise Source-Comparison Arena.

NOTE (UI-only this build): these power the demoable Arena screen and a local
JSON-backed stub store. A teammate wires the real Terac API/MCP + model training
later — see app/ml/trainer.py and app/ml/model_registry.py for the # TODO(terac)
seams. The shapes here ARE the contract the live integration must satisfy.
"""
from pydantic import BaseModel, Field


class FeedbackForm(BaseModel):
    """Checklist a Terac annotator fills in — mirrors the verdict dimensions so
    human judgement stays aligned with what the model scores."""
    author_credible: bool | None = None
    citations_sufficient: bool | None = None
    recency_adequate: bool | None = None
    not_clickbait: bool | None = None
    domain_trusted: bool | None = None
    free_text: str | None = None


class ComparisonPair(BaseModel):
    pair_id: str
    task: str
    url_a: str
    url_b: str
    domain_a: str
    domain_b: str
    score_a: int
    score_b: int
    reasons_a: list[str] = Field(default_factory=list)
    reasons_b: list[str] = Field(default_factory=list)
    labeled: bool = False


class CreatePairRequest(BaseModel):
    task: str
    url_a: str
    url_b: str


class LabelSubmission(BaseModel):
    pair_id: str
    winner: str = Field(pattern="^(a|b|tie)$", description="Which source is more credible")
    annotator: str | None = None
    checklist: FeedbackForm | None = None


class ModelStatus(BaseModel):
    loaded: bool = False
    trained_at: str | None = None
    n_labels_used: int = 0
    coefficients: dict[str, float] | None = None
    active_scorer: str = "heuristic"          # "logistic_model" | "heuristic"
    note: str | None = None                   # e.g. "Terac training not configured yet"

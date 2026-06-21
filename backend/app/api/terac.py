"""Terac Source-Comparison Arena endpoints.

UI-ONLY THIS BUILD: /pairs, /pairs/next and /labels work against a local JSON
store so the Arena screen is fully demoable. /train and /model return a clear
"not configured" status — a teammate wires the real Terac API/MCP + training
later (see app/ml/trainer.py and app/ml/terac_store.py # TODO(terac) notes).
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.ml import model_registry, terac_store, trainer
from app.schemas.score import ScoreRequest
from app.schemas.terac import (
    ComparisonPair,
    CreatePairRequest,
    LabelSubmission,
    ModelStatus,
)

router = APIRouter(prefix="/api/terac", tags=["terac"])


@router.post("/pairs", response_model=ComparisonPair)
async def create_pair(body: CreatePairRequest, request: Request) -> ComparisonPair:
    """Score two sources for the same task and store them as a comparison pair."""
    pipeline = request.app.state.pipeline
    a = await pipeline.score_source(ScoreRequest(url=body.url_a, task=body.task))
    b = await pipeline.score_source(ScoreRequest(url=body.url_b, task=body.task))

    pair = terac_store.add_pair({
        "task": body.task,
        "url_a": a.url, "url_b": b.url,
        "domain_a": a.domain, "domain_b": b.domain,
        "score_a": a.trust_score, "score_b": b.trust_score,
        "reasons_a": [v.detail for v in a.verdicts[:4]],
        "reasons_b": [v.detail for v in b.verdicts[:4]],
    })
    return ComparisonPair(**pair)


@router.get("/pairs/next", response_model=ComparisonPair | None)
async def next_pair() -> ComparisonPair | None:
    pair = terac_store.next_unlabeled()
    return ComparisonPair(**pair) if pair else None


@router.get("/pairs", response_model=list[ComparisonPair])
async def list_pairs() -> list[ComparisonPair]:
    return [ComparisonPair(**p) for p in terac_store.all_pairs()]


@router.post("/labels")
async def submit_label(label: LabelSubmission) -> dict:
    terac_store.add_label(label.model_dump())
    return {"ok": True, "label_count": terac_store.label_count()}


@router.post("/train", response_model=ModelStatus)
async def train() -> ModelStatus:
    result = trainer.train()  # stub — see trainer.py TODO(terac)
    if result.get("trained"):
        model_registry.load()
    return _model_status(note=result.get("note"))


@router.get("/model", response_model=ModelStatus)
async def model_status() -> ModelStatus:
    return _model_status()


def _model_status(note: str | None = None) -> ModelStatus:
    loaded = model_registry.is_loaded()
    return ModelStatus(
        loaded=loaded,
        trained_at=model_registry.meta().get("trained_at"),
        n_labels_used=terac_store.label_count(),
        coefficients=model_registry.coefficients(),
        active_scorer="logistic_model" if loaded else "heuristic",
        note=note or (None if loaded else "Terac training not configured yet (UI-only build)."),
    )

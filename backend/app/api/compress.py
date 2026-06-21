"""Compression endpoints for The Token Company challenge demo."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.schemas.compress import CompressionRequest, CompressionResponse
from app.services.prompt_compressor import CompressionConfig, PromptCompressor
from app.services.semantic_ir_compressor import FinanceCredibilityCompressor, SemanticIRCompressor

router = APIRouter(prefix="/api", tags=["compression"])
_EVALUATION_REPORT = Path(__file__).resolve().parents[2] / "data" / "compression_evaluations" / "latest.json"


@router.post("/compress", response_model=CompressionResponse)
def compress(req: CompressionRequest) -> CompressionResponse:
    if req.method == "sentence_selector":
        result = PromptCompressor(CompressionConfig(use_llmlingua2=False)).compress(
            req.text,
            query=req.query,
        )
        original_tokens = _token_estimate(result.normalized_text)
        compressed_tokens = _token_estimate(result.compressed_text)
        preserved, missing = _preservation_items(result.compressed_text, req.query)
        return CompressionResponse(
            method=req.method,
            original_text=result.original_text,
            compressed_text=result.compressed_text,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            compression_ratio=compressed_tokens / original_tokens if original_tokens else 0.0,
            token_savings_percent=_savings(original_tokens, compressed_tokens),
            preservation_score=_preservation_score(preserved, missing),
            preserved_items=preserved,
            missing_items=missing,
            notes=list(result.notes),
        )

    if req.method == "finance_credibility":
        result = FinanceCredibilityCompressor().compress(req.text)
        preserved, missing = _preservation_items(result.compact_language, req.query)
        return CompressionResponse(
            method=req.method,
            original_text=result.original_text,
            compressed_text=result.compact_language,
            reconstructed_prompt=result.reconstructed_prompt,
            original_tokens=result.original_token_estimate,
            compressed_tokens=result.compact_token_estimate,
            compression_ratio=result.compression_ratio,
            token_savings_percent=_savings(result.original_token_estimate, result.compact_token_estimate),
            preservation_score=_preservation_score(preserved, missing),
            preserved_items=preserved,
            missing_items=missing,
            notes=list(result.notes),
        )

    result = SemanticIRCompressor().compress(req.text)
    preserved, missing = _preservation_items(
        "\n".join([result.compact_language, result.reconstructed_prompt]),
        req.query,
    )
    return CompressionResponse(
        method=req.method,
        original_text=result.original_text,
        compressed_text=result.compact_language,
        reconstructed_prompt=result.reconstructed_prompt,
        original_tokens=result.original_token_estimate,
        compressed_tokens=result.compact_token_estimate,
        compression_ratio=result.compression_ratio,
        token_savings_percent=_savings(result.original_token_estimate, result.compact_token_estimate),
        preservation_score=_preservation_score(preserved, missing),
        preserved_items=preserved,
        missing_items=missing,
        semantic_ir=asdict(result.semantic_ir),
        notes=list(result.notes),
    )


@router.get("/compress/evaluations/latest")
def latest_compression_evaluation() -> dict:
    """Return the saved raw/compressed prompt pairs for visualization."""

    try:
        with _EVALUATION_REPORT.open(encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="No compression evaluation yet. Run scripts/eval_ttc_compression.py first.",
        ) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Latest compression evaluation is invalid JSON.") from exc


def _token_estimate(text: str) -> int:
    return max(1, round(len(text) / 4))


def _savings(original_tokens: int, compressed_tokens: int) -> int:
    if original_tokens <= 0:
        return 0
    return max(0, round((1 - compressed_tokens / original_tokens) * 100))


def _preservation_items(text: str, query: str | None) -> tuple[list[str], list[str]]:
    if not query:
        return [], []
    required = [item.strip() for item in query.split(",") if item.strip()]
    lowered = text.casefold()
    preserved = [item for item in required if item.casefold() in lowered]
    missing = [item for item in required if item.casefold() not in lowered]
    return preserved, missing


def _preservation_score(preserved: list[str], missing: list[str]) -> float | None:
    total = len(preserved) + len(missing)
    if total == 0:
        return None
    return round(len(preserved) / total, 3)

"""Stage 5 — Credibility Capsule (context compression).

This is the Token Company track: reduce 800–1500 tokens of raw source context to
a compact evidence packet (~capsule_token_budget tokens) that PRESERVES the top
credibility reasons + key claims, so a downstream agent gets the verdict cheaply.

Primary: FinanceCredibilityCompressor, a domain-specific compression model that
extracts the finance signals a downstream trust agent needs. Fallback:
extractive — rank sentences containing claim/evidence keywords and pack the top
ones within budget.
"""
from __future__ import annotations

import logging
import re

from app.core.config import settings
from app.schemas.score import EvidenceCapsule, SourceFeatures
from app.services.collector import CollectResult
from app.services.extractor import ExtractResult
from app.services.semantic_ir_compressor import FinanceCredibilityCompressor

logger = logging.getLogger("captain_america.capsule")


def _est_tokens(text: str) -> int:
    # ~4 chars per token heuristic — good enough for a before/after demo number.
    return max(1, round(len(text) / 4))


async def compress(
    collected: CollectResult,
    extracted: ExtractResult,
    features: SourceFeatures,
    top_reasons: list[str],
) -> EvidenceCapsule:
    before = _est_tokens(collected.text)

    if collected.text:
        try:
            return _compress_finance_credibility(collected, extracted, top_reasons, before)
        except Exception as exc:
            logger.warning("Finance credibility capsule failed, using extractive: %s", exc)

    return _compress_extractive(collected, extracted, top_reasons, before)


# ------------------------------------------------------------------ #
def _compress_finance_credibility(
    collected: CollectResult,
    extracted: ExtractResult,
    top_reasons: list[str],
    before: int,
) -> EvidenceCapsule:
    """Build a compact, deterministic finance capsule without a general LLM call."""

    # The compressor recognizes URLs in the source text; crawlers normally keep
    # it separately, so include it explicitly.
    source = f"URL: {collected.final_url}\n{collected.text}"
    compressed = FinanceCredibilityCompressor().compress(source).compact_language
    lines = [line for line in compressed.splitlines() if line]

    if extracted.claims:
        claim = extracted.claims[0]
        status = "supported" if claim.get("supported") else "unsupported"
        text = _compact_value(str(claim.get("text") or ""), 120)
        if text:
            lines.append(f"claim={text}/{status}")

    # These reasons are calculated by the scoring stages, not necessarily stated
    # verbatim in the page, so preserve them alongside source-derived signals.
    for reason in top_reasons[:5]:
        compact_reason = _compact_value(reason, 90)
        if compact_reason:
            lines.append(f"reason={compact_reason}")

    text = _within_budget(lines, settings.capsule_token_budget)
    return EvidenceCapsule(
        compressed_text=text,
        key_reasons=top_reasons[:5],
        token_estimate_before=before,
        token_estimate_after=_est_tokens(text),
        method="finance_credibility",
    )


def _compact_value(value: str, limit: int) -> str:
    return re.sub(r"\s+", " ", value).strip().replace("\n", " ")[:limit].rstrip()


def _within_budget(lines: list[str], budget_tokens: int) -> str:
    """Keep whole key=value rows, preserving the model's compact DSL."""

    kept: list[str] = []
    for line in lines:
        candidate = "\n".join([*kept, line])
        if _est_tokens(candidate) > budget_tokens:
            break
        kept.append(line)
    return "\n".join(kept)


# ------------------------------------------------------------------ #
def _compress_extractive(collected, extracted, top_reasons, before) -> EvidenceCapsule:
    budget_chars = settings.capsule_token_budget * 4
    keywords = ("claim", "evidence", "source", "cite", "%", "$", "return", "risk", "profit", "loss")

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", collected.text) if 30 <= len(s.strip()) <= 240]
    scored = sorted(
        sentences,
        key=lambda s: sum(s.lower().count(k) for k in keywords),
        reverse=True,
    )

    packed, used = [], 0
    for s in scored:
        if used + len(s) > budget_chars:
            break
        packed.append(s)
        used += len(s)

    claim_line = ""
    if extracted.claims:
        c = extracted.claims[0]
        verdict = "supported" if c.get("supported") else "UNSUPPORTED"
        claim_line = f"Key claim: \"{c.get('text', '')}\" — {verdict}. "

    body = claim_line + " ".join(packed)
    if not body:
        body = (collected.title or collected.url)[:budget_chars]

    return EvidenceCapsule(
        compressed_text=body[:budget_chars],
        key_reasons=top_reasons[:5],
        token_estimate_before=before,
        token_estimate_after=_est_tokens(body[:budget_chars]),
        method="extractive_fallback",
    )

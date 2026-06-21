"""Stage 5 — Credibility Capsule (context compression).

This is the Token Company track: reduce 800–1500 tokens of raw source context to
a compact evidence packet (~capsule_token_budget tokens) that PRESERVES the top
credibility reasons + key claims, so a downstream agent gets the verdict cheaply.

Primary: Claude token-budgeted summarization. Fallback: extractive — rank
sentences containing claim/evidence keywords and pack the top ones within budget.

# TODO(token-company): if a Token Company compression API key is added, slot it
# here as an alternate primary behind a has_* flag and compare ratios.
"""
from __future__ import annotations

import logging
import re

from app.core.config import settings
from app.schemas.score import EvidenceCapsule, SourceFeatures
from app.services.collector import CollectResult
from app.services.extractor import ExtractResult

logger = logging.getLogger("agentshield.capsule")


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

    if settings.has_anthropic and collected.text:
        try:
            return await _compress_claude(collected, extracted, top_reasons, before)
        except Exception as exc:
            logger.warning("Claude capsule failed, using extractive: %s", exc)

    return _compress_extractive(collected, extracted, top_reasons, before)


# ------------------------------------------------------------------ #
async def _compress_claude(collected, extracted, top_reasons, before) -> EvidenceCapsule:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    budget = settings.capsule_token_budget

    prompt = (
        f"Compress this finance source into a credibility capsule of at most ~{budget} tokens. "
        "Preserve: (1) the single most important claim, (2) whether it's supported by on-page "
        "evidence, (3) the top trust/risk reasons. Be terse and factual.\n\n"
        f"TOP REASONS: {'; '.join(top_reasons[:5])}\n\n"
        f"SOURCE TEXT:\n{collected.text[:12000]}"
    )
    msg = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=budget + 80,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    return EvidenceCapsule(
        compressed_text=text,
        key_reasons=top_reasons[:5],
        token_estimate_before=before,
        token_estimate_after=_est_tokens(text),
        method="claude",
    )


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

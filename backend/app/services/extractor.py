"""Stage 2 — Extractor.

Pulls claims + evidence + authorship/citation/recency signals from the page.

Primary: Claude (Anthropic SDK, structured output) when ANTHROPIC_API_KEY is set.
Fallback: a pure-Python heuristic extractor (regex/DOM) — same ExtractResult
shape, lower confidences. Always available with zero keys.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from app.core.config import settings
from app.services.collector import CollectResult

logger = logging.getLogger("agentshield.extractor")

_CLICKBAIT_WORDS = (
    "shocking", "secret", "guaranteed", "you won't believe", "miracle", "exposed",
    "this one trick", "get rich", "doctors hate", "skyrocket", "explode", "100x",
    "millionaire", "insane", "crazy", "urgent", "act now", "limited time",
)


@dataclass
class ExtractResult:
    claims: list[dict] = field(default_factory=list)   # {text, supported, evidence_snippet, confidence}
    has_author: bool = False
    author_name: str | None = None
    has_citations: bool = False
    citation_count: int = 0
    publish_date: str | None = None        # ISO date string if found
    clickbait_signal: float = 0.0          # 0..1
    mode: str = "heuristic_fallback"       # "claude" | "heuristic_fallback"


class Extractor:
    async def extract(self, collected: CollectResult, task: str) -> ExtractResult:
        if settings.has_anthropic and collected.text:
            try:
                return await self._extract_claude(collected, task)
            except Exception as exc:
                logger.warning("Claude extract failed, using heuristic: %s", exc)
        return self._extract_heuristic(collected)

    # ------------------------------------------------------------------ #
    async def _extract_claude(self, collected: CollectResult, task: str) -> ExtractResult:
        """Structured extraction via the Anthropic SDK (Claude Opus 4.8)."""
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=settings.anthropic_api_key)

        # Budget the page text so we don't blow context on huge pages.
        page = collected.text[:18000]
        title = collected.title or ""

        system = (
            "You are AgentShield's source-analysis engine for FINANCE sources only. "
            "Extract factual/financial claims and assess whether each is supported by "
            "evidence ON THE PAGE (citations, data, named sources). Also detect authorship, "
            "citation presence, publish date, and clickbait. Be skeptical and precise."
        )
        prompt = (
            f"TASK THE AGENT WANTS TO DO: {task}\n\n"
            f"PAGE TITLE: {title}\n\n"
            f"PAGE TEXT:\n{page}\n\n"
            "Return JSON with keys: claims (array of {text, supported (bool), "
            "evidence_snippet (string or null), confidence (0..1)}), has_author (bool), "
            "author_name (string or null), has_citations (bool), citation_count (int), "
            "publish_date (ISO date string or null), clickbait_signal (0..1). "
            "Limit to the 6 most important claims."
        )

        msg = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=2000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")
        data = _loads_json(raw)

        return ExtractResult(
            claims=data.get("claims", [])[:6],
            has_author=bool(data.get("has_author")),
            author_name=data.get("author_name"),
            has_citations=bool(data.get("has_citations")),
            citation_count=int(data.get("citation_count") or 0),
            publish_date=data.get("publish_date"),
            clickbait_signal=float(data.get("clickbait_signal") or 0.0),
            mode="claude",
        )

    # ------------------------------------------------------------------ #
    def _extract_heuristic(self, collected: CollectResult) -> ExtractResult:
        html, text, title = collected.html, collected.text, collected.title or ""

        # Authorship
        author = None
        m = re.search(r'(?i)(?:by|author[:\s])\s+([A-Z][a-z]+\s+[A-Z][a-z]+)', text[:2000])
        if not m:
            m = re.search(r'(?i)<meta[^>]+name=["\']author["\'][^>]+content=["\']([^"\']+)', html)
        if m:
            author = m.group(1).strip()
        has_author = author is not None

        # Citations: <cite>, references, footnote markers, outbound links to known domains
        citation_count = len(re.findall(r"(?i)<cite\b", html))
        citation_count += len(re.findall(r"(?i)\b(references|sources|citations)\b", text))
        citation_count += min(len(collected.outbound_links), 20)
        has_citations = citation_count >= 3

        # Publish date
        publish_date = None
        dm = re.search(r"(?i)<meta[^>]+(?:article:published_time|date)[^>]+content=[\"']([^\"']+)", html)
        if not dm:
            dm = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text[:3000])
        if dm:
            publish_date = dm.group(1)[:10]

        # Clickbait
        haystack = (title + " " + text[:500]).lower()
        hits = sum(1 for w in _CLICKBAIT_WORDS if w in haystack)
        caps_ratio = sum(1 for c in title if c.isupper()) / max(len(title), 1)
        exclam = title.count("!")
        clickbait = min(1.0, 0.2 * hits + 0.5 * (caps_ratio > 0.4) + 0.2 * min(exclam, 2))

        # Claims: take a few declarative sentences as candidate claims (unsupported by default)
        sentences = re.split(r"(?<=[.!?])\s+", text)
        claims = []
        for s in sentences:
            s = s.strip()
            if 40 <= len(s) <= 240 and re.search(r"(?i)\b(will|cure|guarantee|return|profit|best|"
                                                 r"%|percent|\$|growth|crash|surge)\b", s):
                claims.append({
                    "text": s,
                    "supported": has_citations,
                    "evidence_snippet": None,
                    "confidence": 0.4,
                })
            if len(claims) >= 5:
                break

        return ExtractResult(
            claims=claims,
            has_author=has_author,
            author_name=author,
            has_citations=has_citations,
            citation_count=citation_count,
            publish_date=publish_date,
            clickbait_signal=clickbait,
            mode="heuristic_fallback",
        )


def _loads_json(raw: str) -> dict:
    import json

    raw = raw.strip()
    # strip ```json fences if present
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.S)
    if fence:
        raw = fence.group(1)
    else:
        brace = re.search(r"\{.*\}", raw, re.S)
        if brace:
            raw = brace.group(0)
    try:
        return json.loads(raw)
    except Exception:
        return {}


def days_since(iso_date: str | None) -> int | None:
    if not iso_date:
        return None
    try:
        d = datetime.fromisoformat(iso_date[:10]).date()
        return (date.today() - d).days
    except Exception:
        return None

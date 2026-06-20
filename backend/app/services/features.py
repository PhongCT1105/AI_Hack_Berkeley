"""Stage 3 — Feature builder.

Combines collector DOM signals + extractor output + domain reputation into the
SourceFeatures vector the ranker consumes. Pure-ish: the only I/O is the
reputation lookup, passed in by the pipeline.
"""
from __future__ import annotations

import re

from app.schemas.score import SourceFeatures
from app.services.collector import CollectResult
from app.services.extractor import ExtractResult, days_since

# Hosts commonly associated with ads / trackers — used to estimate ad density.
_AD_HOSTS = (
    "doubleclick.net", "googlesyndication.com", "adservice.google", "amazon-adsystem.com",
    "taboola.com", "outbrain.com", "adnxs.com", "criteo.com", "media.net", "/ads/",
)


def build_features(
    collected: CollectResult,
    extracted: ExtractResult,
    reputation: float,
    listed: str | None,
) -> SourceFeatures:
    html = collected.html or ""

    https = collected.final_url.startswith("https://")
    word_count = len(collected.text.split()) if collected.text else 0

    # Ad density: ad-ish script/iframe hosts vs total script+iframe tags.
    ad_hits = sum(html.lower().count(h) for h in _AD_HOSTS)
    tag_total = len(re.findall(r"(?i)<(script|iframe)\b", html)) or 1
    ad_density = min(1.0, ad_hits / tag_total)

    return SourceFeatures(
        https=https,
        has_author=extracted.has_author,
        has_citations=extracted.has_citations,
        citation_count=extracted.citation_count,
        ad_density=round(ad_density, 3),
        domain_reputation=round(reputation, 3),
        domain_listed=listed,
        clickbait_score=round(extracted.clickbait_signal, 3),
        recency_days=days_since(extracted.publish_date),
        word_count=word_count,
        outbound_link_count=len(collected.outbound_links),
        collector_mode=collected.mode,
        extractor_mode=extracted.mode,
    )

"""Credential-free-or-Firecrawl crawler for the Terac training-data endpoint."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

from app.schemas.crawl import (
    ClaimCandidate, CrawlBatchResponse, CrawlPageResult, CrawlRequest,
    CredibilityCapsule, SourceProfile, TeracClaimFeature,
    TeracExtractedFeaturesForLabeling, TeracTrainingPayload,
    TeracTrustEvaluationRequest, TrustSignal,
)
from app.services.collector import Collector


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _clip(value: str, limit: int) -> str:
    value = _clean(value)
    return value if len(value) <= limit else value[:limit].rsplit(" ", 1)[0].rstrip() + "…"


def _meta(html: str, names: tuple[str, ...]) -> str | None:
    for name in names:
        match = re.search(
            rf'<meta[^>]+(?:name|property)=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)',
            html, re.IGNORECASE,
        )
        if match:
            return _clean(match.group(1))
    return None


def _links(html: str, base_url: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for href, label in re.findall(r'(?is)<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html):
        url = urljoin(base_url, href)
        text = _clean(re.sub(r"<[^>]+>", " ", label))
        parsed = urlparse(url)
        if parsed.scheme in {"http", "https"} and parsed.netloc and text and not any(item["href"] == url for item in links):
            links.append({"text": _clip(text, 120), "href": url})
    return links[:150]


def _claims(text: str) -> list[ClaimCandidate]:
    candidates: list[ClaimCandidate] = []
    for sentence in re.split(r"(?<=[.!?])\s+", _clean(text)):
        words = re.findall(r"\b\w+\b", sentence)
        if len(words) < 8:
            continue
        lower = sentence.lower()
        factual = bool(re.search(r"\b(is|was|were|has|have|reported|said|announced|found|shows|data|study)\b", lower))
        numeric = bool(re.search(r"\b\d+(?:[.,]\d+)?%?\b", sentence))
        if not (factual or numeric):
            continue
        confidence = min(0.95, 0.35 + (0.25 if factual else 0) + (0.25 if numeric else 0))
        candidates.append(ClaimCandidate(claim_text=_clip(sentence, 300), evidence_snippet=_clip(sentence, 500), confidence=confidence))
        if len(candidates) == 8:
            break
    return candidates


class Crawler:
    def __init__(self) -> None:
        self._collector = Collector()

    async def crawl(self, payload: CrawlRequest) -> CrawlBatchResponse:
        urls = self._dedupe_urls(payload.urls)[:payload.max_pages]
        if not urls:
            raise ValueError("At least one valid URL is required")
        started_at = datetime.now(timezone.utc)
        pages = [await self._crawl_page(url, payload.text_limit) for url in urls]
        finished_at = datetime.now(timezone.utc)
        return CrawlBatchResponse(
            session_id=f"crawl-{uuid.uuid4().hex}", session_url="", query=payload.query,
            requested_urls=urls, total_pages=len(pages), started_at=started_at,
            finished_at=finished_at, pages=pages,
        )

    async def _crawl_page(self, requested_url: str, text_limit: int) -> CrawlPageResult:
        result = await self._collector.collect(requested_url)
        final_url = result.final_url
        html = result.html
        text_excerpt = _clip(result.text, text_limit)
        parsed = urlparse(final_url)
        raw_links = _links(html, final_url)
        hostname = parsed.hostname or "unknown"
        external_links = [link for link in raw_links if (urlparse(link["href"]).hostname or "") != hostname]
        canonical = _meta(html, ("canonical",))
        description = _meta(html, ("description", "og:description"))
        author = _meta(html, ("author", "article:author"))
        published = _meta(html, ("article:published_time", "date", "publishdate"))
        profile = SourceProfile(domain=hostname, canonical_url=canonical, content_length=len(text_excerpt), extracted_link_count=len(raw_links), outbound_link_count=len(external_links), published_time=published)
        signals = self._signals(canonical, description, author, published, external_links, text_excerpt, result.error)
        claim_candidates = _claims(result.text)
        capsule = CredibilityCapsule(
            source_url=final_url, title=result.title or None,
            compact_summary=f"domain={hostname} | title={result.title or 'unknown'} | content_length={len(text_excerpt)} | claims={len(claim_candidates)} | collector={result.mode}",
            claim_count=len(claim_candidates), evidence_count=len(claim_candidates), trust_signals=signals,
        )
        terac_payload = TeracTrainingPayload(
            trust_evaluation_request=TeracTrustEvaluationRequest(domain=hostname, url=final_url),
            extracted_features_for_labeling=TeracExtractedFeaturesForLabeling(
                outbound_link_density_ratio=round(len(external_links) / max(1, len(raw_links)), 4),
                has_verified_ssl=parsed.scheme == "https",
                top_extracted_claims=[TeracClaimFeature(claim=item.claim_text, context_snippet=item.evidence_snippet, source_trust_score=item.confidence) for item in claim_candidates[:3]],
            ),
        )
        return CrawlPageResult(
            requested_url=requested_url, final_url=final_url, title=result.title or None,
            meta_description=description, author=author, published_time=published,
            source_profile=profile, fetched_at=datetime.now(timezone.utc), text_excerpt=text_excerpt,
            links=external_links[:20], claim_candidates=claim_candidates, trust_signals=signals,
            credibility_capsule=capsule, terac_payload=terac_payload,
        )

    @staticmethod
    def _signals(canonical: str | None, description: str | None, author: str | None, published: str | None, external_links: list[dict[str, str]], text: str, error: str | None) -> list[TrustSignal]:
        signals = []
        for kind, value in (("canonical-url", canonical), ("meta-description", description), ("author-meta", author), ("published-time", published)):
            if value:
                signals.append(TrustSignal(kind=kind, detail=_clip(value, 220)))
        if external_links:
            signals.append(TrustSignal(kind="external-links", detail=f"{len(external_links)} outbound links detected"))
        if len(text) > 4000:
            signals.append(TrustSignal(kind="substantial-text", detail=f"{len(text)} visible characters captured"))
        if error:
            signals.append(TrustSignal(kind="collection-error", detail=_clip(error, 220)))
        return signals or [TrustSignal(kind="baseline", detail="No high-signal metadata found; use with caution")]

    @staticmethod
    def _dedupe_urls(urls: list[str]) -> list[str]:
        output: list[str] = []
        for url in urls:
            normalized = _clean(url)
            parsed = urlparse(normalized)
            if parsed.scheme in {"http", "https"} and parsed.netloc and normalized not in output:
                output.append(normalized)
        return output

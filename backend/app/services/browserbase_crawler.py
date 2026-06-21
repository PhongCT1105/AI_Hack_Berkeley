"""Browserbase-backed crawling for Terac training data."""
from __future__ import annotations

import re
from contextlib import suppress
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from browserbase import Browserbase
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from app.core.config import settings
from app.schemas.crawl import (
    ClaimCandidate,
    CrawlBatchResponse,
    CrawlPageResult,
    CrawlRequest,
    CredibilityCapsule,
    SourceProfile,
    TeracClaimFeature,
    TeracExtractedFeaturesForLabeling,
    TeracTrainingPayload,
    TeracTrustEvaluationRequest,
    TrustSignal,
)


CLAIM_KEYWORDS = (
    "according to",
    "reports",
    "states",
    "says",
    "announced",
    "claimed",
    "found",
    "shows",
    "indicates",
    "estimated",
    "research",
    "study",
    "evidence",
    "data",
    "confirmed",
    "verified",
)

FACTUAL_VERBS = (
    "is",
    "was",
    "were",
    "has",
    "have",
    "had",
    "won",
    "wins",
    "played",
    "plays",
    "founded",
    "born",
    "released",
    "published",
    "announced",
    "reported",
    "serves",
    "includes",
    "contains",
    "recorded",
    "measured",
    "described",
    "became",
    "earned",
)

NOISE_LINK_TEXT_RE = re.compile(
    r"^(jump to content|main page|donate|create account|log in|log out|search|menu|contents?|hide|toggle.*|main menu|sidebar|help|privacy policy|terms of use)$",
    re.IGNORECASE,
)

NOISE_LINK_PATH_RE = re.compile(
    r"(?:login|log-in|logout|sign-in|signin|signup|sign-up|create-account|account|special:|portal|help|sitemap|site-map|index|category|talk|history|edit|preferences)",
    re.IGNORECASE,
)

SOURCE_LINK_PATH_RE = re.compile(
    r"(?:citation|reference|references|source|sources|paper|papers|pdf|doi|docs?|document|report|whitepaper|scholar)",
    re.IGNORECASE,
)

LANGUAGE_TEXT_RE = re.compile(r"^[A-Za-zÀ-ÿ'\- ]{2,24}$")


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _clip_text(value: str, limit: int) -> str:
    clean_value = _clean_text(value)
    if len(clean_value) <= limit:
        return clean_value

    clipped = clean_value[:limit].rstrip()
    last_space = clipped.rfind(" ")
    last_punctuation = max(clipped.rfind("."), clipped.rfind("!"), clipped.rfind("?"))
    cut_point = max(last_space, last_punctuation)
    if cut_point >= max(0, limit // 2):
        clipped = clipped[:cut_point].rstrip()
    return f"{clipped}…"


def _hostname_root(hostname: str | None) -> str:
    if not hostname:
        return ""
    parts = hostname.lower().split(".")
    if len(parts) <= 2:
        return hostname.lower()
    return ".".join(parts[-2:])


def _is_noise_link(link: dict[str, str], page_hostname: str, page_root: str) -> bool:
    href = str(link.get("href", "")).strip()
    text = _clean_text(str(link.get("text", "")))
    lowered_text = text.lower()

    if not href:
        return True

    parsed = urlparse(href)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return True

    if href.startswith(("javascript:", "mailto:", "tel:")):
        return True

    if NOISE_LINK_TEXT_RE.match(text):
        return True

    if NOISE_LINK_PATH_RE.search(parsed.path):
        return True

    if parsed.fragment and _hostname_root(parsed.hostname) == page_root:
        return True

    link_hostname = parsed.hostname or ""
    link_root = _hostname_root(link_hostname)
    if link_hostname == page_hostname:
        return not SOURCE_LINK_PATH_RE.search(parsed.path)

    if link_root == page_root:
        if SOURCE_LINK_PATH_RE.search(parsed.path) or SOURCE_LINK_PATH_RE.search(lowered_text):
            return False
        if LANGUAGE_TEXT_RE.match(text) and len(text.split()) <= 3:
            return True
        return True

    return False


def _filter_links(links: list[dict[str, str]], page_hostname: str) -> list[dict[str, str]]:
    page_root = _hostname_root(page_hostname)
    filtered: list[dict[str, str]] = []

    for link in links:
        href = str(link.get("href", "")).strip()
        text = _clean_text(str(link.get("text", "")))
        if not href or not text:
            continue

        if _is_noise_link(link, page_hostname, page_root):
            continue

        filtered.append({"text": _clip_text(text, 120), "href": href})
        if len(filtered) >= 20:
            break

    return filtered


def _is_factual_claim(sentence: str) -> bool:
    lowered = sentence.lower()
    if any(re.search(rf"\b{re.escape(verb)}\b", lowered) for verb in FACTUAL_VERBS):
        return True
    return bool(re.search(r"\b(?:according to|reports|states|says|claimed|found|shows|indicates|estimated|research|study|evidence|data|confirmed|verified)\b", lowered))


def _split_sentences(text: str) -> list[str]:
    normalized = _clean_text(text)
    if not normalized:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def _build_context_snippet(sentences: list[str], index: int, *, max_chars: int = 500) -> str:
    if not sentences:
        return ""

    start = max(0, index - 1)
    end = min(len(sentences), index + 2)
    context = _clean_text(" ".join(sentences[start:end]))

    if len(context) <= max_chars:
        return context

    sentence = sentences[index]
    sentence_index = context.find(sentence)
    if sentence_index == -1:
        return _clip_text(context, max_chars)

    prefix_budget = max_chars // 3
    suffix_budget = max_chars - len(sentence) - prefix_budget - 3
    prefix = context[max(0, sentence_index - prefix_budget) : sentence_index].strip()
    suffix = context[sentence_index + len(sentence) : sentence_index + len(sentence) + max(0, suffix_budget)].strip()

    snippet_parts = [part for part in [prefix, sentence, suffix] if part]
    snippet = " ... ".join(snippet_parts)
    return _clip_text(snippet, max_chars)


def _extract_evidence_snippet(text: str, sentence: str, window: int = 90) -> tuple[str, int | None, int | None]:
    if not text or not sentence:
        return "", None, None

    match = re.search(re.escape(sentence[:200]), text)
    if match is None:
        return sentence[:300], None, None

    start = max(0, match.start() - window)
    end = min(len(text), match.end() + window)
    return text[start:end], start, end


def _extract_claim_candidates(text: str, max_claims: int = 8) -> list[ClaimCandidate]:
    candidates: list[ClaimCandidate] = []
    sentences = _split_sentences(text)
    for index, sentence in enumerate(sentences):
        sentence = _clip_text(sentence, 320)
        if not sentence:
            continue

        lowered = sentence.lower()
        has_number = bool(re.search(r"\b\d+(?:[.,:]\d+)?%?\b", sentence))
        has_keyword = any(keyword in lowered for keyword in CLAIM_KEYWORDS)
        has_quote = '"' in sentence or "'" in sentence
        has_factual_verb = _is_factual_claim(sentence)
        word_count = len(re.findall(r"\b\w+\b", sentence))
        nav_word_count = len(
            re.findall(
                r"\b(?:jump|content|main|menu|search|donate|create|account|log|in|contents|hide|toggle|language|sidebar|article|edit|history|help)\b",
                lowered,
            )
        )

        if word_count < 8 or nav_word_count >= max(2, word_count // 3):
            continue

        if not (has_number or has_keyword or has_quote or has_factual_verb):
            continue

        confidence = 0.2
        if has_number:
            confidence += 0.25
        if has_keyword:
            confidence += 0.25
        if has_quote:
            confidence += 0.1
        if has_factual_verb:
            confidence += 0.2
        if 10 <= word_count <= 32:
            confidence += 0.1
        if sentence.endswith((".", "!", "?")):
            confidence += 0.05

        context_snippet = _build_context_snippet(sentences, index)
        evidence_snippet, evidence_start, evidence_end = _extract_evidence_snippet(context_snippet, sentence, window=40)
        if not evidence_snippet or _clean_text(evidence_snippet) == _clean_text(sentence):
            evidence_snippet = context_snippet or sentence
        candidates.append(
            ClaimCandidate(
                claim_text=_clip_text(sentence, 300),
                evidence_snippet=_clip_text(evidence_snippet, 500),
                confidence=min(confidence, 1.0),
                evidence_start=evidence_start,
                evidence_end=evidence_end,
            )
        )
        if len(candidates) >= max_claims:
            break

    return candidates


def _build_terac_payload(
    *,
    requested_url: str,
    final_url: str,
    source_profile: SourceProfile,
    claim_candidates: list[ClaimCandidate],
) -> TeracTrainingPayload:
    parsed_final_url = urlparse(final_url)
    top_claims = [
        TeracClaimFeature(
            claim=candidate.claim_text,
            context_snippet=candidate.evidence_snippet,
            source_trust_score=candidate.confidence,
        )
        for candidate in claim_candidates[:3]
    ]
    density_denominator = max(1, source_profile.extracted_link_count)
    return TeracTrainingPayload(
        trust_evaluation_request=TeracTrustEvaluationRequest(
            domain=parsed_final_url.hostname or source_profile.domain,
            url=final_url or requested_url,
        ),
        extracted_features_for_labeling=TeracExtractedFeaturesForLabeling(
            outbound_link_density_ratio=round(source_profile.outbound_link_count / density_denominator, 4),
            has_verified_ssl=parsed_final_url.scheme == "https",
            top_extracted_claims=top_claims,
        ),
    )


def _build_trust_signals(page_meta: dict[str, Any], links: list[dict[str, str]], text: str) -> list[TrustSignal]:
    signals: list[TrustSignal] = []
    if page_meta.get("canonical"):
        signals.append(TrustSignal(kind="canonical-url", detail=str(page_meta["canonical"])))
    if page_meta.get("description"):
        signals.append(TrustSignal(kind="meta-description", detail=str(page_meta["description"])[:220]))
    if page_meta.get("author"):
        signals.append(TrustSignal(kind="author-meta", detail=str(page_meta["author"])[:160]))
    if page_meta.get("publishedTime"):
        signals.append(TrustSignal(kind="published-time", detail=str(page_meta["publishedTime"])))

    external_links = 0
    hostname = page_meta.get("hostname")
    for link in links:
        href = link.get("href", "")
        parsed = urlparse(href)
        if parsed.scheme in {"http", "https"} and parsed.netloc and parsed.netloc != hostname:
            external_links += 1
    if external_links:
        signals.append(TrustSignal(kind="external-links", detail=f"{external_links} outbound links detected"))

    if len(text) > 4000:
        signals.append(TrustSignal(kind="substantial-text", detail=f"{len(text)} visible characters captured"))

    if not signals:
        signals.append(TrustSignal(kind="baseline", detail="No high-signal metadata found; use with caution"))

    return signals


def _build_source_profile(page_meta: dict[str, Any], links: list[dict[str, str]], text: str) -> SourceProfile:
    hostname = page_meta.get("hostname") or urlparse(str(page_meta.get("canonical") or "")).hostname or "unknown"
    external_link_count = 0
    for link in links:
        href = link.get("href", "")
        parsed = urlparse(href)
        if parsed.scheme in {"http", "https"} and parsed.netloc and parsed.netloc != hostname:
            external_link_count += 1

    return SourceProfile(
        domain=str(hostname),
        canonical_url=page_meta.get("canonical"),
        content_length=len(text),
        extracted_link_count=len(links),
        outbound_link_count=external_link_count,
        published_time=page_meta.get("publishedTime"),
    )


def _compress_capsule(
    *,
    requested_url: str,
    final_url: str,
    title: str | None,
    text_excerpt: str,
    claim_candidates: list[ClaimCandidate],
    trust_signals: list[TrustSignal],
    source_profile: SourceProfile,
) -> CredibilityCapsule:
    claim_bits = [candidate.claim_text[:120] for candidate in claim_candidates[:3]]
    signal_bits = [signal.kind for signal in trust_signals[:4]]
    domain = urlparse(final_url).hostname or urlparse(requested_url).hostname or source_profile.domain or "unknown"
    summary = " | ".join(
        part
        for part in [
            f"domain={domain}",
            f"title={title or 'unknown'}",
            f"content_length={source_profile.content_length}",
            f"claims={' ; '.join(claim_bits) if claim_bits else 'none'}",
            f"signals={', '.join(signal_bits) if signal_bits else 'none'}",
            f"excerpt={text_excerpt[:240]}",
        ]
        if part
    )
    return CredibilityCapsule(
        source_url=final_url,
        title=title,
        compact_summary=summary,
        claim_count=len(claim_candidates),
        evidence_count=len(claim_candidates),
        trust_signals=trust_signals,
    )


class BrowserbaseCrawler:
    def __init__(self) -> None:
        api_key = settings.browserbase_api_key
        if not api_key:
            raise ValueError("BROWSERBASE_API_KEY is required for Browserbase crawling")

        self._browserbase = Browserbase(api_key=api_key)
        self._project_id = settings.browserbase_project_id
        self._page_timeout_ms = settings.browserbase_page_timeout_ms
        self._max_text_chars = settings.browserbase_max_text_chars

    def crawl(self, payload: CrawlRequest) -> CrawlBatchResponse:
        urls = self._dedupe_urls(payload.urls)[: payload.max_pages]
        if not urls:
            raise ValueError("At least one valid URL is required")

        started_at = datetime.now(timezone.utc)
        session = self._create_session()
        browser = None
        pages: list[CrawlPageResult] = []

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.connect_over_cdp(session.connect_url)
                context = browser.contexts[0]
                page = context.pages[0] if context.pages else context.new_page()

                for url in urls:
                    pages.append(
                        self._crawl_single_page(
                            page=page,
                            requested_url=url,
                            text_limit=payload.text_limit,
                            page_timeout_ms=payload.page_timeout_ms,
                        )
                    )
        finally:
            if browser is not None:
                with suppress(Exception):
                    browser.close()
            with suppress(Exception):
                self._browserbase.sessions.update(id=session.id, status="REQUEST_RELEASE")

        finished_at = datetime.now(timezone.utc)
        return CrawlBatchResponse(
            session_id=session.id,
            session_url=f"https://browserbase.com/sessions/{session.id}",
            query=payload.query,
            requested_urls=urls,
            total_pages=len(pages),
            started_at=started_at,
            finished_at=finished_at,
            pages=pages,
        )

    def _create_session(self):
        if self._project_id:
            return self._browserbase.sessions.create(project_id=self._project_id)
        return self._browserbase.sessions.create()

    def _crawl_single_page(
        self,
        *,
        page,
        requested_url: str,
        text_limit: int,
        page_timeout_ms: int,
    ) -> CrawlPageResult:
        effective_timeout = min(page_timeout_ms, self._page_timeout_ms)
        effective_text_limit = min(text_limit, self._max_text_chars)

        try:
            page.goto(requested_url, wait_until="networkidle", timeout=effective_timeout)
        except PlaywrightTimeoutError:
            page.goto(requested_url, wait_until="domcontentloaded", timeout=effective_timeout)
        with suppress(PlaywrightTimeoutError):
            page.wait_for_load_state("domcontentloaded", timeout=min(effective_timeout, 10000))

        final_url = page.url
        title = _clean_text(page.title()) or None

        page_meta = page.evaluate(
            """() => {
                const canonical = document.querySelector('link[rel="canonical"]')?.href ?? null;
                const description = document.querySelector('meta[name="description"]')?.content
                  ?? document.querySelector('meta[property="og:description"]')?.content
                  ?? null;
                const author = document.querySelector('meta[name="author"]')?.content
                  ?? document.querySelector('meta[property="article:author"]')?.content
                  ?? null;
                const publishedTime = document.querySelector('meta[property="article:published_time"]')?.content
                  ?? document.querySelector('time[datetime]')?.getAttribute('datetime')
                  ?? null;
                                const links = Array.from(document.querySelectorAll('a[href]')).slice(0, 150).map((anchor) => ({
                  text: (anchor.innerText || anchor.textContent || '').trim(),
                  href: anchor.href,
                })).filter((link) => Boolean(link.href));
                return {
                  canonical,
                  description,
                  author,
                  publishedTime,
                  hostname: location.hostname,
                  links,
                };
            }"""
        )

        raw_text = page.evaluate(
            """() => {
                const bodyText = document.body?.innerText || document.documentElement?.innerText || '';
                return bodyText;
            }"""
        )
        if not isinstance(raw_text, str):
            raw_text = str(raw_text)
        text_excerpt = _clip_text(raw_text, effective_text_limit)

        raw_links = page_meta.get("links") or []
        if not isinstance(raw_links, list):
            raw_links = []

        page_hostname = str(page_meta.get("hostname") or urlparse(final_url).hostname or "")
        links = _filter_links(raw_links, page_hostname)

        trust_signals = _build_trust_signals(page_meta, links, text_excerpt)
        source_profile = _build_source_profile(page_meta, raw_links, text_excerpt)
        claim_candidates = _extract_claim_candidates(raw_text)
        capsule = _compress_capsule(
            requested_url=requested_url,
            final_url=final_url,
            title=title,
            text_excerpt=text_excerpt,
            claim_candidates=claim_candidates,
            trust_signals=trust_signals,
            source_profile=source_profile,
        )
        terac_payload = _build_terac_payload(
            requested_url=requested_url,
            final_url=final_url,
            source_profile=source_profile,
            claim_candidates=claim_candidates,
        )

        return CrawlPageResult(
            requested_url=requested_url,
            final_url=final_url,
            title=title,
            meta_description=page_meta.get("description"),
            author=page_meta.get("author"),
            published_time=page_meta.get("publishedTime"),
            source_profile=source_profile,
            fetched_at=datetime.now(timezone.utc),
            text_excerpt=text_excerpt,
            links=links,
            claim_candidates=claim_candidates,
            trust_signals=trust_signals,
            credibility_capsule=capsule,
            terac_payload=terac_payload,
        )

    @staticmethod
    def _dedupe_urls(urls: list[str]) -> list[str]:
        seen: set[str] = set()
        clean_urls: list[str] = []
        for url in urls:
            normalized = _clean_text(url)
            if not normalized:
                continue
            parsed = urlparse(normalized)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            clean_urls.append(normalized)
        return clean_urls
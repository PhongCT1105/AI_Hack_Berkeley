"""Stage 1 — discover and collect public web pages.

Discovery uses Firecrawl Search. Collection then uses Firecrawl Scrape with a
direct HTTP fallback for a specific source URL.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx

from app.core.config import settings

logger = logging.getLogger("captain_america.collector")

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


@dataclass
class CollectResult:
    url: str
    final_url: str
    html: str = ""
    text: str = ""
    title: str = ""
    screenshot_b64: str | None = None
    outbound_links: list[str] = field(default_factory=list)
    mode: str = "httpx_fallback"  # "firecrawl" | "httpx_fallback"
    error: str | None = None


@dataclass
class SearchResult:
    """URLs discovered for a research request plus an operator-safe status."""

    urls: list[str] = field(default_factory=list)
    mode: str = "unknown"
    error: str | None = None


class Collector:
    async def search(self, query: str, limit: int = 100) -> SearchResult:
        """Discover public result URLs without depending on browser-rendered SERPs.

        Search-engine HTML is intentionally not parsed here.  Firecrawl owns
        discovery and returns direct source URLs, so a challenge page from a
        third-party search engine cannot leave the crawler with zero targets.
        """
        limit = max(1, limit)
        if not settings.has_firecrawl:
            return SearchResult(
                mode="firecrawl_search_unavailable",
                error="Firecrawl search is not configured",
            )
        try:
            urls = await self._search_firecrawl(query, limit)
        except Exception:
            # Do not expose provider internals (or request details) to API
            # callers. The server log retains the exception for diagnosis.
            logger.exception("Firecrawl search failed for query %r", query)
            return SearchResult(mode="firecrawl_search_failed", error="Firecrawl search request failed")
        if not urls:
            logger.warning("Firecrawl search returned no usable source URLs for query %r", query)
            return SearchResult(
                mode="firecrawl_search_empty",
                error="Firecrawl search returned no usable source URLs",
            )
        return SearchResult(urls=urls, mode="firecrawl_search")

    async def _search_firecrawl(self, query: str, limit: int) -> list[str]:
        """Use Firecrawl's v2 search API to get real source URLs.

        Search is deliberately separate from ``_collect_firecrawl``: the former
        finds candidate pages, the latter retrieves the exact page selected for
        scoring.  This avoids attempting to parse a third-party search engine's
        browser HTML.
        """
        endpoint = f"{settings.firecrawl_api_url.rstrip('/')}/v2/search"
        payload = {
            "query": query,
            "limit": min(limit, 100),
            "sources": ["web"],
            "timeout": settings.firecrawl_page_timeout_ms,
        }
        headers = {"Authorization": f"Bearer {settings.firecrawl_api_key}"}
        timeout = min(settings.firecrawl_page_timeout_ms / 1000, 180)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()

        if not body.get("success", True):
            raise RuntimeError("Firecrawl search returned an unsuccessful response")
        data = body.get("data") or {}
        # v2 returns {data: {web: [...]}}.  Accept the v1 list shape too, so a
        # self-hosted endpoint can be upgraded without breaking research.
        candidates = data.get("web", []) if isinstance(data, dict) else data
        return _result_urls(candidates, limit)

    async def collect(self, url: str) -> CollectResult:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        if settings.has_firecrawl:
            try:
                return await self._collect_firecrawl(url)
            except Exception as exc:
                logger.warning("Firecrawl collection failed for %s; using HTTP fallback: %s", url, exc)
        return await self._collect_httpx(url)

    async def _collect_firecrawl(self, url: str) -> CollectResult:
        endpoint = f"{settings.firecrawl_api_url.rstrip('/')}/v2/scrape"
        payload = {
            "url": url,
            "formats": ["markdown", "html", "links"],
            "onlyMainContent": False,
        }
        headers = {"Authorization": f"Bearer {settings.firecrawl_api_key}"}
        timeout = min(settings.firecrawl_page_timeout_ms / 1000, 180)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()

        if not body.get("success", True):
            raise RuntimeError(str(body.get("error") or "Firecrawl scrape failed"))
        data = body.get("data") or {}
        metadata = data.get("metadata") or {}
        html = str(data.get("html") or "")
        text = _clean_text(str(data.get("markdown") or "")) or _html_to_text(html)
        links = _normalize_links(data.get("links"), url)
        final_url = str(metadata.get("sourceURL") or metadata.get("url") or url)
        title = _clean_text(str(metadata.get("title") or "")) or _extract_title(html)
        return CollectResult(
            url=url,
            final_url=final_url,
            html=html,
            text=text,
            title=title,
            outbound_links=links or _extract_links(html, final_url),
            mode="firecrawl",
        )

    async def _collect_httpx(self, url: str) -> CollectResult:
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=15.0, headers={"User-Agent": _UA}) as client:
                response = await client.get(url)
                response.raise_for_status()
                html = response.text
                final_url = str(response.url)
        except Exception as exc:
            logger.warning("httpx collect failed for %s: %s", url, exc)
            return CollectResult(url=url, final_url=url, mode="httpx_fallback", error=str(exc))
        return CollectResult(
            url=url, final_url=final_url, html=html, text=_html_to_text(html),
            title=_extract_title(html), outbound_links=_extract_links(html, final_url), mode="httpx_fallback",
        )


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _html_to_text(html: str) -> str:
    if not html:
        return ""
    try:
        from selectolax.parser import HTMLParser

        tree = HTMLParser(html)
        for tag in tree.css("script, style, noscript"):
            tag.decompose()
        body = tree.body or tree.root
        return _clean_text(body.text(separator=" ")) if body else ""
    except Exception:
        stripped = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", html)
        return _clean_text(re.sub(r"(?s)<[^>]+>", " ", stripped))


def _extract_title(html: str) -> str:
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html or "")
    return _clean_text(match.group(1)) if match else ""


def _normalize_links(value: object, base_url: str) -> list[str]:
    candidates = value if isinstance(value, list) else []
    links: list[str] = []
    for candidate in candidates:
        href = candidate.get("url") if isinstance(candidate, dict) else candidate
        if not isinstance(href, str):
            continue
        absolute = urljoin(base_url, href)
        if urlparse(absolute).scheme in {"http", "https"} and absolute not in links:
            links.append(absolute)
    return links[:100]


def _result_urls(candidates: object, limit: int) -> list[str]:
    """Extract and validate URL fields from Firecrawl search result objects."""
    if not isinstance(candidates, list):
        return []
    urls: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        metadata = candidate.get("metadata")
        raw_url = candidate.get("url")
        if not isinstance(raw_url, str) and isinstance(metadata, dict):
            raw_url = metadata.get("sourceURL") or metadata.get("url")
        if not isinstance(raw_url, str):
            continue
        parsed = urlparse(raw_url)
        if parsed.scheme in {"http", "https"} and parsed.netloc and raw_url not in urls:
            urls.append(raw_url)
        if len(urls) >= limit:
            break
    return urls


def _extract_links(html: str, base_url: str) -> list[str]:
    if not html:
        return []
    base_domain = urlparse(base_url).netloc
    links: list[str] = []
    for href in re.findall(r'(?i)href=["\']([^"\']+)["\']', html):
        absolute = urljoin(base_url, href)
        if urlparse(absolute).netloc and urlparse(absolute).netloc != base_domain and absolute not in links:
            links.append(absolute)
    return links[:100]

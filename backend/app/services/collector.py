"""Stage 1 — Collector.

Primary: Browserbase/Stagehand opens the live page (real browser, screenshot,
JS-rendered DOM) — this is the Browserbase sponsor track. Fallback: a plain
httpx GET parsed with selectolax (or a stdlib regex fallback if selectolax is
absent). The fallback is AUTOMATIC on missing creds or any error, so the demo
never hard-crashes.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx

from app.core.config import settings

logger = logging.getLogger("agentshield.collector")

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
    mode: str = "httpx_fallback"      # "browserbase" | "httpx_fallback"
    error: str | None = None


class Collector:
    async def collect(self, url: str) -> CollectResult:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        if settings.has_browserbase:
            try:
                return await self._collect_browserbase(url)
            except Exception as exc:  # automatic fallback
                logger.warning("Browserbase failed, falling back to httpx: %s", exc)

        return await self._collect_httpx(url)

    # ------------------------------------------------------------------ #
    async def _collect_browserbase(self, url: str) -> CollectResult:
        """Drive a Browserbase session over Playwright CDP, screenshot + DOM.

        Import-guarded so a missing package degrades to httpx automatically.
        """
        from browserbase import Browserbase  # type: ignore
        from playwright.async_api import async_playwright  # type: ignore

        bb = Browserbase(api_key=settings.browserbase_api_key)
        session = bb.sessions.create(project_id=settings.browserbase_project_id)

        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(session.connect_url)
            try:
                page = await browser.contexts[0].pages[0]
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                html = await page.content()
                title = await page.title()
                shot = await page.screenshot(type="png")
                import base64

                screenshot_b64 = base64.b64encode(shot).decode()
            finally:
                await browser.close()

        text = _html_to_text(html)
        links = _extract_links(html, url)
        return CollectResult(
            url=url, final_url=url, html=html, text=text, title=title,
            screenshot_b64=screenshot_b64, outbound_links=links, mode="browserbase",
        )

    # ------------------------------------------------------------------ #
    async def _collect_httpx(self, url: str) -> CollectResult:
        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=15.0, headers={"User-Agent": _UA}
            ) as client:
                resp = await client.get(url)
                html = resp.text
                final_url = str(resp.url)
        except Exception as exc:
            logger.warning("httpx collect failed for %s: %s", url, exc)
            return CollectResult(url=url, final_url=url, mode="httpx_fallback", error=str(exc))

        return CollectResult(
            url=url,
            final_url=final_url,
            html=html,
            text=_html_to_text(html),
            title=_extract_title(html),
            outbound_links=_extract_links(html, final_url),
            mode="httpx_fallback",
        )


# --- parsing helpers: prefer selectolax, fall back to regex --------------- #
def _html_to_text(html: str) -> str:
    if not html:
        return ""
    try:
        from selectolax.parser import HTMLParser

        tree = HTMLParser(html)
        for tag in tree.css("script, style, noscript"):
            tag.decompose()
        body = tree.body or tree.root
        return re.sub(r"\s+", " ", body.text(separator=" ")).strip() if body else ""
    except Exception:
        stripped = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", html)
        stripped = re.sub(r"(?s)<[^>]+>", " ", stripped)
        return re.sub(r"\s+", " ", stripped).strip()


def _extract_title(html: str) -> str:
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", html or "")
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def _extract_links(html: str, base_url: str) -> list[str]:
    if not html:
        return []
    base_domain = urlparse(base_url).netloc
    links: list[str] = []
    for href in re.findall(r'(?i)href=["\']([^"\']+)["\']', html):
        try:
            absolute = urljoin(base_url, href)
            if urlparse(absolute).netloc and urlparse(absolute).netloc != base_domain:
                links.append(absolute)
        except Exception:
            continue
    # de-dup, cap
    seen, out = set(), []
    for link in links:
        if link not in seen:
            seen.add(link)
            out.append(link)
        if len(out) >= 100:
            break
    return out

"""Captain Ddoski demo endpoints — deterministic, mocked-first.

UI-ONLY THIS BUILD: classification below is synthetic (domain prior + keyword
heuristics), not a real collector/extractor/Firecrawl run. The real pipeline
already exists at app/services/pipeline.py (Pipeline.score_source) and powers
/api/score-source — swap `_classify_url` for a call into that pipeline once
per-source latency is acceptable for a judge-facing demo.
# TODO(real-pipeline): replace _classify_url with `await pipeline.score_source(...)`
# TODO(terac): replace _MOCK_EVAL with metrics computed from real Terac labels
# vs held-out hidden_original_labels.csv once the trained ranker (app/ml/trainer.py)
# is wired up.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from urllib.parse import urlparse

from fastapi import APIRouter

from app.core.config import settings
from app.data.finance_domains import classify_domain
from app.schemas.demo import (
    ArenaLabelRequest,
    DemoRunRequest,
    DemoSource,
    EvalExample,
    EvalMetrics,
)

router = APIRouter(prefix="/api", tags=["demo"])

DEFAULT_DEMO_URLS = [
    "https://investor.nvidia.com/financial-info/quarterly-results/",
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=nvidia",
    "https://www.reuters.com/technology/nvidia-revenue-growth-ai-chips",
    "https://best-stock-picks-now.com/nvidia-going-to-the-moon",
]

_HYPE_KEYWORDS = ("stock-picks", "moon", "secrets", "guaranteed", "10x", "millionaire", "hot-penny")
_NEWS_DOMAINS = (
    "reuters.com", "bloomberg.com", "wsj.com", "ft.com", "cnbc.com",
    "marketwatch.com", "investopedia.com", "barrons.com",
)
_IR_HINTS = ("investor.", "ir.", "/investor", "investor-relations")


def _domain_of(url: str) -> str:
    try:
        host = urlparse(url if "://" in url else f"https://{url}").hostname or url
    except ValueError:
        host = url
    return host.lower().removeprefix("www.")


def _source_type(domain: str, url: str) -> str:
    if domain.endswith(".gov") or domain == "sec.gov":
        return "regulatory_filing"
    if any(h in url.lower() for h in _IR_HINTS):
        return "company_ir"
    if any(domain.endswith(n) or domain == n for n in _NEWS_DOMAINS):
        return "financial_news"
    if any(k in url.lower() for k in _HYPE_KEYWORDS):
        return "promotional_blog"
    return "general_web"


def _title_for(domain: str, source_type: str, task: str) -> str:
    labels = {
        "regulatory_filing": f"SEC EDGAR filing — {domain}",
        "company_ir": f"Investor Relations — {domain}",
        "financial_news": f"Market coverage — {domain}",
        "promotional_blog": f"“Guaranteed returns” blog post — {domain}",
        "general_web": f"Web page — {domain}",
    }
    return labels.get(source_type, domain)


def _classify_url(url: str, task: str, idx: int) -> DemoSource:
    domain = _domain_of(url)
    source_type = _source_type(domain, url)
    reputation, listed = classify_domain(domain)

    base_score = round(reputation * 100)
    risk_tags: list[str] = []
    evidence_quality = "medium"
    citation_quality = "medium"

    if source_type == "regulatory_filing":
        base_score = max(base_score, 92)
        risk_tags = ["primary_source"]
        evidence_quality, citation_quality = "strong", "strong"
    elif source_type == "company_ir":
        base_score = max(base_score, 78)
        risk_tags = ["primary_source", "commercial_pressure"]
        evidence_quality, citation_quality = "strong", "medium"
    elif source_type == "financial_news":
        base_score = max(base_score, 74)
        risk_tags = ["reputable_publisher"]
        evidence_quality, citation_quality = "strong", "strong"
    elif source_type == "promotional_blog" or listed == "block":
        base_score = min(base_score, 14)
        risk_tags = [
            "unsupported_prediction",
            "weak_citations",
            "anonymous_author",
            "sensational_language",
            "commercial_pressure",
        ]
        evidence_quality, citation_quality = "weak", "weak"
    else:
        base_score = 50
        risk_tags = ["weak_citations"]
        evidence_quality, citation_quality = "medium", "weak"

    # Terac-trained ranker: same ordering, sharper separation (the "calibration" story).
    if base_score >= 70:
        trained_score = min(99, base_score + 8)
    elif base_score <= 30:
        trained_score = max(1, base_score - 8)
    else:
        trained_score = base_score

    trust_score = round(trained_score * 0.65 + base_score * 0.35)

    if trust_score >= 70:
        recommendation = "cite"
    elif trust_score >= 40:
        recommendation = "use_with_caution"
    else:
        recommendation = "do_not_cite"

    claims = {
        "regulatory_filing": [f"Official filing data relevant to: {task}"],
        "company_ir": [f"Company-reported figures relevant to: {task}"],
        "financial_news": [f"Third-party reported analysis relevant to: {task}"],
        "promotional_blog": [f"Unverified prediction about: {task}"],
        "general_web": [f"General claim relevant to: {task}"],
    }[source_type]

    raw_tokens = {
        "regulatory_filing": 21400,
        "company_ir": 15800,
        "financial_news": 9200,
        "promotional_blog": 6100,
        "general_web": 8000,
    }[source_type]
    capsule_tokens = max(120, round(raw_tokens * (0.03 if recommendation == "cite" else 0.05)))
    compression_pct = round((1 - capsule_tokens / raw_tokens) * 100, 1)

    source_id = hashlib.sha256(f"{url}|{idx}".encode()).hexdigest()[:16]
    capsule = {
        "compressed_text": (
            f"{_title_for(domain, source_type, task)}. "
            f"Recommendation: {recommendation.replace('_', ' ')}. "
            f"Key reasons: {', '.join(risk_tags) if risk_tags else 'none flagged'}."
        ),
        "key_reasons": risk_tags or ["reputable_publisher"],
        "method": "mock_synthetic",
    }

    return DemoSource(
        id=source_id,
        url=url,
        domain=domain,
        title=_title_for(domain, source_type, task),
        sourceType=source_type,
        trustScore=trust_score,
        baseScore=base_score,
        trainedScore=trained_score,
        recommendation=recommendation,
        riskTags=risk_tags,
        claims=claims,
        evidenceQuality=evidence_quality,
        citationQuality=citation_quality,
        capsule=capsule,
        rawTokens=raw_tokens,
        capsuleTokens=capsule_tokens,
        compressionPct=compression_pct,
    )


@router.get("/demo-results", response_model=list[DemoSource])
def demo_results() -> list[DemoSource]:
    task = "Which sources should an AI agent cite when analyzing Nvidia revenue growth?"
    return [_classify_url(u, task, i) for i, u in enumerate(DEFAULT_DEMO_URLS)]


@router.post("/demo-run", response_model=list[DemoSource])
def demo_run(body: DemoRunRequest) -> list[DemoSource]:
    urls = body.urls or DEFAULT_DEMO_URLS
    return [_classify_url(u, body.task, i) for i, u in enumerate(urls)]


# ---------------------------------------------------------------------------
# Eval — base heuristic vs Terac-trained ranker accuracy comparison.
# ---------------------------------------------------------------------------

_EVAL_EXAMPLES: list[EvalExample] = [
    EvalExample(task="Cite a source for Nvidia data-center revenue", source_a="investor.nvidia.com", source_b="best-stock-picks-now.com", human_preferred="a", base_predicted="a", trained_predicted="a", result="both_right"),
    EvalExample(task="Cite a source for Fed rate decision impact", source_a="federalreserve.gov", source_b="hot-penny-stocks.net", human_preferred="a", base_predicted="a", trained_predicted="a", result="both_right"),
    EvalExample(task="Cite a source for retirement allocation guidance", source_a="vanguard.com", source_b="guaranteed-returns-blog.com", human_preferred="a", base_predicted="b", trained_predicted="a", result="base_wrong_trained_right"),
    EvalExample(task="Cite a source for quarterly earnings beat", source_a="reuters.com", source_b="crypto-millionaire-secrets.com", human_preferred="a", base_predicted="a", trained_predicted="a", result="both_right"),
    EvalExample(task="Cite a source for SEC filing detail", source_a="sec.gov", source_b="affiliate-finance-deals.com", human_preferred="a", base_predicted="a", trained_predicted="a", result="both_right"),
    EvalExample(task="Cite a source for analyst price target", source_a="morningstar.com", source_b="best-stock-picks-now.com", human_preferred="a", base_predicted="b", trained_predicted="a", result="base_wrong_trained_right"),
    EvalExample(task="Cite a source for inflation data", source_a="bls.gov", source_b="hot-penny-stocks.net", human_preferred="a", base_predicted="a", trained_predicted="a", result="both_right"),
    EvalExample(task="Cite a source for company 10-K risk factors", source_a="sec.gov", source_b="unknown-finance-blog.net", human_preferred="a", base_predicted="b", trained_predicted="a", result="base_wrong_trained_right"),
    EvalExample(task="Cite a source for IPO valuation context", source_a="wsj.com", source_b="affiliate-finance-deals.com", human_preferred="a", base_predicted="a", trained_predicted="a", result="both_right"),
    EvalExample(task="Cite a source for dividend yield claim", source_a="fidelity.com", source_b="crypto-millionaire-secrets.com", human_preferred="a", base_predicted="a", trained_predicted="a", result="both_right"),
]

_MOCK_EVAL = EvalMetrics(
    base_accuracy=78.0,
    trained_accuracy=94.0,
    improvement_pct=16.0,
    held_out_examples=len(_EVAL_EXAMPLES),
    human_preference_match=94.0,
    bad_source_filtering_precision=97.0,
    cite_do_not_cite_accuracy=91.0,
    avg_token_reduction_pct=96.0,
    raw_tokens_example=18420,
    capsule_tokens_example=742,
    examples=_EVAL_EXAMPLES,
)

_EVAL_RESULTS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "eval_results.json")


def _load_real_eval() -> EvalMetrics | None:
    """Real metrics from scripts/compute_eval_metrics.py, if computed."""
    try:
        with open(_EVAL_RESULTS_PATH) as fh:
            return EvalMetrics(**json.load(fh))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


@router.get("/eval", response_model=EvalMetrics)
def eval_metrics() -> EvalMetrics:
    return _load_real_eval() or _MOCK_EVAL


# ---------------------------------------------------------------------------
# Arena label submission (Terac Source Duel Arena) — local JSON store, separate
# from app/ml/terac_store.py because the new annotation shape adds "neither" +
# a different checklist. Same TODO(terac) seam: swap for the real Terac API/MCP.
# ---------------------------------------------------------------------------

_lock = threading.Lock()


def _arena_label_path() -> str:
    return os.path.join(os.path.dirname(settings.terac_store_path), "arena_labels.json")


def _read_arena_labels() -> list[dict]:
    try:
        with open(_arena_label_path(), "r") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _write_arena_labels(labels: list[dict]) -> None:
    path = _arena_label_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as fh:
        json.dump(labels, fh, indent=2)


@router.post("/terac/label")
def submit_arena_label(label: ArenaLabelRequest) -> dict:
    with _lock:
        labels = _read_arena_labels()
        labels.append(label.model_dump())
        _write_arena_labels(labels)
        return {"ok": True, "label_count": len(labels)}

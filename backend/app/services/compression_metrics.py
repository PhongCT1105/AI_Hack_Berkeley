"""Quality metrics for comparing compressed and uncompressed LLM outputs."""
from __future__ import annotations

from collections import Counter
import json
import re
from typing import Any

_TOKEN_RE = re.compile(r"https?://[^\s\"']+|\$?\d+(?:[.,]\d+)?%?|[A-Za-z][A-Za-z'-]*")
_NUMBER_OR_URL_RE = re.compile(r"https?://[^\s\"']+|\$?\d+(?:[.,]\d+)?%?", re.IGNORECASE)
_PROPER_NOUN_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\b")
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def quality_metrics(reference: str, candidate: str) -> dict[str, Any]:
    """Measure whether compression preserved the downstream decision and facts.

    The uncompressed model output is the reference. We avoid BLEU because the
    target response is structured JSON: agreement on the decision and recall of
    numbers, URLs, and named entities are more meaningful than word order.
    """

    reference_json = _parse_json(reference)
    candidate_json = _parse_json(candidate)
    decision_reference = _decision(reference_json)
    decision_candidate = _decision(candidate_json)
    decision_agreement = (
        decision_reference == decision_candidate
        if decision_reference is not None and decision_candidate is not None
        else False
    )

    token_scores = _overlap_scores(_tokens(reference), _tokens(candidate))
    fact_scores = _overlap_scores(_critical_facts(reference), _critical_facts(candidate))
    return {
        "reference_json_valid": reference_json is not None,
        "compressed_json_valid": candidate_json is not None,
        "reference_decision": decision_reference,
        "compressed_decision": decision_candidate,
        "decision_agreement": decision_agreement,
        "token_precision": token_scores["precision"],
        "token_recall": token_scores["recall"],
        "token_f1": token_scores["f1"],
        "critical_fact_precision": fact_scores["precision"],
        "critical_fact_recall": fact_scores["recall"],
        "critical_fact_f1": fact_scores["f1"],
    }


def summarize_quality(rows: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [row for row in rows if "quality" in row]
    if not completed:
        return {"completed_queries": 0}

    quality = [row["quality"] for row in completed]
    mean_fields = (
        "token_precision",
        "token_recall",
        "token_f1",
        "critical_fact_precision",
        "critical_fact_recall",
        "critical_fact_f1",
    )
    return {
        "completed_queries": len(completed),
        "decision_agreement_rate": _mean_bool(quality, "decision_agreement"),
        "raw_json_valid_rate": _mean_bool(quality, "reference_json_valid"),
        "compressed_json_valid_rate": _mean_bool(quality, "compressed_json_valid"),
        **{f"avg_{field}": _mean(quality, field) for field in mean_fields},
    }


def _parse_json(text: str) -> dict[str, Any] | None:
    match = _JSON_RE.search(text.strip())
    if not match:
        return None
    try:
        decoded = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, dict) else None


def _decision(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    for key in ("citation_decision", "recommendation", "claim_supported"):
        value = payload.get(key)
        if value is not None:
            return f"{key}={str(value).upper()}"
    return None


def _tokens(text: str) -> list[str]:
    return [match.group(0).casefold().rstrip(".,;:") for match in _TOKEN_RE.finditer(text)]


def _critical_facts(text: str) -> list[str]:
    numeric_or_urls = [match.group(0).casefold().rstrip(".,;:") for match in _NUMBER_OR_URL_RE.finditer(text)]
    entities = [match.group(0).casefold() for match in _PROPER_NOUN_RE.finditer(text)]
    return numeric_or_urls + entities


def _overlap_scores(reference: list[str], candidate: list[str]) -> dict[str, float]:
    reference_counts, candidate_counts = Counter(reference), Counter(candidate)
    overlap = sum((reference_counts & candidate_counts).values())
    precision = overlap / sum(candidate_counts.values()) if candidate_counts else 1.0
    recall = overlap / sum(reference_counts.values()) if reference_counts else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def _mean(rows: list[dict[str, Any]], field: str) -> float:
    return round(sum(float(row[field]) for row in rows) / len(rows), 4)


def _mean_bool(rows: list[dict[str, Any]], field: str) -> float:
    return round(sum(bool(row[field]) for row in rows) / len(rows), 4)

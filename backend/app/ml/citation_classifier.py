"""Shared helpers for the Supabase-trained claim/source citation classifier.

The model answers one narrow question: whether a research agent should use a
claim/source as evidence.  It deliberately does not replace the URL feature
ranker in ``services/ranker.py``; these data are labeled at claim level.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


# Positive values mean a source is usable for citation.  The mappings accept
# the common label forms used by annotation tools and Supabase JSON columns.
POSITIVE_LABELS = {"yes", "supported", "true", "good", "use", "usable", "credible", "1"}
NEGATIVE_LABELS = {
    "no", "unsupported", "false", "bad", "avoid", "not_usable", "not credible", "0",
    "questionable", "insufficient_info", "insufficient info", "caution",
}


def parse_json_value(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def normalize_label(value: Any) -> int | None:
    """Return 1 (usable), 0 (not usable), or ``None`` for an unknown label."""
    value = parse_json_value(value)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)) and value in (0, 1):
        return int(value)
    if isinstance(value, Mapping):
        for key in ("would_ai_cite", "label", "human_verdict", "verdict", "value", "answer"):
            if key in value:
                label = normalize_label(value[key])
                if label is not None:
                    return label
        return None
    if isinstance(value, list) and len(value) == 1:
        return normalize_label(value[0])
    if isinstance(value, str):
        normalized = value.strip().lower().replace("-", "_")
        if normalized in POSITIVE_LABELS:
            return 1
        if normalized in NEGATIVE_LABELS:
            return 0
    return None


def record_label(record: Mapping[str, Any], label_column: str) -> int | None:
    """Find a label in a configured column, with conservative common fallbacks."""
    for key in (label_column, "would_ai_cite", "human_verdict", "label", "verdict"):
        if key in record:
            label = normalize_label(record[key])
            if label is not None:
                return label
    return None


def record_text(record: Mapping[str, Any]) -> str:
    """Build one stable text document from the fields present in task exports."""
    parts: list[str] = []
    for key in (
        "research_task", "task", "claim", "title", "author", "source",
        "evidence_url", "url", "capsule", "evidence_text", "content", "text",
    ):
        value = record.get(key)
        if value is None or value == "":
            continue
        value = parse_json_value(value)
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        parts.append(f"{key}: {value}")
    return "\n".join(parts)

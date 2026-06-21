"""Runtime registry for the Supabase-trained citation-usability classifier.

The training script writes a versioned joblib bundle containing either a sklearn
Pipeline or a ``{vectorizer, classifier}`` pair. This module owns loading and
safe inference so the scoring pipeline can use that artifact without depending
on a particular training mode.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from app.core.config import settings

logger = logging.getLogger("captain_america.citation_model")

_model: Any | None = None
_meta: dict[str, Any] = {}


@dataclass(frozen=True)
class CitationPrediction:
    available: bool
    usable_probability: float | None = None
    threshold: float | None = None
    eligible: bool | None = None
    model_version: str | None = None
    error: str | None = None


def load() -> bool:
    """Load the saved citation classifier, returning False when it is absent."""
    global _model, _meta
    _model = None
    _meta = {}
    if not os.path.exists(settings.citation_model_path):
        logger.info("No citation classifier found at %s", settings.citation_model_path)
        return False
    try:
        import joblib

        bundle = joblib.load(settings.citation_model_path)
        model = bundle.get("model") if isinstance(bundle, dict) else None
        if model is None:
            raise ValueError("citation model bundle does not contain a model")
        _model = model
        _meta = dict(bundle.get("meta") or {}) if isinstance(bundle, dict) else {}
        logger.info("Loaded citation classifier from %s", settings.citation_model_path)
        return True
    except Exception as exc:  # pragma: no cover - protects API startup
        logger.warning("Failed to load citation classifier: %s", exc)
        return False


def is_loaded() -> bool:
    return _model is not None


def meta() -> dict[str, Any]:
    return dict(_meta)


def cache_fingerprint() -> str:
    """Stable cache namespace that changes whenever a new artifact is loaded."""
    if not is_loaded():
        return "unavailable"
    return str(_meta.get("trained_at") or _meta.get("model_type") or "loaded")


def assess(document: str, threshold: float) -> CitationPrediction:
    """Return citation usability without letting a model error fail source scoring."""
    if not is_loaded():
        return CitationPrediction(available=False)
    try:
        probability = _predict_probability(document)
        probability = max(0.0, min(1.0, probability))
        return CitationPrediction(
            available=True,
            usable_probability=round(probability, 4),
            threshold=threshold,
            eligible=probability >= threshold,
            model_version=str(_meta.get("trained_at") or _meta.get("model_type") or "loaded"),
        )
    except Exception as exc:  # pragma: no cover - model compatibility guard
        logger.warning("Citation classifier inference failed: %s", exc)
        return CitationPrediction(available=False, error="citation classifier inference failed")


def _predict_probability(document: str) -> float:
    if isinstance(_model, dict):
        vectorizer = _model["vectorizer"]
        classifier = _model["classifier"]
        return float(classifier.predict_proba(vectorizer.transform([document]))[0][1])
    return float(_model.predict_proba([document])[0][1])

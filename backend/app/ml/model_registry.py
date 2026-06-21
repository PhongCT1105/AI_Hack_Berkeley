"""Trained-model registry — the override hinge for the ranker.

For THIS build `is_loaded()` returns False (no model trained yet), so the ranker
always uses the transparent heuristic. When the Terac loop is wired up
(see app/ml/trainer.py), a persisted joblib model drops in here and the ranker
switches to `scorer_mode="logistic_model"` automatically — no other code changes.

The feature order in FEATURE_ORDER is the contract between trainer and predictor.
"""
from __future__ import annotations

import logging
import os

from app.core.config import settings
from app.schemas.score import SourceFeatures

logger = logging.getLogger("captain_ddoski.model_registry")

# Order of the numeric feature vector fed to the logistic model. Keep in sync
# with app/ml/trainer.py when wiring the real training.
FEATURE_ORDER = [
    "https", "has_author", "has_citations", "citation_count", "ad_density",
    "domain_reputation", "clickbait_score", "recency_days_norm", "word_count_norm",
    "outbound_link_count_norm",
]

_model = None
_meta: dict = {}


def feature_vector(f: SourceFeatures) -> list[float]:
    """Map SourceFeatures -> the numeric vector in FEATURE_ORDER."""
    recency_norm = 0.5 if f.recency_days is None else max(0.0, 1.0 - min(f.recency_days, 1825) / 1825)
    return [
        1.0 if f.https else 0.0,
        1.0 if f.has_author else 0.0,
        1.0 if f.has_citations else 0.0,
        min(f.citation_count, 30) / 30.0,
        f.ad_density,
        f.domain_reputation,
        f.clickbait_score,
        recency_norm,
        min(f.word_count, 4000) / 4000.0,
        min(f.outbound_link_count, 100) / 100.0,
    ]


def load() -> bool:
    """Attempt to load a persisted model. Silent + returns False if none exists."""
    global _model, _meta
    if not os.path.exists(settings.ml_model_path):
        return False
    try:
        import joblib

        bundle = joblib.load(settings.ml_model_path)
        _model = bundle["model"]
        _meta = bundle.get("meta", {})
        logger.info("Loaded Terac-trained ranker from %s", settings.ml_model_path)
        return True
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to load model, staying heuristic: %s", exc)
        _model = None
        return False


def is_loaded() -> bool:
    return _model is not None


def predict_proba(vec: list[float]) -> float:
    """Return P(credible) in 0..1. Caller guards with is_loaded()."""
    return float(_model.predict_proba([vec])[0][1])


def coefficients() -> dict[str, float] | None:
    if _model is None:
        return None
    try:
        coefs = _model.coef_[0]
        return {name: round(float(c), 4) for name, c in zip(FEATURE_ORDER, coefs)}
    except Exception:
        return None


def meta() -> dict:
    return dict(_meta)

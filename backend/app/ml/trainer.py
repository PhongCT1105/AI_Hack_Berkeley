"""Train a small logistic ranker from Terac pairwise labels.

STUB THIS BUILD — not trained. The function below is the skeleton a teammate
fills in once real Terac expert labels are flowing. Until then the ranker uses
the transparent heuristic (model_registry.is_loaded() stays False).

# TODO(terac): To make training live —
#   1. Gather labels via Terac (terac_store currently holds locally-submitted
#      labels; swap to authoritative Terac labels — see terac_store.py).
#   2. Build pairwise rows: x = feature_vector(A) - feature_vector(B)
#      (model_registry.FEATURE_ORDER defines the vector), y = 1 if winner == "a"
#      else 0; drop "tie" rows or model them as 0.5 with sample weights.
#   3. Fit sklearn LogisticRegression on (X, y).
#   4. joblib.dump({"model": clf, "meta": {...}}, settings.ml_model_path).
#   5. Call model_registry.load() — is_loaded() flips True and the ranker
#      switches scorer_mode to "logistic_model" automatically. No other changes.
"""
from __future__ import annotations

import logging

from app.core.config import settings
from app.ml import model_registry, terac_store

logger = logging.getLogger("agentshield.trainer")

MIN_LABELS = 20


def can_train() -> tuple[bool, str]:
    n = terac_store.label_count()
    if n < MIN_LABELS:
        return False, f"Need >= {MIN_LABELS} labels to train; have {n}."
    return True, "Ready to train."


def train() -> dict:
    """Returns a status dict. STUB: refuses to train and explains what's missing.

    Wire the steps in the module docstring to make this real.
    """
    ok, msg = can_train()
    if not ok:
        return {"trained": False, "note": msg}

    # TODO(terac): implement the real fit here. Intentionally not training in this
    # build so the demo's active scorer stays the transparent heuristic.
    logger.info("train() called but Terac training is not yet wired (UI-only build).")
    return {
        "trained": False,
        "note": (
            "Terac training not configured yet. Labels are being collected; a "
            "teammate will wire the Terac API/MCP + sklearn fit (see trainer.py "
            "TODO). Active scorer remains the heuristic baseline."
        ),
    }


__all__ = ["train", "can_train", "MIN_LABELS", "settings", "model_registry"]

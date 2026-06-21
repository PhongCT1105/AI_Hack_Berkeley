"""Train a small logistic ranker from Terac pairwise labels, gated on a
held-out accuracy proof against the deployed heuristic.

Pairwise rows: x = feature_vector(A) - feature_vector(B)
(model_registry.FEATURE_ORDER defines the vector), y = 1 if winner == "a" else
0. Ties are dropped. Rows are mirrored (x -> -x, y -> 1-y) after the holdout
split so doubling the data never leaks a pair across train/holdout.

The holdout proof reuses score_a/score_b already stored on each pair: the
heuristic's own pairwise call (score_a > score_b) is the baseline a candidate
model must beat by a margin before it's allowed to replace the heuristic.
"""
from __future__ import annotations

import logging
import random
from datetime import datetime, timezone
from typing import Any

from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes

from app.core.config import settings
from app.core.observability import get_tracer
from app.ml import model_registry, terac_store

logger = logging.getLogger("captain_ddoski.trainer")

MIN_LABELS = 20
HOLDOUT_FRACTION = 0.2
IMPROVEMENT_MARGIN = 0.03
MIN_HOLDOUT_ACCURACY = 0.55
RANDOM_SEED = 42


def can_train() -> tuple[bool, str]:
    n = terac_store.label_count()
    if n < MIN_LABELS:
        return False, f"Need >= {MIN_LABELS} labels to train; have {n}."
    return True, "Ready to train."


def _usable_rows() -> list[dict]:
    pairs_by_id = {p["pair_id"]: p for p in terac_store.all_pairs()}
    rows = []
    for label in terac_store.all_labels():
        winner = label.get("winner")
        if winner not in ("a", "b"):
            continue
        pair = pairs_by_id.get(label["pair_id"])
        if not pair or pair.get("features_a") is None or pair.get("features_b") is None:
            continue
        rows.append({
            "x": [a - b for a, b in zip(pair["features_a"], pair["features_b"])],
            "y": 1 if winner == "a" else 0,
            "score_a": pair["score_a"],
            "score_b": pair["score_b"],
        })
    return rows


def train() -> dict:
    """Fit a candidate model and only promote it if it beats the heuristic's
    own pairwise accuracy on a held-out split of the same human labels.

    Wrapped in its own EVALUATOR span: this is the "proves improvement
    against held-out human labels" step from the monitored-MCP pitch, and the
    one piece of the retrain loop where the actual decision (promote vs keep
    heuristic) needs to be auditable in Arize, not just in the log line.
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("captain_ddoski.trainer.train") as span:
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.EVALUATOR.value)
        result = _train()
        span.set_attribute("trainer.trained", bool(result.get("trained")))
        span.set_attribute("trainer.note", result.get("note", ""))
        if "holdout_accuracy" in result:
            span.set_attribute("trainer.holdout_accuracy", result["holdout_accuracy"])
        if "baseline_accuracy" in result:
            span.set_attribute("trainer.baseline_accuracy", result["baseline_accuracy"])
        if "n_labels_used" in result:
            span.set_attribute("trainer.n_labels_used", result["n_labels_used"])
        if "holdout_size" in result:
            span.set_attribute("trainer.holdout_size", result["holdout_size"])
        span.set_attribute(SpanAttributes.OUTPUT_VALUE, str(result))
        return result


def fit_candidate() -> tuple[Any | None, dict]:
    """Fit a candidate model and evaluate it against the heuristic baseline
    on a held-out split, WITHOUT persisting or promoting it.

    train() calls this and only promotes when the candidate clears the bar.
    The comparison showcase also calls this directly: it wants the
    candidate's real numbers — pass or fail — instead of waiting for a model
    that has already been promoted into production.
    """
    ok, msg = can_train()
    if not ok:
        return None, {"trained": False, "note": msg}

    rows = _usable_rows()
    if len(rows) < MIN_LABELS:
        return None, {"trained": False, "note": f"Need >= {MIN_LABELS} usable labeled pairs (with features); have {len(rows)}."}

    try:
        from sklearn.linear_model import LogisticRegression
    except ImportError:
        return None, {"trained": False, "note": "scikit-learn is not installed."}

    rng = random.Random(RANDOM_SEED)
    shuffled = rows[:]
    rng.shuffle(shuffled)
    split = max(1, int(len(shuffled) * (1 - HOLDOUT_FRACTION)))
    train_rows, holdout_rows = shuffled[:split], shuffled[split:]
    if not holdout_rows:
        return None, {"trained": False, "note": "Not enough labels to carve out a held-out split."}

    # Mirror only the training rows: x -> -x, y -> 1-y. Doubles data and
    # removes any order bias without leaking holdout pairs into training.
    X = [r["x"] for r in train_rows] + [[-v for v in r["x"]] for r in train_rows]
    y = [r["y"] for r in train_rows] + [1 - r["y"] for r in train_rows]

    clf = LogisticRegression(max_iter=1000)
    clf.fit(X, y)

    correct = sum(1 for r in holdout_rows if int(clf.predict_proba([r["x"]])[0][1] > 0.5) == r["y"])
    holdout_accuracy = correct / len(holdout_rows)

    baseline_correct = sum(
        1 for r in holdout_rows if int(r["score_a"] > r["score_b"]) == r["y"]
    )
    baseline_accuracy = baseline_correct / len(holdout_rows)

    beats_baseline = (
        holdout_accuracy >= MIN_HOLDOUT_ACCURACY
        and holdout_accuracy >= baseline_accuracy + IMPROVEMENT_MARGIN
    )
    meta = {
        "n_labels_used": len(rows),
        "holdout_accuracy": round(holdout_accuracy, 3),
        "baseline_accuracy": round(baseline_accuracy, 3),
        "holdout_size": len(holdout_rows),
        "beats_baseline": beats_baseline,
    }
    return clf, meta


def _train() -> dict:
    clf, meta = fit_candidate()
    if clf is None:
        return meta

    if not meta["beats_baseline"]:
        note = (
            f"Candidate model holdout accuracy {meta['holdout_accuracy']:.2f} did not beat the "
            f"heuristic baseline {meta['baseline_accuracy']:.2f} by the required {IMPROVEMENT_MARGIN:.2f} "
            f"margin (n_holdout={meta['holdout_size']}). Keeping heuristic active."
        )
        logger.info(note)
        return {
            "trained": False,
            "note": note,
            "holdout_accuracy": meta["holdout_accuracy"],
            "baseline_accuracy": meta["baseline_accuracy"],
        }

    full_meta = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        **{k: v for k, v in meta.items() if k != "beats_baseline"},
    }

    import joblib

    joblib.dump({"model": clf, "meta": full_meta}, settings.ml_model_path)
    logger.info(
        "Promoted new ranker model: holdout_accuracy=%.2f beats baseline=%.2f (n=%d)",
        full_meta["holdout_accuracy"], full_meta["baseline_accuracy"], full_meta["n_labels_used"],
    )
    return {"trained": True, "note": "Promoted: beat heuristic baseline on held-out labels.", **full_meta}


__all__ = ["train", "fit_candidate", "can_train", "MIN_LABELS", "settings", "model_registry"]

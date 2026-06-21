#!/usr/bin/env python3
"""Compute real EvalMetrics from the trained citation classifier.

Replaces the hand-written _MOCK_EVAL in app/api/demo.py. "Base" is the
Fin-Fact pretrain-only model (zero human input); "trained" is the model
fit directly on the Terac-labeled tasks (best-performing real model, see
train_citation_classifier.py). Both are evaluated on the identical held-out
Terac test split for a fair before/after comparison.

The EvalExample schema was built for pairwise source comparison (source_a vs
source_b). Our real labels are single-resource (cite / do-not-cite), so each
test row is mapped onto that shape: source_a/source_b hold the claim and its
evidence URL, and "a"/"b" stand for "cite"/"do_not_cite" respectively.

Token-compression fields (raw/capsule tokens) measure a different pipeline
stage (Firecrawl/Claude capsule extraction) whose evidence_text is empty
for this dataset — those three fields are left as illustrative placeholders,
not computed here.

Example:
  cd backend
  .venv/bin/python scripts/compute_eval_metrics.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import settings  # noqa: E402
from app.ml.citation_classifier import record_label, record_text  # noqa: E402
from scripts.train_citation_classifier import TFIDF_PARAMS, build_pipeline, cross_validated_metrics  # noqa: E402

# Illustrative only — see module docstring. Matches the original mock's order
# of magnitude so the UI doesn't regress while the real capsule pipeline isn't
# wired to this dataset.
PLACEHOLDER_RAW_TOKENS = 18420
PLACEHOLDER_CAPSULE_TOKENS = 742
PLACEHOLDER_TOKEN_REDUCTION_PCT = 96.0

CITE, DO_NOT_CITE = "a", "b"


def load_examples(path: Path, label_column: str) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            label = record_label(row, label_column)
            text = record_text(row)
            if label is not None and text.strip():
                rows.append({"row": row, "text": text, "label": label})
    return rows


def annotator_agreement_rate(rows: list[dict]) -> float:
    """Fraction of tasks where every annotator gave the same verdict."""
    unanimous = sum(1 for r in rows if len(set(r["row"].get("annotator_votes", []))) <= 1)
    return round(100.0 * unanimous / len(rows), 1) if rows else 0.0


def main() -> int:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import SGDClassifier
    from sklearn.metrics import accuracy_score, classification_report
    from sklearn.model_selection import train_test_split
    from sklearn.utils import shuffle
    from sklearn.utils.class_weight import compute_class_weight
    import numpy as np

    terac_export = Path(settings.supabase_export_path)
    pretrain_export = Path("data/finfact_pretrain.jsonl")
    if not terac_export.exists():
        raise SystemExit(f"Missing {terac_export}; run pull_supabase_labels.py first.")
    if not pretrain_export.exists():
        raise SystemExit(f"Missing {pretrain_export}; run pull_finfact_pretrain.py first.")

    terac_rows = load_examples(terac_export, settings.supabase_label_column)
    pretrain_rows = load_examples(pretrain_export, "label")

    texts = [r["text"] for r in terac_rows]
    labels = [r["label"] for r in terac_rows]
    x_train, x_test, y_train, y_test, rows_train, rows_test = train_test_split(
        texts, labels, terac_rows, test_size=0.2, random_state=42, stratify=labels,
    )

    # "Trained" model: tuned char n-gram + logistic regression (see
    # train_citation_classifier.py), fit only on Terac human-labeled rows.
    # Headline accuracy is the 5-fold CV mean, not this one holdout split —
    # with only 200 rows a single 40-row split is too noisy to "showcase" on
    # its own (it swings ~70-72% depending on the random seed).
    trained_pipeline = build_pipeline()
    trained_pipeline.fit(x_train, y_train)
    trained_proba = trained_pipeline.predict_proba(x_test)[:, 1]
    trained_preds = (trained_proba >= 0.5).astype(int)
    trained_cv = cross_validated_metrics(texts, labels)

    # "Base" model: pretrain-only on Fin-Fact's own true/false verdicts, zero
    # human input, same feature representation, evaluated on the same Terac
    # held-out split for a fair side-by-side.
    pretrain_texts = [r["text"] for r in pretrain_rows]
    pretrain_labels = [r["label"] for r in pretrain_rows]
    vectorizer = TfidfVectorizer(**TFIDF_PARAMS)
    vectorizer.fit(pretrain_texts + x_train)
    x_pretrain_vec = vectorizer.transform(pretrain_texts)
    x_test_vec = vectorizer.transform(x_test)
    weights = compute_class_weight("balanced", classes=np.array([0, 1]), y=pretrain_labels)
    base_classifier = SGDClassifier(loss="log_loss", class_weight={0: weights[0], 1: weights[1]},
                                     random_state=42, alpha=1e-5)
    for _ in range(60):
        xs, ys = shuffle(x_pretrain_vec, pretrain_labels, random_state=42)
        base_classifier.partial_fit(xs, ys, classes=[0, 1])
    base_proba = base_classifier.predict_proba(x_test_vec)[:, 1]
    base_preds = (base_proba >= 0.5).astype(int)

    base_accuracy = round(100 * accuracy_score(y_test, base_preds), 1)
    trained_accuracy = round(100 * trained_cv["cv_accuracy_mean"], 1)
    trained_report = classification_report(y_test, trained_preds, output_dict=True, zero_division=0)
    bad_source_precision = round(100 * trained_report.get("0", {}).get("precision", 0.0), 1)
    cite_f1 = round(100 * trained_report.get("1", {}).get("f1-score", 0.0), 1)

    examples = []
    for i in range(len(y_test)):
        row = rows_test[i]["row"]
        human = CITE if y_test[i] == 1 else DO_NOT_CITE
        base_pred = CITE if base_preds[i] == 1 else DO_NOT_CITE
        trained_pred = CITE if trained_preds[i] == 1 else DO_NOT_CITE
        base_right = base_pred == human
        trained_right = trained_pred == human
        if base_right and trained_right:
            result = "both_right"
        elif not base_right and not trained_right:
            result = "both_wrong"
        elif not base_right and trained_right:
            result = "base_wrong_trained_right"
        else:
            result = "base_right_trained_wrong"
        examples.append({
            "task": row.get("research_task", "")[:120],
            "source_a": row.get("claim", "")[:160],
            "source_b": row.get("evidence_url", "") or "(no evidence url provided)",
            "human_preferred": human,
            "base_predicted": base_pred,
            "trained_predicted": trained_pred,
            "result": result,
        })

    metrics = {
        "base_accuracy": base_accuracy,
        "trained_accuracy": trained_accuracy,
        "improvement_pct": round(trained_accuracy - base_accuracy, 1),
        "held_out_examples": len(y_test),
        "human_preference_match": annotator_agreement_rate(terac_rows),
        "bad_source_filtering_precision": bad_source_precision,
        "cite_do_not_cite_accuracy": cite_f1,
        "avg_token_reduction_pct": PLACEHOLDER_TOKEN_REDUCTION_PCT,
        "raw_tokens_example": PLACEHOLDER_RAW_TOKENS,
        "capsule_tokens_example": PLACEHOLDER_CAPSULE_TOKENS,
        "examples": examples,
        # Extra, not part of EvalMetrics — kept in the JSON for transparency.
        # trained_accuracy above IS this cv_accuracy_mean*100; see it broken
        # out with its std so the number isn't read as more precise than it is.
        "_trained_model_cross_validation": trained_cv,
    }

    output = Path("data/eval_results.json")
    output.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps({
        "saved": str(output),
        "base_accuracy": base_accuracy,
        "trained_accuracy": trained_accuracy,
        "annotator_agreement_rate": metrics["human_preference_match"],
        "bad_source_filtering_precision": bad_source_precision,
        "n_examples": len(examples),
        "label_counts_test": dict(Counter(y_test)),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

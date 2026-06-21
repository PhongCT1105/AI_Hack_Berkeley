#!/usr/bin/env python3
"""Train a claim/source usability classifier from the Supabase JSONL export.

The artifact includes its vectorizer and metadata, so inference only needs the
saved joblib file.  It is intentionally a transparent baseline: TF-IDF +
regularized logistic regression, not an opaque LLM fine-tune.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import settings  # noqa: E402
from app.ml.citation_classifier import record_label, record_text  # noqa: E402


def load_examples(path: Path, label_column: str) -> tuple[list[str], list[int]]:
    texts: list[str] = []
    labels: list[int] = []
    with path.open(encoding="utf-8") as fh:
        for line_number, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc
            label = record_label(row, label_column)
            text = record_text(row)
            if label is not None and text.strip():
                texts.append(text)
                labels.append(label)
    return texts, labels


def main() -> int:
    parser = argparse.ArgumentParser(description="Train citation/usability classifier")
    parser.add_argument("--input", type=Path, default=Path(settings.supabase_export_path))
    parser.add_argument("--label-column", default=settings.supabase_label_column)
    parser.add_argument("--output", type=Path, default=Path(settings.citation_model_path))
    parser.add_argument("--test-size", type=float, default=0.2)
    args = parser.parse_args()
    if not 0 < args.test_size < 0.5:
        parser.error("--test-size must be between 0 and 0.5")
    if not args.input.exists():
        parser.error(f"Input export does not exist: {args.input}. Run pull_supabase_labels.py first.")

    texts, labels = load_examples(args.input, args.label_column)
    counts = Counter(labels)
    if len(texts) < 20:
        parser.error(f"Need at least 20 labeled rows; found {len(texts)}")
    if len(counts) != 2:
        parser.error(f"Need both usable (1) and not-usable (0) labels; found {dict(counts)}")
    if min(counts.values()) < 2:
        parser.error(f"Each class needs at least 2 rows for a stratified split; found {dict(counts)}")

    from joblib import dump
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import classification_report, roc_auc_score
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline

    x_train, x_test, y_train, y_test = train_test_split(
        texts, labels, test_size=args.test_size, random_state=42, stratify=labels,
    )
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_df=0.98,
                                  max_features=40_000, sublinear_tf=True)),
        ("classifier", LogisticRegression(max_iter=2_000, class_weight="balanced", random_state=42)),
    ])
    pipeline.fit(x_train, y_train)
    probabilities = pipeline.predict_proba(x_test)[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    report = classification_report(y_test, predictions, output_dict=True, zero_division=0)
    metrics = {
        "test_rows": len(y_test),
        "accuracy": round(float(report["accuracy"]), 4),
        "f1_usable": round(float(report["1"]["f1-score"]), 4),
        "roc_auc": round(float(roc_auc_score(y_test, probabilities)), 4),
    }
    bundle = {
        "model": pipeline,
        "meta": {
            "model_type": "tfidf_logistic_regression",
            "purpose": "claim/source is usable for an AI research citation",
            "label_column": args.label_column,
            "label_mapping": {"1": "usable", "0": "not_usable"},
            "trained_at": datetime.now(UTC).isoformat(),
            "n_examples": len(texts),
            "class_counts": dict(counts),
            "metrics": metrics,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    dump(bundle, args.output)
    print(json.dumps({"saved": str(args.output), **bundle["meta"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

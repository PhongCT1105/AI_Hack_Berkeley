#!/usr/bin/env python3
"""Train a claim/source usability classifier from labeled task exports.

Two modes:

- Single-dataset (no --pretrain-input): TF-IDF + logistic regression on one
  labeled export. This is the original baseline trainer.

- Two-stage (--pretrain-input set): pretrain a TF-IDF + SGD classifier on the
  Fin-Fact-derived pretrain set (Snopes true/false verdicts, no human input),
  then fine-tune (continue training via partial_fit) on the Terac-labeled
  set. Both stages are evaluated on the same held-out Terac test split, so
  the metrics delta isolates the effect of the human annotations.

The artifact includes its vectorizer and metadata, so inference only needs
the saved joblib file.
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


def evaluate(classifier, vectorizer, texts: list[str], labels: list[int]) -> dict:
    from sklearn.metrics import classification_report, roc_auc_score

    x = vectorizer.transform(texts)
    probabilities = classifier.predict_proba(x)[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    report = classification_report(labels, predictions, output_dict=True, zero_division=0)
    return {
        "test_rows": len(labels),
        "accuracy": round(float(report["accuracy"]), 4),
        "f1_usable": round(float(report.get("1", {}).get("f1-score", 0.0)), 4),
        "roc_auc": round(float(roc_auc_score(labels, probabilities)), 4),
    }


# Char n-grams (3-6 chars) + tuned regularization. Found via grid search over
# ngram_range/min_df/max_df/C with 5-fold stratified CV; beat word n-grams
# (CV accuracy 0.60 -> 0.67) and beat ensembling with word/NB models.
TFIDF_PARAMS = {"analyzer": "char_wb", "ngram_range": (3, 6), "min_df": 1, "max_df": 0.85, "sublinear_tf": True}
LOGREG_PARAMS = {"max_iter": 2_000, "class_weight": "balanced", "random_state": 42, "C": 0.1}


def build_pipeline():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline

    return Pipeline([
        ("tfidf", TfidfVectorizer(**TFIDF_PARAMS)),
        ("classifier", LogisticRegression(**LOGREG_PARAMS)),
    ])


def cross_validated_metrics(texts: list[str], labels: list[int], n_splits: int = 5) -> dict:
    """5-fold CV accuracy/AUC — far more stable than one small holdout split,
    since a single 40-row test set has enough variance to make any one number
    look better or worse than the model actually is."""
    from sklearn.model_selection import StratifiedKFold, cross_val_score

    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    acc = cross_val_score(build_pipeline(), texts, labels, cv=cv, scoring="accuracy")
    auc = cross_val_score(build_pipeline(), texts, labels, cv=cv, scoring="roc_auc")
    return {
        "cv_folds": n_splits,
        "cv_accuracy_mean": round(float(acc.mean()), 4),
        "cv_accuracy_std": round(float(acc.std()), 4),
        "cv_roc_auc_mean": round(float(auc.mean()), 4),
        "cv_roc_auc_std": round(float(auc.std()), 4),
    }


def train_single_stage(args, texts: list[str], labels: list[int]) -> None:
    from joblib import dump
    from sklearn.model_selection import train_test_split

    counts = Counter(labels)
    cv_metrics = cross_validated_metrics(texts, labels)

    x_train, x_test, y_train, y_test = train_test_split(
        texts, labels, test_size=args.test_size, random_state=42, stratify=labels,
    )
    pipeline = build_pipeline()
    pipeline.fit(x_train, y_train)
    holdout_metrics = evaluate(pipeline.named_steps["classifier"], pipeline.named_steps["tfidf"], x_test, y_test)

    # Final artifact is refit on all labeled data for deployment; cv_metrics is
    # the trustworthy generalization estimate, holdout_metrics is one example split.
    pipeline_final = build_pipeline()
    pipeline_final.fit(texts, labels)

    bundle = {
        "model": pipeline_final,
        "meta": {
            "model_type": "tfidf_char_ngram_logistic_regression",
            "purpose": "claim/source is usable for an AI research citation",
            "label_column": args.label_column,
            "label_mapping": {"1": "usable", "0": "not_usable"},
            "trained_at": datetime.now(UTC).isoformat(),
            "n_examples": len(texts),
            "class_counts": dict(counts),
            "metrics": holdout_metrics,
            "cross_validated_metrics": cv_metrics,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    dump(bundle, args.output)
    print(json.dumps({"saved": str(args.output), **bundle["meta"]}, indent=2))


def train_pretrain_then_finetune(
    args, pretrain_texts: list[str], pretrain_labels: list[int],
    terac_texts: list[str], terac_labels: list[int],
) -> None:
    from joblib import dump
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import SGDClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.utils import shuffle
    from sklearn.utils.class_weight import compute_class_weight

    terac_train_texts, terac_test_texts, terac_train_labels, terac_test_labels = train_test_split(
        terac_texts, terac_labels, test_size=args.test_size, random_state=42, stratify=terac_labels,
    )

    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_df=0.98,
                                  max_features=40_000, sublinear_tf=True)
    vectorizer.fit(pretrain_texts + terac_train_texts)

    x_pretrain = vectorizer.transform(pretrain_texts)
    x_terac_train = vectorizer.transform(terac_train_texts)

    import numpy as np
    weights = compute_class_weight("balanced", classes=np.array([0, 1]), y=pretrain_labels)
    class_weight = {0: weights[0], 1: weights[1]}
    classifier = SGDClassifier(loss="log_loss", class_weight=class_weight, random_state=42, alpha=1e-5)

    for _ in range(args.pretrain_epochs):
        xs, ys = shuffle(x_pretrain, pretrain_labels, random_state=42)
        classifier.partial_fit(xs, ys, classes=[0, 1])
    metrics_pretrain_only = evaluate(classifier, vectorizer, terac_test_texts, terac_test_labels)

    for _ in range(args.finetune_epochs):
        xs, ys = shuffle(x_terac_train, terac_train_labels, random_state=42)
        classifier.partial_fit(xs, ys)
    metrics_finetuned = evaluate(classifier, vectorizer, terac_test_texts, terac_test_labels)

    bundle = {
        "model": {"vectorizer": vectorizer, "classifier": classifier},
        "meta": {
            "model_type": "tfidf_sgd_pretrain_finetune",
            "purpose": "claim/source is usable for an AI research citation",
            "label_column": args.label_column,
            "label_mapping": {"1": "usable", "0": "not_usable"},
            "trained_at": datetime.now(UTC).isoformat(),
            "n_pretrain_examples": len(pretrain_texts),
            "n_finetune_examples": len(terac_train_texts),
            "pretrain_class_counts": dict(Counter(pretrain_labels)),
            "finetune_class_counts": dict(Counter(terac_train_labels)),
            "metrics_pretrain_only": metrics_pretrain_only,
            "metrics_finetuned": metrics_finetuned,
            "improvement": {
                key: round(metrics_finetuned[key] - metrics_pretrain_only[key], 4)
                for key in ("accuracy", "f1_usable", "roc_auc")
            },
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    dump(bundle, args.output)
    print(json.dumps({"saved": str(args.output), **bundle["meta"]}, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Train citation/usability classifier")
    parser.add_argument("--input", type=Path, default=Path(settings.supabase_export_path))
    parser.add_argument("--pretrain-input", type=Path, default=None,
                         help="Fin-Fact pretrain JSONL (see pull_finfact_pretrain.py). "
                              "If set, runs two-stage pretrain-then-fine-tune.")
    parser.add_argument("--label-column", default=settings.supabase_label_column)
    parser.add_argument("--output", type=Path, default=Path(settings.citation_model_path))
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--pretrain-epochs", type=int, default=60)
    parser.add_argument("--finetune-epochs", type=int, default=40)
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

    if args.pretrain_input is None:
        train_single_stage(args, texts, labels)
        return 0

    if not args.pretrain_input.exists():
        parser.error(f"Pretrain export does not exist: {args.pretrain_input}. Run pull_finfact_pretrain.py first.")
    pretrain_texts, pretrain_labels = load_examples(args.pretrain_input, "label")
    if len(pretrain_texts) < 20:
        parser.error(f"Need at least 20 pretrain rows; found {len(pretrain_texts)}")

    train_pretrain_then_finetune(args, pretrain_texts, pretrain_labels, texts, labels)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

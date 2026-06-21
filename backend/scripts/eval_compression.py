"""Evaluate Captain Ddoski context compression prototypes.

Run from repo root:
    backend/.venv/bin/python backend/scripts/eval_compression.py
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.prompt_compressor import CompressionConfig, PromptCompressor
from app.services.semantic_ir_compressor import SemanticIRCompressor


DATASET = REPO_ROOT / "data" / "compression_eval.jsonl"


@dataclass(frozen=True)
class EvalRow:
    item_id: str
    method: str
    original_tokens: int
    compressed_tokens: int
    savings_percent: int
    preservation_score: float
    missing: tuple[str, ...]


def main() -> None:
    rows: list[EvalRow] = []
    for item in load_dataset(DATASET):
        rows.append(eval_semantic_ir(item))
        rows.append(eval_sentence_selector(item))

    print_table(rows)
    print_summary(rows)


def load_dataset(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def eval_semantic_ir(item: dict[str, str]) -> EvalRow:
    result = SemanticIRCompressor().compress(item["context"])
    check_text = "\n".join([result.compact_language, result.reconstructed_prompt])
    preserved, missing = preservation(check_text, item["query"])
    return EvalRow(
        item_id=item["id"],
        method="semantic_ir",
        original_tokens=result.original_token_estimate,
        compressed_tokens=result.compact_token_estimate,
        savings_percent=savings(result.original_token_estimate, result.compact_token_estimate),
        preservation_score=score(preserved, missing),
        missing=tuple(missing),
    )


def eval_sentence_selector(item: dict[str, str]) -> EvalRow:
    result = PromptCompressor(CompressionConfig(use_llmlingua2=False)).compress(
        item["context"],
        query=item["query"],
    )
    original_tokens = token_estimate(result.normalized_text)
    compressed_tokens = token_estimate(result.compressed_text)
    preserved, missing = preservation(result.compressed_text, item["query"])
    return EvalRow(
        item_id=item["id"],
        method="sentence_selector",
        original_tokens=original_tokens,
        compressed_tokens=compressed_tokens,
        savings_percent=savings(original_tokens, compressed_tokens),
        preservation_score=score(preserved, missing),
        missing=tuple(missing),
    )


def preservation(text: str, query: str) -> tuple[list[str], list[str]]:
    required = [item.strip() for item in query.split(",") if item.strip()]
    lowered = text.casefold()
    preserved = [item for item in required if item.casefold() in lowered]
    missing = [item for item in required if item.casefold() not in lowered]
    return preserved, missing


def score(preserved: list[str], missing: list[str]) -> float:
    total = len(preserved) + len(missing)
    return round(len(preserved) / total, 3) if total else 1.0


def token_estimate(text: str) -> int:
    return max(1, round(len(text) / 4))


def savings(original_tokens: int, compressed_tokens: int) -> int:
    return max(0, round((1 - compressed_tokens / original_tokens) * 100)) if original_tokens else 0


def print_table(rows: list[EvalRow]) -> None:
    print("id,method,original_tokens,compressed_tokens,savings_percent,preservation_score,missing")
    for row in rows:
        print(
            f"{row.item_id},{row.method},{row.original_tokens},{row.compressed_tokens},"
            f"{row.savings_percent},{row.preservation_score},{'|'.join(row.missing)}"
        )


def print_summary(rows: list[EvalRow]) -> None:
    print("\nsummary")
    for method in sorted({row.method for row in rows}):
        method_rows = [row for row in rows if row.method == method]
        avg_savings = sum(row.savings_percent for row in method_rows) / len(method_rows)
        avg_preservation = sum(row.preservation_score for row in method_rows) / len(method_rows)
        print(f"{method}: avg_savings={avg_savings:.1f}% avg_preservation={avg_preservation:.3f}")


if __name__ == "__main__":
    main()

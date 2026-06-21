"""Compare raw, Captain Ddoski, and The Token Company prompts on citation tasks.

The evaluator saves the raw/compressed inputs and both model outputs after
every item. This makes the run consumable by a later chart or review UI.

Run from ``backend`` after setting ``ANTHROPIC_API_KEY`` and ``TTC_API_KEY``:
    .venv/bin/python scripts/eval_ttc_compression.py
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys
from typing import Any

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from thetokencompany import AsyncTheTokenCompany

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.compression_metrics import quality_metrics, summarize_quality
from app.services.semantic_ir_compressor import FinanceCredibilityCompressor, SemanticIRCompressor


DATASET = BACKEND_ROOT / "data" / "finfact_pretrain.jsonl"
OUTPUT_DIR = BACKEND_ROOT / "data" / "compression_evaluations"
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")
TTC_MODEL = os.getenv("TTC_COMPRESSION_MODEL", "bear-2")
TTC_AGGRESSIVENESS = float(os.getenv("TTC_AGGRESSIVENESS", "0.2"))
MAX_EVIDENCE_CHARS = 12_000
SYSTEM = """You assess whether an AI financial research agent may cite a claim.
Use only the supplied evidence. Do not introduce outside facts. Return only valid JSON."""


def build_prompt(item: dict[str, Any]) -> str:
    """Create a task-specific prompt from the project’s labeled citation data."""

    evidence = str(item.get("evidence_text") or "").strip()[:MAX_EVIDENCE_CHARS]
    return f"""SOURCEGUARD CITATION ASSESSMENT
Task: {item.get("research_task") or "Assess whether this source can be cited."}
Claim: {item.get("claim") or ""}
Author: {item.get("author") or "unknown"}
Source: {item.get("source") or "unknown"}
Evidence URL: {item.get("evidence_url") or "unknown"}

Evidence:
{evidence}

Return exactly this JSON object:
{{
  "citation_decision": "CITE|CAUTION|DO_NOT_CITE",
  "claim_supported": true,
  "risk_tags": ["short_tag"],
  "evidence": ["short supporting or conflicting fact"],
  "rationale": "one concise sentence grounded only in the evidence"
}}
"""


def build_captain_ddoski_prompt(item: dict[str, Any], raw_prompt: str) -> tuple[str, str]:
    """Build the project-native capsule variant for the same downstream task.

    FinanceCredibilityCompressor is the active production compressor. The
    FinFact benchmark also contains general fact-checking evidence, for which
    its finance-specific fields can be empty; Semantic IR is the documented
    project fallback in that case so every task remains evaluable.
    """

    source = f"URL: {item.get('evidence_url') or 'unknown'}\n{item.get('evidence_text') or ''}"
    finance_capsule = FinanceCredibilityCompressor().compress(source).compact_language
    if finance_capsule:
        task_header = raw_prompt.split("Evidence:", 1)[0]
        schema = raw_prompt.split("Return exactly this JSON object:", 1)[-1]
        return (
            f"{task_header}Evidence capsule:\n{finance_capsule}\n\n"
            f"Return exactly this JSON object:{schema}",
            "finance_credibility",
        )

    semantic = SemanticIRCompressor().compress(raw_prompt)
    return semantic.compact_language, "semantic_ir_fallback"


async def call_model(client: AsyncAnthropic, prompt: str) -> dict[str, Any]:
    response = await client.messages.create(
        model=MODEL,
        max_tokens=500,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return {
        "output": "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        ).strip(),
        "input_tokens": int(response.usage.input_tokens),
        "output_tokens": int(response.usage.output_tokens),
    }


async def evaluate(limit: int, output_dir: Path, concurrency: int, resume: bool = False) -> Path:
    global MODEL, TTC_MODEL, TTC_AGGRESSIVENESS
    load_dotenv(BACKEND_ROOT / ".env")
    MODEL = os.getenv("ANTHROPIC_MODEL", MODEL)
    TTC_MODEL = os.getenv("TTC_COMPRESSION_MODEL", TTC_MODEL)
    TTC_AGGRESSIVENESS = float(os.getenv("TTC_AGGRESSIVENESS", str(TTC_AGGRESSIVENESS)))
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    ttc_key = os.getenv("TTC_API_KEY")
    if not anthropic_key or not ttc_key:
        raise SystemExit("Set ANTHROPIC_API_KEY and TTC_API_KEY in backend/.env before running this evaluation.")

    items = load_dataset(DATASET)[:limit]
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_dir.mkdir(parents=True, exist_ok=True)
    latest_path = output_dir / "latest.json"
    if resume and latest_path.exists():
        report = json.loads(latest_path.read_text(encoding="utf-8"))
        if report.get("report_version") != 2:
            raise SystemExit("Cannot resume an evaluation report from a different schema version.")
        run_id = str(report["run_id"])
        completed_ids = {row["task_id"] for row in report["rows"] if row.get("status") == "complete"}
        # Remove partial rows before retrying them, so every task id occurs once.
        report["rows"] = [row for row in report["rows"] if row.get("status") == "complete"]
        items = [item for item in items if item.get("task_id") not in completed_ids]
        report["status"] = "running"
    else:
        report = {
            "report_version": 2,
            "run_id": run_id,
            "status": "running",
            "model": MODEL,
            "ttc_model": TTC_MODEL,
            "ttc_aggressiveness": TTC_AGGRESSIVENESS,
            "dataset": str(DATASET.relative_to(REPO_ROOT)),
            "requested_queries": limit,
            "variants": {
                "raw": "Original, uncompressed task prompt.",
                "captain_ddoski": "FinanceCredibilityCompressor with Semantic IR fallback for non-finance evidence.",
                "ttc": "The Token Company bear-2 compression.",
            },
            "metric_definitions": {
                "decision_agreement": "Exact agreement on citation_decision, recommendation, or claim_supported.",
                "token_f1": "Unigram precision, recall, and F1 of compressed output against the raw-model output.",
                "critical_fact_f1": "Precision, recall, and F1 for numbers, URLs, and capitalized entity phrases.",
                "json_valid": "Whether each model output can be parsed as the required JSON object.",
            },
            "rows": [],
        }
    output_path = output_dir / f"run-{run_id}.json"
    _write_report(report, output_path, latest_path)

    write_lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(concurrency)

    async with AsyncTheTokenCompany(api_key=ttc_key, app_id="captain-ddoski-eval") as compressor:
        client = AsyncAnthropic(api_key=anthropic_key)

        async def evaluate_item(item: dict[str, Any]) -> None:
            async with semaphore:
                await _evaluate_item(
                    item=item,
                    report=report,
                    compressor=compressor,
                    client=client,
                    output_path=output_path,
                    latest_path=latest_path,
                    write_lock=write_lock,
                )

        await asyncio.gather(*(evaluate_item(item) for item in items))

    report["status"] = "complete"
    report["summary"] = _summary(report["rows"])
    _write_report(report, output_path, latest_path)
    return output_path


async def _evaluate_item(
    *,
    item: dict[str, Any],
    report: dict[str, Any],
    compressor: AsyncTheTokenCompany,
    client: AsyncAnthropic,
    output_path: Path,
    latest_path: Path,
    write_lock: asyncio.Lock,
) -> None:
    raw_prompt = build_prompt(item)
    row: dict[str, Any] = {
        "task_id": item.get("task_id"),
        "dataset_label": item.get("label"),
        "variants": {"raw": {"input": raw_prompt}},
        "status": "input_saved",
    }
    async with write_lock:
        report["rows"].append(row)
        _write_report(report, output_path, latest_path)

    try:
        captain_ddoski_prompt, captain_ddoski_method = build_captain_ddoski_prompt(item, raw_prompt)
        ttc_result = await compressor.compress(
            raw_prompt,
            model=TTC_MODEL,
            aggressiveness=TTC_AGGRESSIVENESS,
        )
        row["variants"].update({
            "captain_ddoski": {
                "input": captain_ddoski_prompt,
                "compression_method": captain_ddoski_method,
            },
            "ttc": {
                "input": ttc_result.output,
                "compressor_raw_input_tokens": ttc_result.input_tokens,
                "compressor_output_tokens": ttc_result.output_tokens,
                "compressor_tokens_saved": ttc_result.tokens_saved,
                "compressor_input_token_savings_pct": _savings(
                    ttc_result.input_tokens, ttc_result.output_tokens
                ),
            },
        })
        row["status"] = "compressed_inputs_saved"
        async with write_lock:
            _write_report(report, output_path, latest_path)

        raw_result, captain_ddoski_result, ttc_model_result = await asyncio.gather(
            call_model(client, raw_prompt),
            call_model(client, captain_ddoski_prompt),
            call_model(client, ttc_result.output),
        )
        row["variants"]["raw"]["result"] = raw_result
        row["variants"]["captain_ddoski"].update({
            "result": captain_ddoski_result,
            "llm_input_token_savings_pct": _savings(
                raw_result["input_tokens"], captain_ddoski_result["input_tokens"]
            ),
            "quality_vs_raw": quality_metrics(raw_result["output"], captain_ddoski_result["output"]),
        })
        row["variants"]["ttc"].update({
            "result": ttc_model_result,
            "llm_input_token_savings_pct": _savings(
                raw_result["input_tokens"], ttc_model_result["input_tokens"]
            ),
            "quality_vs_raw": quality_metrics(raw_result["output"], ttc_model_result["output"]),
        })
        row["status"] = "complete"
    except Exception as exc:
        row.update({"status": "failed", "error": str(exc)})
    finally:
        async with write_lock:
            _write_report(report, output_path, latest_path)


def load_dataset(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [row for row in rows if row.get("status") == "complete"]
    variants: dict[str, Any] = {}
    if completed:
        raw_tokens = [row["variants"]["raw"]["result"]["input_tokens"] for row in completed]
        variants["raw"] = {"avg_llm_input_tokens": round(sum(raw_tokens) / len(raw_tokens), 2)}
        for name in ("captain_ddoski", "ttc"):
            items = [row["variants"][name] for row in completed]
            quality = summarize_quality([{"quality": item["quality_vs_raw"]} for item in items])
            variants[name] = {
                "avg_llm_input_tokens": round(
                    sum(item["result"]["input_tokens"] for item in items) / len(items), 2
                ),
                "avg_llm_input_token_savings_pct": round(
                    sum(float(item["llm_input_token_savings_pct"]) for item in items) / len(items), 2
                ),
                **quality,
            }
            if name == "ttc":
                variants[name]["avg_compressor_input_token_savings_pct"] = round(
                    sum(float(item["compressor_input_token_savings_pct"]) for item in items) / len(items), 2
                )
    return {
        "completed_queries": len(completed),
        "failed_queries": len(rows) - len(completed),
        "variants": variants,
    }


def _savings(original_tokens: int, compressed_tokens: int) -> float:
    if original_tokens <= 0:
        return 0.0
    return round((1 - compressed_tokens / original_tokens) * 100, 2)


def _write_report(report: dict[str, Any], output_path: Path, latest_path: Path) -> None:
    serialized = json.dumps(report, indent=2, ensure_ascii=False)
    for path in (output_path, latest_path):
        temporary = path.with_suffix(".tmp")
        temporary.write_text(serialized, encoding="utf-8")
        temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=30, help="Number of dataset queries to evaluate (default: 30).")
    parser.add_argument("--concurrency", type=int, default=3, help="Maximum concurrent benchmark tasks (default: 3).")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--resume", action="store_true", help="Continue incomplete tasks from the latest saved report.")
    args = parser.parse_args()
    if args.limit < 1 or args.concurrency < 1:
        raise SystemExit("--limit and --concurrency must be at least 1")
    path = asyncio.run(evaluate(args.limit, args.output_dir, args.concurrency, args.resume))
    print(f"Saved compression evaluation to {path}")


if __name__ == "__main__":
    main()

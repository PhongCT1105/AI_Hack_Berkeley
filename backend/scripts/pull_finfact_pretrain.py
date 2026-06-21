#!/usr/bin/env python3
"""Pull a pretraining set from the public Fin-Fact dataset (Snopes-derived).

This is a *different* sample than the 200 claims sent to Terac for human
annotation — those stay reserved for fine-tuning and held-out eval, never for
pretraining, so the human-input improvement story stays honest.

Fin-Fact's own "label" (true/false/neutral) is used as the pretrain target:
true -> citable (1), false -> not citable (0). "neutral" is dropped since it
is not a confident binary signal.

Finance-only filtering caps out around ~210 rows after dedup/exclusion (Fin-Fact
only has ~433 finance-tagged rows total, and 200 of those are already reserved
for Terac). Pass --finance-only to keep the stricter domain filter; by default
this pulls from all Fin-Fact topics to reach the requested --limit.

Example:
  cd backend
  .venv/bin/python scripts/pull_finfact_pretrain.py --limit 500
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import settings  # noqa: E402

FINANCE_KEYWORDS = re.compile(
    r"\b(stock|share|market|invest|fund|earnings|revenue|dividend|crypto|bitcoin|bond|interest rate|"
    r"inflation|economy|economic|price|trading|trader|nasdaq|dow|s&p|ipo|profit|loss|debt|loan|tax|"
    r"bank|fiscal|gdp|currency|asset|portfolio|valuation|merger|acquisition)\b",
    re.IGNORECASE,
)
LABEL_MAP = {"true": 1, "false": 0}
BASE_URL = (
    "https://datasets-server.huggingface.co/rows"
    "?dataset=amanrangapur%2FFin-Fact&config=default&split=train"
)


def fetch_rows(page_size: int = 100) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    total = None
    while total is None or offset < total:
        endpoint = f"{BASE_URL}&offset={offset}&length={page_size}"
        req = urllib.request.Request(endpoint, headers={"User-Agent": "CaptainAmerica/1.0"})
        for attempt in range(5):
            try:
                with urllib.request.urlopen(req, timeout=45) as resp:
                    payload = json.load(resp)
                break
            except urllib.error.HTTPError as exc:
                if exc.code != 429 or attempt == 4:
                    raise
                time.sleep(2 ** attempt)
        page = [x["row"] for x in payload.get("rows", []) if isinstance(x, dict)]
        if not page:
            break
        rows.extend(page)
        total = payload.get("num_rows_total", offset + len(page))
        offset += len(page)
        time.sleep(0.3)
    return rows


def normalize_claim(claim: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", claim.lower()).strip()


def evidence_text_of(row: dict) -> str:
    sentences = [
        str(item.get("sentence") or "").strip()
        for item in (row.get("evidence") or [])
        if isinstance(item, dict) and item.get("sentence")
    ]
    return "\n".join(f"• {s}" for s in sentences[:5])[:1200]


def load_existing_claims(path: Path) -> set[str]:
    if not path.exists():
        return set()
    claims: set[str] = set()
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            claim = row.get("claim", "")
            if claim:
                claims.add(normalize_claim(claim))
    return claims


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a Fin-Fact pretrain export (not Terac-labeled)")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument(
        "--finance-only", action="store_true",
        help="Restrict to finance-keyword claims (caps out around ~210 rows after exclusion)",
    )
    parser.add_argument(
        "--exclude-from",
        type=Path,
        default=Path(settings.supabase_export_path),
        help="JSONL of claims to exclude (the Terac-labeled set) so pretrain never overlaps eval",
    )
    parser.add_argument("--output", type=Path, default=Path("data/finfact_pretrain.jsonl"))
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")

    exclude = load_existing_claims(args.exclude_from)
    raw = fetch_rows()

    seen: set[str] = set()
    out: list[dict] = []
    for row in raw:
        claim = str(row.get("claim") or "").strip()
        label = LABEL_MAP.get(str(row.get("label") or "").strip().lower())
        if len(claim) < 12 or label is None:
            continue
        key = normalize_claim(claim)
        if key in seen or key in exclude:
            continue
        if args.finance_only and not FINANCE_KEYWORDS.search(claim):
            continue
        seen.add(key)
        out.append({
            "task_id": f"finfact_pretrain_{len(out) + 1:06d}",
            "research_task": (
                "An AI financial research agent is deciding whether it can cite "
                "this claim/source. Judge whether the claim is trustworthy enough to use."
            ),
            "claim": claim,
            "author": str(row.get("author") or ""),
            "source": "snopes.com",
            "evidence_url": str(row.get("url") or ""),
            "evidence_text": evidence_text_of(row),
            "capsule": f"Claim submitted for review: {claim}",
            "label": label,
        })
        if len(out) >= args.limit:
            break

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        for row in out:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    positives = sum(r["label"] for r in out)
    print(json.dumps({
        "saved": str(args.output),
        "rows": len(out),
        "label_true": positives,
        "label_false": len(out) - positives,
        "excluded_terac_claims": len(exclude),
        "raw_rows_scanned": len(raw),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

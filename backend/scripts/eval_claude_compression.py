"""Run original vs compressed context through Claude and compare real token usage.

Two benchmarks:
  - SHORT: 100-word article (unfavorable proportions, shows floor case)
  - LONG:  400-word article (realistic production article, shows target case)

Run from repo root:
    backend/.venv/bin/python backend/scripts/eval_claude_compression.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from anthropic import Anthropic
from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.semantic_ir_compressor import FINANCE_TASK_COMPACT, FinanceCredibilityCompressor


MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")

# --- Verbose baseline task (unchanged for fair comparison) ---
TASK = """You are a finance AI agent helping a user decide whether a web article is trustworthy enough to use in a retirement investment plan.

Evaluate the source carefully.

Return only valid JSON:
{
  "recommendation": "USE | REVIEW | AVOID",
  "trust_score": 0,
  "risk_tags": [],
  "evidence": [],
  "short_rationale": ""
}"""

# --- Short article (100-word, used in initial tests) ---
SOURCE_SHORT = """The article claims that retirees can earn guaranteed 18% annual returns by moving savings into a private crypto yield fund. The source URL is https://best-stock-picks-now.com/double-your-money. The author is listed only as "Market Insider Team," with no individual credentials, no professional license, and no employer disclosure. The article was published on March 14, 2026. It mentions Vanguard and Fidelity but does not link to either company. It says the strategy is "SEC-safe" but provides no SEC filing number, no FINRA BrokerCheck record, and no citations to Federal Reserve data. The page includes affiliate links, urgent language, and a limited-time signup form. It also claims the fund has never lost money, even during market crashes."""

# --- Long article (~400 words, realistic crawled finance page) ---
SOURCE_LONG = """The following article appears at https://best-stock-picks-now.com/double-your-money and was published on March 14, 2026.

DOUBLE YOUR RETIREMENT SAVINGS WITH GUARANTEED 18% ANNUAL RETURNS
By Market Insider Team

Are you worried your retirement savings aren't growing fast enough? Millions of Americans are watching their 401(k) accounts underperform as traditional investments struggle to keep pace with inflation. But there is a proven way to earn guaranteed 18% annual returns — regardless of what the stock market does.

Introducing a groundbreaking private crypto yield fund that has completely changed the retirement investment landscape. Unlike volatile stocks or low-yield bonds, this exclusive fund uses proprietary blockchain yield optimization technology to generate consistent, guaranteed returns of 18% per year. According to our in-house research team, investors in this fund have never lost money — not even during the most severe market crashes and corrections of the past decade, including the 2020 pandemic crash and the 2022 crypto winter.

This strategy has been recognized by top names in the industry. Vanguard and Fidelity have both been monitoring this space closely, recognizing the extraordinary potential of crypto yield investing for retirement portfolios. While these institutions have not yet formally announced participation, our sources indicate they are preparing to offer similar products to their clients in the near future. You can move ahead of that trend today.

Best of all, this fund is fully SEC-safe, operating within all regulatory guidelines without the need for cumbersome SEC filing numbers or FINRA BrokerCheck records. Our compliance team has ensured the strategy aligns with all relevant financial standards. We recommend reviewing the strategy overview document rather than citing specific regulatory filings, as the approach is designed to be self-evidently compliant.

There are several key features that set this fund apart from traditional retirement investments. First, returns are mathematically guaranteed through smart contract technology that automatically rebalances positions. Second, the fund has maintained positive performance through every major market downturn without a single losing year on record. Third, the minimum investment is remarkably accessible, starting at just $5,000 — far lower than most institutional funds.

IMPORTANT: Due to overwhelming demand, we are only accepting new investors through March 31, 2026. Once this limited-time enrollment window closes, the next available slot may not open for six months. Use the signup form below to secure your position before this exclusive opportunity expires.

Note: this article contains affiliate links and our editorial team may receive compensation for referrals to this investment vehicle."""


def main() -> None:
    load_dotenv(BACKEND_ROOT / ".env")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("Missing ANTHROPIC_API_KEY in backend/.env")

    client = Anthropic(api_key=api_key)
    compressor = FinanceCredibilityCompressor()

    print("\n=== BENCHMARK 1: Short article (100 words, unfavorable proportions) ===")
    cap_short = compressor.compress(SOURCE_SHORT)
    _run_benchmark(client, "short", SOURCE_SHORT, TASK, cap_short)

    print("\n=== BENCHMARK 2: Long article (400 words, realistic) ===")
    cap_long = compressor.compress(SOURCE_LONG)
    _run_benchmark(client, "long", SOURCE_LONG, TASK, cap_long)

    print("\n=== BENCHMARK 3: Long article + compact task (full-prompt compression) ===")
    _run_benchmark(client, "long+compact_task", SOURCE_LONG, FINANCE_TASK_COMPACT, cap_long)


def _run_benchmark(
    client: Anthropic,
    label: str,
    source: str,
    task: str,
    compression: object,
) -> None:
    from app.services.semantic_ir_compressor import SemanticIRResult
    assert isinstance(compression, SemanticIRResult)

    original_prompt = f"{task}\n\nSource context:\n{source}"
    compressed_prompt = f"{task}\n\nCompressed source context:\n{compression.compact_language}"

    original = run_claude(client, original_prompt)
    compressed = run_claude(client, compressed_prompt)

    orig_in = int(original["input_tokens"])
    comp_in = int(compressed["input_tokens"])
    savings = round((1 - comp_in / orig_in) * 100, 1)

    report = {
        "benchmark": label,
        "model": MODEL,
        "capsule": compression.compact_language,
        "original_input_tokens": orig_in,
        "compressed_input_tokens": comp_in,
        "input_token_savings_pct": savings,
        "original_output": original["output"],
        "compressed_output": compressed["output"],
    }
    print(json.dumps(report, indent=2))


def run_claude(client: Anthropic, prompt: str) -> dict[str, object]:
    response = client.messages.create(
        model=MODEL,
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text if response.content else ""
    return {
        "output": text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }


if __name__ == "__main__":
    main()

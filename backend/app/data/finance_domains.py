"""Static finance-domain reputation lists.

Scope is FINANCE ONLY by design — a broad domain makes the model hallucinate
trust. These seed reputations are the demo's domain-knowledge prior; the Redis
reputation store (when present) layers a learned rolling reputation on top.

Reputation is 0..1. Anything not listed is treated as neutral (0.5).
"""

# High-trust finance / regulatory / primary sources
ALLOWLIST: dict[str, float] = {
    "sec.gov": 0.98,
    "federalreserve.gov": 0.98,
    "treasury.gov": 0.97,
    "irs.gov": 0.96,
    "cftc.gov": 0.95,
    "finra.org": 0.95,
    "consumerfinance.gov": 0.93,
    "bls.gov": 0.93,
    "imf.org": 0.92,
    "worldbank.org": 0.91,
    "bloomberg.com": 0.88,
    "reuters.com": 0.88,
    "wsj.com": 0.87,
    "ft.com": 0.87,
    "morningstar.com": 0.84,
    "investopedia.com": 0.80,
    "fidelity.com": 0.80,
    "vanguard.com": 0.82,
    "schwab.com": 0.80,
    "nerdwallet.com": 0.70,
}

# Known low-trust patterns: content farms, affiliate-heavy, pump-and-dump styles.
# Demo-friendly placeholders — extend freely.
BLOCKLIST: dict[str, float] = {
    "best-stock-picks-now.com": 0.08,
    "crypto-millionaire-secrets.com": 0.05,
    "guaranteed-returns-blog.com": 0.07,
    "hot-penny-stocks.net": 0.06,
    "affiliate-finance-deals.com": 0.12,
}


def classify_domain(domain: str) -> tuple[float, str | None]:
    """Return (reputation, listed) where listed is "allow" | "block" | None.

    Matches exact domain and any parent domain suffix (so www.sec.gov -> sec.gov).
    """
    d = domain.lower().lstrip("www.")
    for source, listed in ((ALLOWLIST, "allow"), (BLOCKLIST, "block")):
        for known, rep in source.items():
            if d == known or d.endswith("." + known):
                return rep, listed
    return 0.5, None

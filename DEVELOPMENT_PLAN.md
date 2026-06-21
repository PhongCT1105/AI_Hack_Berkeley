# Captain America development plan

This document is the source of truth for what is live, what is synthetic, and what must change
before describing Captain America as a production source-verification product.

## Current state

| Area | Status | What is real today | Constraint or placeholder |
|---|---|---|---|
| Brand and public interfaces | Active | Product name, API caller header, MCP server, tracing, and frontend use Captain America. | The legacy `X-AgentShield-Caller` header and `AGENTSHIELD_*` MCP variables remain only as migration fallbacks. |
| Direct source scoring | Active | `/api/score-source` collects a URL, extracts signals, ranks it, compresses evidence, and records history. | The fallback collector is less reliable than Firecrawl on JavaScript-heavy sites. |
| Prompt-driven research | Active with Firecrawl | `/api/research` uses Firecrawl Search, scores each discovered source, and only synthesizes from `USE` sources. | Firecrawl configuration is mandatory. Per-source scoring failures are currently excluded from the result rather than itemized. |
| Crawl endpoint | Active | `/api/crawl` turns supplied URLs into page, claim, and training-payload records. | It does not discover URLs and does not persist crawl jobs. |
| Citation classifier | Active when artifact exists | The saved Supabase-trained artifact is loaded at startup and can downgrade a `USE` source to `CAUTION` when citation-usability confidence is below the configured threshold. | It is a source-level gate built from extracted claims and evidence snippets, not a claim-by-claim verifier. |
| Terac arena and training | Local-only | Pairs and labels persist to a local JSON store. | `/api/terac/train` is intentionally a stub. There is no authoritative Terac sync or trained ranker. |
| Demo run | Synthetic | `/api/demo-run` returns deterministic domain and keyword heuristics. | It does not call the live collector, extractor, ranker, or Firecrawl. |
| Evaluation | Mixed | `/api/eval` can read a generated `data/eval_results.json`. | The fallback values are mock metrics, and token-compression metrics in the script are placeholders. |
| Persistence and operations | Local-development only | Score history is stored as a local JSON file; optional Redis backs cache and reputation. | No database migration, multi-instance coordination, rate limit, authentication, or retention policy exists. |

## Delivery gates

### Gate 1: Honest live-research demo

Status: ready after Firecrawl is configured.

1. Set `FIRECRAWL_API_KEY` in `backend/.env`.
2. Run `GET /api/health` and require `capabilities.research_discovery: true`.
3. Run `POST /api/research` with a current finance question.
4. Confirm `search_mode: firecrawl_search`, nonzero discovered and inspected counts, and that the
   answer cites only `USE` sources.
5. If any source score fails, expose its failure count and reason in the response before using the
   workflow as an operator-facing tool.

Acceptance: discovery is provider-explicit, sources are inspectable, and no synthetic response is
represented as live research.

### Gate 2: Improve the live citation gate

Status: first source-level gate shipped.

1. Keep the startup-loaded classifier versioned and require its probability threshold to be
   configured per deployment.
2. Score each extracted claim/evidence pair rather than one combined source document.
3. Calibrate the probability threshold on a held-out Supabase-labeled set.
4. Add regression tests with accepted and rejected claims from the real label export.

Acceptance: citation eligibility is calibrated at the claim/evidence level, with the source-level
gate retained as a conservative backstop.

### Gate 3: Replace local Terac loop with a trainable feedback loop

Status: not started.

1. Submit comparison tasks to Terac or ingest authoritative completed labels.
2. Store task and label provenance in durable storage.
3. Implement pairwise training in `backend/app/ml/trainer.py`.
4. Version the resulting artifact, validate it on a held-out set, and load it atomically.
5. Compare the heuristic and trained-ranker policies on a fixed evaluation set before rollout.

Acceptance: `/api/terac/train` produces a versioned artifact and `scorer_mode` can truthfully be
`logistic_model`.

### Gate 4: Replace demo metrics with reproducible evaluation

Status: partially available.

1. Require a generated `data/eval_results.json` in non-demo deployments.
2. Remove mock fallback numbers from production UI or label them as sample data.
3. Measure token reduction from actual Firecrawl plus capsule inputs, not constants.
4. Report dataset version, label count, split strategy, confidence interval, and model version.

Acceptance: every displayed metric can be regenerated from versioned data and code.

### Gate 5: Production hardening

Status: not started.

1. Add authenticated API access, per-caller quotas, request IDs, and structured audit logs.
2. Move history, research jobs, source snapshots, and feedback labels from local JSON to durable
   storage.
3. Make research runs asynchronous with per-source status, retry policy, and cancellation.
4. Add URL validation, SSRF protection, domain policy controls, provider budgets, and secret
   rotation.
5. Add integration tests for Firecrawl success, timeout, malformed result, and quota failure.

Acceptance: the system is safe to operate across multiple instances and failures are observable
without reading server logs.

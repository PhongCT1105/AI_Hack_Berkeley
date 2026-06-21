# Captain Ddoski — Architecture & Pipeline Report

## 1. What it is

**Credibility infrastructure for AI agents (finance domain).** A calling agent (or human, via the
UI) sends `{url, task}`; the system returns a **trust score (0–100)**, **USE / CAUTION / AVOID**,
**risk tags**, per-dimension **verdicts**, extracted **claims + evidence**, and a compressed
**Credibility Capsule** (~9-field DSL, ~150-250 tokens). Exposed as a REST API, an MCP stdio tool,
and an MCP HTTP server.

## 2. Tech stack

| Layer | Stack |
|---|---|
| Frontend | Next.js 16 (App Router) + React 19 + TypeScript, Tailwind v4, shadcn/ui, Recharts, Sentry (`@sentry/nextjs`) |
| Backend | FastAPI (Python 3.13), Pydantic Settings, httpx, async/await throughout |
| LLM | Anthropic Claude (`claude-haiku-4-5` default) — extraction, planning, synthesis |
| Search/Scrape | Firecrawl (Search + Scrape), with a direct-HTTP fallback collector |
| ML | Two separate logistic-regression slots: (1) **citation classifier** — TF-IDF + sklearn `LogisticRegression`, trained on Supabase claim/evidence labels, **populated and active** as the stage-4b citation gate; (2) **ranker logistic model** — `SourceFeatures`-based `LogisticRegression`, meant to replace the heuristic headline `trust_score`, **not yet populated** (no Terac-pairwise training data/loop yet) |
| Compression | Custom `FinanceCredibilityCompressor` (semantic IR), extractive fallback, plus optional **The Token Company (TTC)** transparent Anthropic-client wrapper (`bear-2` model) — wraps the *entire* `messages.create` call, so it compresses the interpolated prompt template **and** the crawled website text together as one unit, not as separate passes |
| Observability | Sentry (errors/perf), **Arize AX** (preferred tracer) or **Phoenix** (fallback) via OpenTelemetry/OpenInference spans — both optional and gracefully no-op |
| Data/labels | Supabase (Postgres) for `source_claim_tasks` / `simple_claim_annotations`; local JSON for score history, Terac auto-launch state, retrain queue |
| Crowd labeling | Terac (opportunities/MCP) — auto-launches labeling tasks when a source fails the gate |
| Cache | Redis if configured, else in-memory |
| Deploy | Render (`render.yaml` — backend as a Python web service); frontend deploys separately (e.g. Vercel) |

## 3. The core pipeline (`Pipeline.score_source`, `backend/app/services/pipeline.py`)

```
URL + task
   │
   ▼
[1] Collector  — Firecrawl Scrape, or direct-HTTP fallback (collector.py)
   │  → title, text, author/date candidates, citation links, redirects
   ▼
[2] Extractor  — Claude extracts claims/evidence/citations; heuristic fallback (extractor.py)
   │  (TTC, when configured, wraps the whole messages.create call — the task/title
   │   prompt template AND the crawled page text are compressed together as one
   │   unit before Claude ever sees them, not compressed in two separate passes)
   ▼
[3] Features   — reputation lookup (allow/block lists, Redis-cached) + feature vector (features.py, reputation.py)
   ▼
[4] Ranker     — transparent heuristic weighted-sum (baseline 50 ± deltas);
   │             swaps to a logistic model if one is trained/loaded (ranker.py)
   ▼
[4b] Citation classifier — TF-IDF + sklearn model gates "USE" sources down to
   │   "CAUTION" if citation-usability probability < threshold (citation_classifier.py)
   ▼
[5] Capsule    — FinanceCredibilityCompressor → compact key=value DSL capsule,
   │             extractive fallback if it fails (capsule.py, semantic_ir_compressor.py)
   ▼
ScoreResponse  — score, recommendation, risk_tags, verdicts, claims, capsule,
                 degradations[], trace_id  → cached, recorded to history,
                 fires terac_auto_launch in background
```

Every stage is wrapped in its own OpenTelemetry span (`stage.collector`, `stage.extractor`, etc.),
tagged with OpenInference span kinds (`TOOL`, `CHAIN`, `EVALUATOR`) so Arize groups the whole call
as one tool invocation. Per-stage failures degrade gracefully into a `degradations[]` list instead
of 500s — **the system always returns a usable verdict, even with zero API keys configured.**

### 3.1 `url` and `task` are not produced the same way — two different entry points

It's tempting to picture a single "understand the prompt, split it into url + task" step. That's
not what happens. The codebase has two separate entry points, and `url` and `task` reach the core
pipeline through entirely different mechanisms depending on which one is used.

**`POST /api/score-source`** — the caller already hands over `{url, task}` pre-split in the
request body. There is no understanding step at all here: neither field is extracted from
anything, they just arrive as two separate fields.

**`POST /api/research`** — the caller sends a single `prompt` string, and `url`/`task` are
produced asymmetrically (`research_agent.py`):

```
prompt
  │
  ├──► plan(prompt) ──► Claude (tool-use call) derives a SEARCH QUERY
  │                       (a short web-search string — NOT the task)
  │                       │
  │                       ▼
  │                  Firecrawl Search(query) ──► discovers N urls
  │
  └──► task = prompt, passed through verbatim, UNCHANGED ──┐
                                                              ▼
                                in ScoreRequest(url=url, task=prompt)
                                for each discovered url, into the §3 core pipeline
```

- **`task`** never goes through any understanding step — the full original prompt is reused
  as-is, verbatim, as the `task` field for *every single discovered source*. Zero transformation.
- **`url`** is the thing that actually goes through a multi-step process: Claude reads the prompt
  and derives a *different* artifact (a short search query) → that query seeds Firecrawl Search →
  which returns a list of URLs. The URL was never sitting "inside" the prompt waiting to be
  extracted; it's discovered externally, guided by (but not equal to) something derived from the
  prompt.

So `task` is a pass-through (the literal input prompt) and `url` is a generated/discovered output
(query-derivation + external search) — they are not peers produced by one shared understanding
step, even though they end up sitting side-by-side in the same `ScoreRequest(url, task)` that goes
into the one core pipeline.

### 3.2 Compression — three independent mechanisms, not one

"Compression" shows up in three unrelated places in this codebase. They have different inputs,
different algorithms, different purposes, and different lifecycles — conflating them is the
easiest way to misdescribe the system.

| # | Mechanism | Compresses | Algorithm | Used in the real `/api/score-source` or `/api/research` run? |
|---|---|---|---|---|
| 1 | **TTC prompt compression** | what *we send to Claude* (inbound) | third-party (`thetokencompany`, model `bear-2`) | **Yes, but conditionally** — only if `TTC_API_KEY` is set. Unset → `create_anthropic_client()` returns a bare client and every Claude call (extractor, research planner, research synthesizer) runs uncompressed. Runs independently at every Claude call site — see below. |
| 2 | **Credibility Capsule** | what *the pipeline hands back to the calling agent* (outbound) | `FinanceCredibilityCompressor` — deterministic regex/keyword extraction, zero model calls, zero API key needed | **Yes, always.** `pipeline.py` imports `app.services.capsule.compress`, which calls this directly at Stage 5 on every scored source — can't be turned off. |
| 3 | **Benchmark/demo compressors** (`semantic_ir`, `sentence_selector`) | arbitrary input text, for comparison only | two selectable algorithms (see below) | **No.** Neither `pipeline.py` nor `research_agent.py` import these. Only reachable via `POST /api/compress`, the `/compress` demo page, and the MCP `compress_context` tool. |

**#1 is not a single compression pass over a `/api/research` request — it fires once per Claude
call, on a fresh client each time, so the stats from one call never accumulate into another's.**
For a research request that discovers 5 sources, that's up to 7 independent compressions if TTC is
configured: 1 for `plan()` (the search-query-planning prompt), 5 for each source's
`_extract_claude()` call (task + title + that source's crawled page text, compressed together as
one payload — see §3 Stage 2), and 1 for `synthesize()` (the final evidence-digest + question
prompt). Each compresses a completely different payload.

**#2 has nothing to do with TTC or any LLM call.** It's the "Token Company track" capsule
described in the README — a hand-written finance-domain extractor that pulls 9 fields (`url, ret,
veh, auth, date, brand, reg, sales, hist`) out of the crawled text + extracted claims + the
ranker's top reasons via regex. It runs unconditionally on every scored source, with or without any
API key configured, and produces the `EvidenceCapsule` returned in `ScoreResponse`.

**#3 exists purely for the demo/eval surface, not the live serving path.** `POST /api/compress`
(`compress.py`) dispatches on a `method` field to one of three algorithms, none of which the live
`score_source`/`research` pipelines call:
  - `"finance_credibility"` — the *same* `FinanceCredibilityCompressor` class as #2, just invoked
    standalone on arbitrary pasted text for the demo page.
  - `"semantic_ir"` — `SemanticIRCompressor`: a generic, non-finance pipeline (`prompt → semantic
    IR (objective/facts/entities/numbers/keywords) → compact DSL → reconstructed prompt`),
    entirely deterministic, no model calls.
  - `"sentence_selector"` — `PromptCompressor`: normalize → dedupe → query-aware sentence
    selection → optional LLMLingua-2 backend compression (falls back to the selected text if the
    optional `llmlingua` package isn't installed).

`scripts/eval_ttc_compression.py` is the one place that compares mechanism #1 and #2 head-to-head
against the uncompressed baseline — three variants (raw prompt, Captain Ddoski capsule, TTC Bear-2)
on the same extraction task, measured in real Claude API token counts, written to
`backend/data/compression_evaluations/` and surfaced at `GET /api/compress/evaluations/latest`.

## 4. Other surfaces built on the same pipeline

- **`POST /api/research`** (`research_agent.py`): see §3.1 for how it turns a single `prompt` into
  many `{url, task}` pairs. Claude plans a search query (tool-use), Firecrawl Search discovers URLs
  (discovery is Firecrawl-only — it reports `discovery_error` rather than silently falling back to
  another provider), each URL is scored through the *same* core pipeline (with `task` = the
  original prompt, unchanged), then Claude synthesizes an answer citing only `USE` sources.
- **`POST /api/crawl`**: structured crawl → training-payload records (no discovery, no job
  persistence).
- **`POST /api/compress`** (Token Company track): isolated compression benchmark — compares raw
  prompt vs. Captain Ddoski capsule vs. TTC Bear-2 compression on real Claude token counts and
  quality metrics (citation-decision agreement, JSON validity, unigram F1, entity/number/URL
  precision-recall).
- **MCP servers**: `backend/mcp_server.py` (stdio, exposes `captain_ddoski_score_source` to Claude
  Code/Cursor) and `backend/app/mcp_server.py` (HTTP FastMCP, exposes raw `compress_context`
  compression tools).
- **Terac auto-launch loop** (`terac_auto_launch.py`): when a scored source misses the
  trust/citation threshold, fires a background task (never blocks the caller) that searches for a
  fresh candidate, inserts a labeling task into Supabase, and creates (and optionally launches) a
  Terac opportunity — bounded by a per-domain cooldown and a hard cap.
- **`/api/system-health`**: reads recent Sentry issues via Sentry's REST API for the dashboard's
  health panel.

## 5. Frontend routes

`/` (dashboard + system health), `/demo` (research), `/compare`, `/compress` (Token Company demo),
`/eval`, `/threats` (flagged-domain feed), `/source/[id]`.

## 6. Results & evaluation

- **`backend/scripts/eval_compression.py` / `eval_claude_compression.py` / `eval_ttc_compression.py`**
  — real-token, three-way (raw / capsule / TTC) compression benchmark, persisted to
  `backend/data/compression_evaluations/`, surfaced live at `GET /api/compress/evaluations/latest`.
- **Latest real numbers** (README): long realistic article → 68.5% token savings with capsule, up
  to 74.2% with a compact task; quality preserved (AVOID verdict held across all variants).
- **`compute_eval_metrics.py`** — trains/evaluates the citation classifier on a held-out
  Supabase-labeled split (Fin-Fact pretrain "base" model vs. Terac-labeled "trained" model), the
  only metric here that's a real before/after; token-compression numbers in that script are
  explicitly marked placeholder since that dataset has no raw evidence text.
- **`/api/eval`** is honestly mixed: real where `data/eval_results.json` exists, mock fallback
  otherwise — this is documented as a known gap in `DEVELOPMENT_PLAN.md`.
- **Terac arena/training is UI-only right now** — pairs/labels persist locally; `/api/terac/train`
  is a stub; the heuristic ranker remains the production scorer (Gate 3 in the development plan,
  "not started").

## 7. Data flow for labeling/training (separate from the live scoring path)

Fin-Fact dataset → filtered to finance claims → seeded into Supabase (`source_claim_tasks`) →
public `/annotate` flow collects `can_ai_cite` labels (3 per task target) into
`simple_claim_annotations` → `pull_supabase_labels.py` exports labeled rows →
`train_citation_classifier.py` trains/versions the TF-IDF+sklearn citation-usability model →
loaded at FastAPI startup and used as the Stage 4b gate.

## 8. Deployment

- **Backend**: `render.yaml` deploys `backend/` as a Render Python web service
  (`uvicorn app.mcp_server:app`, health check at `/api/health`, Python 3.13).
- **Frontend**: Next.js app, intended for Vercel (per `Documentation/SUPABASE_DEPLOYMENT.md`) — no
  `vercel.json` is checked in, env vars configured directly on the host
  (`NEXT_PUBLIC_SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, etc.).
- **Every external integration is optional and capability-flagged** (`settings.has_*`) —
  Anthropic, Firecrawl, Redis, Sentry, Arize/Phoenix, Terac, Supabase, TTC. The app boots and
  serves valid heuristic verdicts with zero keys set; `GET /api/health` reports which capabilities
  are actually live, which is the honest way to demo graceful degradation.

## 9. Product-boundary discipline (per CLAUDE.md)

The three surfaces are deliberately kept distinct in messaging: `/api/score-source` (real
pipeline, URL-supplied), `/api/research` (real, but hard-requires Firecrawl for discovery — no
silent provider swap), and `/api/demo-run` + `/api/eval` + `/api/terac/*` (synthetic/local-only
paths, labeled as such rather than presented as production metrics).

---

## 10. Model input/output contracts

There isn't one model — there are four distinct components, each with its own input/output
contract. This section shows exactly how `{url, task}` gets reshaped at each hop.

### 10.1 Collector — `{url}` → `CollectResult`

**Input:** just `url` (the `task` isn't used here).
**Conversion:** Firecrawl Scrape (or direct-HTTP fallback) fetches the page.
**Output (dataclass):** `final_url, title, text, html, outbound_links, mode
("firecrawl"|"httpx_fallback"), error`.

### 10.2 Extractor — Claude, `{task, title, page_text}` → structured JSON

This is the only LLM call that touches raw page content. `extractor.py` builds the prompt by
interpolating directly:

```
TASK THE AGENT WANTS TO DO: {task}
PAGE TITLE: {title}
PAGE TEXT: {collected.text[:18000]}
```

**Model:** `claude-haiku-4-5` (configurable), structured JSON output requested in the prompt (no
`response_format`/tool schema — it's parsed out of the text with regex + `json.loads`, see
`_loads_json`).
**Output type:** `ExtractResult` dataclass — `claims: list[{text, supported, evidence_snippet,
confidence}]`, `has_author, author_name, has_citations, citation_count, publish_date,
clickbait_signal, mode`.
**Fallback:** if no `ANTHROPIC_API_KEY` or the call throws, a pure-regex heuristic extractor
produces the *same* `ExtractResult` shape with lower-confidence values — callers downstream never
know which path ran except via `mode`.

### 10.3 Ranker — numeric feature vector → score (not text)

**There are two distinct logistic-regression models in this codebase, not one — and they answer
a natural "isn't this just one improving loop?" question, so it's worth being explicit about why
they're separate.**

The intended design (and what this section describes) IS the "get labeled data from Terac and
improve the model over time" loop:

1. Terac Arena shows two sources (A vs B) for a task; a human picks which one an agent should
   cite. `terac_store.py` stores the pair + the `winner` label.
2. `trainer.py` computes `feature_vector(A) - feature_vector(B)` for every labeled pair, fits a
   `LogisticRegression`, and only **promotes** it (saves `data/terac_model.joblib`) if it beats
   the heuristic's own pairwise accuracy on a held-out split of the same labels, with ≥20 labels
   required to even attempt it.
3. `model_registry.py` loads that artifact (if present) and `ranker.py` uses it as the headline
   `trust_score` instead of the heuristic.

This loop runs end-to-end in code today. What's missing is real data flowing into step 1:
`terac_store.py` is explicitly flagged `# TODO(terac): UI-ONLY THIS BUILD` — pairs/labels come
from whoever clicks through the local Arena screen, not from Terac's actual paid annotation API/MCP,
which was never wired in. So no real labels accumulate, `data/terac_model.joblib` never gets
produced, and the ranker silently keeps using the heuristic. "Not yet populated" means the
*artifact this loop is supposed to produce* doesn't exist — not that the loop's code is missing.

`task`/`url` never reach the ranker directly. `features.py` first turns `CollectResult +
ExtractResult + reputation` into `SourceFeatures` — a fixed Pydantic model: `https, has_author,
has_citations, citation_count, ad_density, domain_reputation, domain_listed, clickbait_score,
recency_days, word_count, outbound_link_count`.

Two scorer paths consume `SourceFeatures` differently:

- **Heuristic (always available, currently the production scorer):** `ranker.py` reads each field
  directly off the Pydantic object — no vectorization, just `if/elif` deltas off baseline 50.
- **Ranker logistic model (slot exists, NOT yet populated):**
  `model_registry.py` `feature_vector()` flattens `SourceFeatures` into a fixed 10-float vector in
  `FEATURE_ORDER`, normalizing the unbounded fields (`recency_days`, `word_count`,
  `outbound_link_count` get divided/clamped into 0-1). `model.predict_proba([vec])[0][1]` →
  probability → `×100` → trust score. This model would be trained on Terac pairwise A/B preference
  labels (`features(A) - features(B)` → human-preferred source), per the Gate 3 plan in
  `DEVELOPMENT_PLAN.md`. Its artifact (`data/terac_model.joblib`) doesn't exist yet, so
  `model_registry.load()` silently returns `False` at startup and `is_loaded()` stays `False` —
  the ranker falls through to the heuristic path on every call, automatically, with no code change
  needed once a real artifact lands.

**Output:** `(trust_score: int, contributions: list[FeatureContribution], verdicts: list[Verdict],
risk_tags: list[str], scorer_mode: "heuristic"|"logistic_model")`.

### 10.4 Citation classifier — claim text → usability probability (the model already in production)

This is the logistic-regression model that **is** trained and active today — easy to miss because
it's described elsewhere as "the TF-IDF classifier," but TF-IDF is just the feature extraction
step; `train_citation_classifier.py` builds a `Pipeline([("tfidf", TfidfVectorizer(...)),
("classifier", LogisticRegression(...))])`. So "the TF-IDF classifier" and "a logistic regression
model" are the same object — TF-IDF turns text into numbers, logistic regression turns those
numbers into a probability.

It is trained on Supabase claim/evidence labels (`can_ai_cite`) collected through a **different,
simpler annotation flow** than §10.3's Terac Arena pairwise comparison: the `/annotate` page shows
one claim+evidence pair at a time and asks a plain Yes/No ("can an AI cite this?"), writing
straight to Supabase — no A-vs-B comparison, no Terac pairwise loop involved. That's what makes it
a separate model from the dormant ranker slot, even though both happen to be logistic regressions:
different training data, different annotation UI, different question being answered (claim-level
citation usability vs. source-level credibility ranking).

Terac does touch this model indirectly: `terac_auto_launch.py` can spin up a *paid* Terac
opportunity (single-item labeling, not pairwise) when a source fails the threshold, and that label
lands in the same Supabase table this classifier trains from. So Terac labels do feed into the
model that's actually live — just not via the pairwise Arena mechanism in §10.3.

It's the one place `task` and `url` get reassembled into a *text document* for a model rather than
structured features. `citation_classifier.py` `inference_text()`:

```python
record_text({
    "research_task": task,
    "title": title,
    "author": author or "",
    "url": url,
    "claim": "\n".join(claim["text"] for claim in claims[:6]),
    "evidence_text": "\n".join(claim["evidence_snippet"] for claim in claims[:6]),
})
```

which `record_text()` flattens to one newline-joined string like `"research_task: ...\ntitle:
...\nclaim: ...\nevidence_text: ..."`. This exact string format is also what the training script
builds from Supabase rows (`citation_classifier.py`) — **inference input and training input go
through the identical `record_text()` function**, which is the contract that keeps them
compatible.

**Input → model:** TF-IDF vectorizer transforms that string → sklearn classifier
`.predict_proba()`.
**Output:** `CitationPrediction(available, usable_probability, threshold, eligible,
model_version)` — only allowed to *downgrade* USE→CAUTION, never upgrade.

### 10.5 Capsule compressor — deterministic, not a learned model

`FinanceCredibilityCompressor` is rule-based (regex/keyword extraction over `collected.text` +
`extracted.claims` + the ranker's `top_reasons`), producing the `key=value` DSL capsule. No LLM
call, no trained weights — so technically the pipeline has 2 learned models (Claude extractor,
citation TF-IDF classifier) and one optional learned model (the unloaded logistic ranker), plus 2
deterministic/heuristic components.

### Summary table

| Component | Algorithm | Status | Input type | Conversion from `{url, task}` | Output type |
|---|---|---|---|---|---|
| Collector | — (Firecrawl/HTTP) | active | URL string | direct | `CollectResult` (raw page data) |
| Extractor | Claude LLM | active | prompt string (task+title+page text interpolated, TTC-compressed as one unit when configured) | string interpolation into a fixed template | JSON parsed into `ExtractResult` |
| Heuristic ranker | weighted-sum, no ML | active (production scorer) | `SourceFeatures` (Pydantic fields) | feature engineering from collector+extractor+reputation, task/url discarded | `int` score + explainability lists |
| Ranker logistic model | `LogisticRegression` on `SourceFeatures` vector | **dormant — no artifact trained yet** | `list[float]` (10-dim vector) | `model_registry.feature_vector()` normalizes `SourceFeatures` | probability → score |
| Citation classifier | TF-IDF + `LogisticRegression` | **active — this is the model already in production** | flat text string | `inference_text()`/`record_text()` reassembles task+title+author+url+claims into one string | TF-IDF → probability |
| Capsule compressor | regex/keyword rules, no ML | active | raw text + claims + reasons | rule-based extraction | `EvidenceCapsule` (compact DSL) |

The key design point: every model has its own narrow input contract built by a dedicated adapter
function (`build_features`, `feature_vector`, `inference_text`) — nothing downstream ever sees the
raw `{url, task}` pair directly except the Claude extractor. The codebase contains **two**
logistic-regression models, not one: the citation classifier (active, text-based, gates citation
eligibility) and the ranker logistic model (dormant, numeric-feature-based, would replace the
heuristic headline score once Terac pairwise training data exists).

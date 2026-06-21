# Captain Ddoski

**Credibility infrastructure for AI agents — finance domain.** A calling agent sends a single
`{url, task}` and Captain Ddoski returns a **trust score (0–100)**, a **USE / CAUTION / AVOID**
recommendation, **risk tags**, per-dimension **verdicts**, extracted **claims + evidence**, and a
compressed **Credibility Capsule** (reduces 800–1500 tokens of source context to a compact packet).
Exposed as a FastAPI endpoint *and* a FastMCP tool, so any MCP-capable agent can call it.

> **Operational boundary:** a supplied URL can be scored without API keys through the direct HTTP
> fallback. Live prompt-driven research is different: Firecrawl Search is required for discovery.
> When it is not configured, `/api/research` returns an explicit discovery error and never falls
> back to Bing, Browserbase, or another search provider.

## What's built

- **Engine** (`backend/app/`): pipeline `collector → extractor → features → ranker → capsule`.
  - Research discovery: Firecrawl Search only. Collection: Firecrawl Scrape with a direct HTTP
    fallback for a supplied source URL.
  - Extractor: **Claude** (Anthropic SDK) → heuristic fallback. Capsule: domain-specific
    **FinanceCredibilityCompressor** → extractive fallback.
  - Ranker: transparent **heuristic** baseline (per-feature contributions + verdicts).
- **MCP server** (`backend/mcp_server.py`): FastMCP stdio tool `captain_ddoski_score_source`.
- **Frontend** (`frontend/src/app/`): dark observability-console UI —
  **Dashboard** (`/`), **Research** (`/demo`), **Evaluation** (`/eval`), and **Threat Feed**
  (`/threats`).
- **Terac Arena is UI-only this build.** Pairs/labels persist to a local JSON store; the real
  Terac API/MCP + model training is a teammate's follow-up — see the `# TODO(terac):` notes in
  `backend/app/ml/trainer.py` and `terac_store.py`. The heuristic stays the active scorer.

## Train from Supabase labels

The labeled Supabase tasks train a separate claim/source **citation-usability** model. This is
intentionally separate from the URL-feature ranker: Supabase labels describe whether a particular
claim and its evidence can be used, not just whether a domain has strong URL-level signals.

Set these server-only values in `backend/.env` (the table and label column must match your
Supabase schema):

```dotenv
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_KEY=<anon-key-with-RLS-read-access-or-service-role-key>
SUPABASE_TABLE=sourceguard_tasks
SUPABASE_LABEL_COLUMN=would_ai_cite
```

Then install the backend requirements, export only rows with a recognized label, and train:

```bash
cd backend
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/pull_supabase_labels.py \
  --table sourceguard_tasks --label-column would_ai_cite
.venv/bin/python scripts/train_citation_classifier.py \
  --label-column would_ai_cite
```

The export is written to `backend/data/supabase_labeled_tasks.jsonl` and the versioned model bundle
to `backend/data/sourceguard_citation_classifier.joblib`. The training command prints held-out
accuracy, usable-class F1, and ROC-AUC. It refuses to train on fewer than 20 usable examples or a
one-class label set.

## Quick start

```bash
# Backend (http://localhost:8000, docs at /docs) — works with no .env
cd backend && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (http://localhost:3000)
cd frontend && cp .env.local.example .env.local && npm run dev

# MCP tool (optional) — engine must be running
cd backend && python mcp_server.py          # or: claude mcp add captain-ddoski -- python $(pwd)/mcp_server.py
```

`curl localhost:8000/api/health` reports which integrations are live, including
`research_discovery`. Copy `backend/.env.example` → `backend/.env` to add keys. Firecrawl is
required only for prompt-driven research discovery. Phoenix skills:
`npx skills add Arize-ai/phoenix --skill phoenix-tracing --skill phoenix-evals --skill phoenix-cli`.

## API surfaces

| Endpoint | Runtime path | Requirement | Notes |
|---|---|---|---|
| `POST /api/score-source` | Collect → extract → rank → capsule | A URL and task | Firecrawl is preferred; direct HTTP is the fallback. |
| `POST /api/research` | Firecrawl Search → score each source → evidence guard → synthesis | `FIRECRAWL_API_KEY` | Discovery is Firecrawl-only. `discovery_error` explains unavailable, failed, or empty discovery. |
| `POST /api/crawl` | Crawl supplied URLs → training payload | One or more URLs | Used for structured crawl output, not research discovery. |
| `GET /api/results`, `GET /api/threats` | Local score history | None | History is local JSON unless a deployment persistence layer is added. |
| `/api/demo-run`, `/api/eval`, `/api/terac/*` | Demo/evaluation surface | Varies | See the development plan before presenting these as production metrics. |

Run a live research request after setting `FIRECRAWL_API_KEY`:

```bash
curl -X POST http://localhost:8000/api/research \
  -H 'Content-Type: application/json' \
  -H 'X-Captain-Ddoski-Caller: local-smoke-test' \
  -d '{"prompt":"For a source-trust showcase, compare Nvidia’s latest earnings and investment outlook using its investor-relations materials, SEC filings, or Reuters reporting. Contrast them with promotional, anonymous, or guaranteed-return stock-pick claims. Cite only validated evidence and clearly reject weak sources.","max_sources":20}'
```

Expected behavior: `search_mode` is `firecrawl_search`, `discovered_count` is greater than zero,
and every cited source has a `USE` recommendation plus an eligible `citation_assessment`. If
discovery cannot run, the response contains
an empty source list plus `discovery_error`; it does not silently substitute a different provider.

See [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) for shipped capability, synthetic demo paths, and
the next implementation gates.

## Claude MCP demo

Captain Ddoski is registered as a local stdio MCP server named `captain-ddoski`.

```bash
# 1. Start the scoring engine.
cd backend
DEBUG=true .venv/bin/python -m uvicorn app.main:app --port 8000

# 2. Register the MCP server with Claude Code.
claude mcp add captain-ddoski -- \
  /absolute/path/to/backend/.venv/bin/python \
  /absolute/path/to/backend/mcp_server.py

# 3. Confirm it is connected.
claude mcp list

# 4. Run a deterministic test prompt.
claude -p "Use Captain Ddoski MCP to score https://best-stock-picks-now.com/double-your-money for this task: Research low-risk retirement investments. Return recommendation, score, and risk tags." \
  --allowedTools mcp__captain_ddoski__captain_ddoski_score_source
```

The backend terminal logs Claude-originated calls like:

```text
[Captain Ddoski] score_source caller=claude-mcp url=https://best-stock-picks-now.com/double-your-money task=Research low-risk retirement investments
```

The backend also records those calls in `GET /api/results` and grouped flagged domains in
`GET /api/threats`, so the frontend can hydrate dashboard/threat feed history from MCP calls.

---

## Scaffold reference

Fullstack hackathon starter — **Next.js** frontend + **Python (FastAPI)** backend, pre-wired
with a curated set of **Claude Code skills** and **MCP servers**.

## Layout

```
AIHackBerk/
├── frontend/              # Next.js 16 (App Router, TS, Tailwind v4, shadcn/ui)
│   ├── src/app/           # routes
│   ├── src/components/ui/ # shadcn components (button installed)
│   └── src/lib/utils.ts
├── backend/               # FastAPI
│   ├── app/main.py        # entrypoint (/ and /api/health)
│   ├── app/core/config.py # settings (.env-driven)
│   ├── app/{api,models,schemas,services}/
│   ├── .venv/             # virtualenv (deps installed)
│   └── requirements.txt
├── .mcp.json              # MCP servers: shadcn + 21st-dev Magic
├── .env.example           # MAGIC_21ST_API_KEY for the Magic MCP
└── .claude/
    ├── skills/            # 20 installed Claude skills (auto-activated)
    └── skill-sources/     # full upstream repos kept for reference
```

## Run it

**Backend** (http://localhost:8000, docs at `/docs`):
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

**Frontend** (http://localhost:3000):
```bash
cd frontend
cp .env.local.example .env.local
npm run dev
```

## Token Company challenge

Captain Ddoski includes a finance-focused compression demo for The Token Company challenge.
It turns long crawled source context into compact credibility capsules for finance AI agents,
preserving source URL, author, citations, dates, claims, risk tags, numbers, and institutions.

- API: `POST /api/compress`
- Demo: `http://localhost:3000/compress`
- Eval: `backend/.venv/bin/python backend/scripts/eval_compression.py`
- Claude API eval: `backend/.venv/bin/python backend/scripts/eval_claude_compression.py`

### The Token Company automatic compression evaluation

Set `TTC_API_KEY=ttc-...` in `backend/.env`. The existing async Anthropic
clients are wrapped automatically, so their `messages.create(...)` calls do not
change. Run the 30-query citation-task comparison with:

```bash
cd backend
.venv/bin/python scripts/eval_ttc_compression.py
```

Each run compares three variants: the raw prompt, the Captain Ddoski credibility
capsule, and The Token Company Bear-2 compression. It saves every input, Claude
output, real input token count, and quality metric to
`backend/data/compression_evaluations/`. The latest run is also available from
`GET /api/compress/evaluations/latest` for the `/compress` visualization.
Quality is measured against the uncompressed output using exact
citation-decision agreement, JSON validity, unigram F1, and precision/recall/F1
for critical numbers, URLs, and named entities.

### Latest benchmarks (real Claude API token counts)

| Benchmark | Original tokens | Compressed | Savings | Quality |
|-----------|----------------|------------|---------|---------|
| Short article, verbose task (worst case) | 275 | 218 | 20.7% | AVOID ✓ |
| **Long article (realistic), verbose task** | **655** | **206** | **68.5%** | AVOID ✓ |
| Long article + compact task (maximum) | 605 | 156 | **74.2%** | AVOID ✓ |
| Local eval set average (char/4 estimate) | — | — | 57.5% | 1.000 preservation |

Real articles are 300-500 words; the 400-word benchmark is representative of production traffic.
The capsule is the same 9-field structure regardless of source length — savings scale with article size.

**Finance credibility capsule** (example — 655 → 206 real Claude tokens):
```
url=best-stock-picks-now.com/double-your-money
ret=guaranteed 18%/yr
veh=private crypto yield fund
auth=Market Insider Team
date=2026-03-14
brand=Vanguard,Fidelity/no links
reg=SEC-safe/no SEC filing/FINRA BrokerCheck
sales=affiliate/urgent/limited-time
hist=never lost money/crashes
```

## Claude Code integration

### MCP servers (`.mcp.json`)
| Server | Purpose | Needs key? |
|--------|---------|-----------|
| `shadcn` | Browse/install shadcn/ui components via the registry | No |
| `magic`  | 21st.dev Magic — generate UI components from prompts (`/ui ...`) | Yes — set `MAGIC_21ST_API_KEY` |

To enable Magic: copy `.env.example` → `.env`, add your key from
https://21st.dev/magic/console, then restart Claude Code and run `/mcp` to confirm both are live.

### Skills (`.claude/skills/`)
Auto-activate when relevant. Installed (20):

- **Frontend / design** — `frontend-design`, `ui-ux-pro-max`, `design`, `design-system`,
  `ui-styling`, `brand`, `brand-guidelines`, `theme-factory`, `canvas-design`,
  `web-artifacts-builder`
- **Backend / data** — `senior-backend`, `api-design-reviewer`, `api-test-suite-builder`,
  `database-schema-designer`, `sql-database-assistant`, `secrets-vault-manager`
- **AI / tooling** — `claude-api`, `mcp-builder`, `skill-creator`, `webapp-testing`

Sources: [anthropics/skills](https://github.com/anthropics/skills),
[ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill),
[alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills).

## Next steps
Pick an idea, then build features into `frontend/src/app/` and `backend/app/api/`. The skills and
MCP servers above will assist automatically.

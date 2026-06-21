# AgentShield

**Credibility infrastructure for AI agents — finance domain.** A calling agent sends a single
`{url, task}` and AgentShield returns a **trust score (0–100)**, a **USE / CAUTION / AVOID**
recommendation, **risk tags**, per-dimension **verdicts**, extracted **claims + evidence**, and a
compressed **Credibility Capsule** (reduces 800–1500 tokens of source context to a compact packet).
Exposed as a FastAPI endpoint *and* a FastMCP tool, so any MCP-capable agent can call it.

> **Design principle:** graceful degradation. The app boots and returns a valid heuristic verdict
> with **zero API keys**. Each integration (Anthropic, Browserbase, Redis, Sentry, Phoenix, Terac)
> sits behind a `has_*` flag and falls back to an in-process path — the demo never hard-crashes.

## What's built

- **Engine** (`backend/app/`): pipeline `collector → extractor → features → ranker → capsule`.
  - Collector: Browserbase/Stagehand → automatic **httpx fallback**.
  - Extractor + Capsule: **Claude** (Anthropic SDK) → heuristic/extractive fallback.
  - Ranker: transparent **heuristic** baseline (per-feature contributions + verdicts).
- **MCP server** (`backend/mcp_server.py`): FastMCP stdio tool `agentshield_score_source`.
- **Frontend** (`frontend/src/app/`): dark observability-console UI —
  **Dashboard** (`/`), **Source Detail** (`/source/[id]`), **Terac Arena** (`/arena`).
- **Terac Arena is UI-only this build.** Pairs/labels persist to a local JSON store; the real
  Terac API/MCP + model training is a teammate's follow-up — see the `# TODO(terac):` notes in
  `backend/app/ml/trainer.py` and `terac_store.py`. The heuristic stays the active scorer.

## Quick start

```bash
# Backend (http://localhost:8000, docs at /docs) — works with no .env
cd backend && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (http://localhost:3000)
cd frontend && cp .env.local.example .env.local && npm run dev

# MCP tool (optional) — engine must be running
cd backend && python mcp_server.py          # or: claude mcp add agentshield -- python $(pwd)/mcp_server.py
```

`curl localhost:8000/api/health` reports which integrations are live. Copy `backend/.env.example`
→ `backend/.env` to add keys (all optional). Phoenix skills:
`npx skills add Arize-ai/phoenix --skill phoenix-tracing --skill phoenix-evals --skill phoenix-cli`.

## Claude MCP demo

AgentShield is registered as a local stdio MCP server named `agentshield`.

```bash
# 1. Start the scoring engine.
cd backend
DEBUG=true .venv/bin/python -m uvicorn app.main:app --port 8000

# 2. Register the MCP server with Claude Code.
claude mcp add agentshield -- \
  /absolute/path/to/backend/.venv/bin/python \
  /absolute/path/to/backend/mcp_server.py

# 3. Confirm it is connected.
claude mcp list

# 4. Run a deterministic test prompt.
claude -p "Use AgentShield MCP to score https://best-stock-picks-now.com/double-your-money for this task: Research low-risk retirement investments. Return recommendation, score, and risk tags." \
  --allowedTools mcp__agentshield__agentshield_score_source
```

The backend terminal logs Claude-originated calls like:

```text
[AgentShield] score_source caller=claude-mcp url=https://best-stock-picks-now.com/double-your-money task=Research low-risk retirement investments
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

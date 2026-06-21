# AIHackBerk

Fullstack hackathon starter — **Next.js** frontend + **Python (FastAPI)** backend, pre-wired
with a curated set of **Claude Code skills** and **MCP servers**. No app logic yet; this is the
scaffold to build on once you pick an idea.

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

AgentShield includes a finance-focused compression demo for The Token Company challenge.
It turns long crawled source context into compact credibility capsules for finance AI agents,
preserving source URL, author, citations, dates, claims, risk tags, numbers, and institutions.

- API: `POST /api/compress`
- Demo: `http://localhost:3000/compress`
- Eval: `backend/.venv/bin/python backend/scripts/eval_compression.py`
- Claude API eval: `backend/.venv/bin/python backend/scripts/eval_claude_compression.py`

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

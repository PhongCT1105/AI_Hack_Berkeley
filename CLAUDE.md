# Captain America engineering guide

## Product boundary

Captain America is finance-source credibility infrastructure for AI agents. The product has three
separate surfaces that must not be presented as the same thing:

- `POST /api/score-source` evaluates a supplied source URL through the real collection and
  ranking pipeline. It can use a direct HTTP fallback if Firecrawl is unavailable.
- `POST /api/research` is live, prompt-driven research. It requires Firecrawl Search for source
  discovery, then scores each discovered URL before citation. It must report a discovery error
  instead of silently using another search provider.
- `/api/demo-run`, `/api/eval`, and `/api/terac/*` include synthetic or local-only paths. Keep
  their UI copy and documentation explicit until the real evaluation and annotation loops ship.

Frontend: Next.js 16 (App Router, TypeScript, Tailwind v4, shadcn/ui) in `frontend/`.
Backend: FastAPI in `backend/` (venv at `backend/.venv`).

## Conventions
- **Frontend**: App Router under `frontend/src/app/`. UI components via shadcn/ui in
  `src/components/ui/`. Add components with `npx shadcn@latest add <name>` (or the `shadcn` MCP).
  Import alias is `@/*`.
- **Backend**: Add routers under `backend/app/api/` and mount them in `app/main.py`. Pydantic
  schemas in `app/schemas/`, models in `app/models/`, business logic in `app/services/`.
  Settings come from `app/core/config.py` (reads `.env`). Run with the venv's interpreter.
- **Branding**: use `Captain America` for product-facing copy, `captain_america` for new internal
  identifiers, and `CAPTAIN_AMERICA_*` for new environment variables. The legacy
  `X-AgentShield-Caller` header and `AGENTSHIELD_*` MCP variables exist only for migration.
- **Secrets**: never commit `.env` / `.env.local`. Templates are the `.example` files.

## MCP & skills
- `.mcp.json` defines the `shadcn` and `magic` (21st.dev) MCP servers. Magic needs
  `MAGIC_21ST_API_KEY` in the root `.env`.
- Skills in `.claude/skills/` auto-activate. Lean on `frontend-design` / `ui-ux-pro-max` for UI,
  `senior-backend` / `api-design-reviewer` for API work, `claude-api` for Anthropic integration.

## Commands
- Backend dev: `cd backend && source .venv/bin/activate && uvicorn app.main:app --reload`
- Backend tests: `cd backend && .venv/bin/python -m unittest discover -s tests -v`
- Frontend dev: `cd frontend && npm run dev`
- Frontend lint/build: `npm run lint` / `npm run build`

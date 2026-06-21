# Optional future: source-pair comparison Terac opportunity

This optional future Browserbase-oriented flow is the source-pair-comparison annotation flow at `/annotate/pairs`
(compare two web sources for one research task). A separate single-claim
flow lives at `/annotate` — see `docs/TERAC_LAUNCH.md` for that one.

## 1. Install the Terac MCP server

```bash
claude mcp add --transport http terac https://terac.com/api/mcp
```

Then run `/mcp` inside Claude Code and authenticate.

## 2. Confirm the tools are available

Expected tools: `terac_list_opportunities`, `terac_create_quote`,
`terac_launch_opportunity`, `terac_get_submissions`, `terac_get_context`,
`terac_pause_opportunity`. If unavailable, use the manual flow in section 4 —
the app stores labels in Supabase regardless of how the opportunity launched.

## 3. MCP-assisted launch (get a quote before launching)

1. Deploy the app and confirm `/annotate/pairs` loads a source pair.
2. Ask Claude to call `terac_create_quote` with:
   - **Task title**: Source credibility comparison for AI agent training
   - **Audience**: general population
   - **Task type**: web annotation / preference labeling
   - **Estimated time**: 45–90 seconds per task
   - **Desired labels**: 3 labels per pair
   - **Budget**: fit within hackathon credit
   - **Annotation URL**: `https://<your-deployment>/annotate/pairs`
   - **Instructions**: copy the annotator instructions shown below.
3. Review the quote. Only call `terac_launch_opportunity` after confirming it
   fits the budget.
4. Poll `terac_get_submissions`, or just check `/admin` — annotators write
   directly to Supabase via `/api/pairs/submit`.

`POST /api/terac/prepare-pairs` (with the admin password) returns a ready-made
JSON payload for the quote request.

## 4. Manual fallback (no MCP tools available)

Create the opportunity by hand at https://terac.com with the same settings as
above, pointing `Annotation URL` at `/annotate/pairs`.

## Annotator instructions (copy verbatim)

> You are helping train an AI agent to choose trustworthy financial sources.
> Given a research task and two web sources, choose which source an AI agent
> should trust or cite. You are not being asked to give financial advice or
> decide whether an investment is good. Focus on source quality: evidence,
> transparency, citations, promotional pressure, and whether the page is
> appropriate for an AI agent to cite.

## After labeling

- `/admin` — label counts, distributions, machine-vs-human agreement.
- `/api/export?password=<ADMIN_PASSWORD>` (or the Export CSV button in
  `/admin`) — training data.
- `ml/README.md` — turning the export into a held-out evaluation.

# Captain Ddoski Finance: Supabase and deployment handoff

## Annotation flow (current)

`/annotate` is the simplified Terac flow: no login, one random claim/evidence
question at a time. Annotators answer "Can an AI financial research agent cite
this claim?" with Yes/No plus an optional one-sentence reason. Training input
is `claim` + `evidence_text_clean`; label output is `can_ai_cite` (yes/no) and
`reason`.

Public task fields: task_id, task_type, research_task, claim, author,
posted_date, source, evidence_text, evidence_text_clean, evidence_url,
image_url, capsule.

Do not add original Fin-Fact labels, verdicts, justifications, explanations,
classifications, visual-bias labels, or issue fields to source_claim_tasks.

`/annotate/pairs` (source-pair comparison) is an optional, unused-for-now flow
kept for future Browserbase-style work; it does not need any of the steps
below.

## One-time database setup

1. Create a Supabase project (or reuse the existing one).
2. Run `supabase/schema.sql` in the SQL editor. It's additive/idempotent
   (`if not exists` / `add column if not exists`), safe to re-run any time.
3. Configure these on the deployment host (see `.env.example`):
   `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`,
   `SUPABASE_SERVICE_ROLE_KEY`, `NEXT_PUBLIC_APP_URL`, `ADMIN_PASSWORD`, and
   optionally `TARGET_LABELS_PER_TASK` (defaults to 3).

The service-role key is server-only. Never use a `NEXT_PUBLIC_` prefix for it.

## Generate the seed dataset

Fin-Fact (`amanrangapur/Fin-Fact` on Hugging Face) is a general fact-checking
dataset, not finance-only, so the script filters claims to ones that actually
mention a finance term (tax, stock, market, earnings, debt, etc.) before
emitting tasks. It also builds `evidence_text_clean` (bullet-extracted from
JSON evidence, href arrays stripped, capped at 1200 characters) so the
annotation page never has to render raw evidence JSON.

From the repository root, run:

    python3 scripts/prepare_finfact_for_terac.py --limit 200

The Hugging Face datasets-server API caps rows-per-request at 100, so the
script pages through the full ~3,300-row dataset to find enough
finance-related claims — expect this to take roughly 30-60 seconds.

If Hugging Face is unavailable, download an official Fin-Fact export and run:

    python3 scripts/prepare_finfact_for_terac.py --input /path/to/finfact.jsonl --limit 200

This generates `data/captain_ddoski_terac_tasks.jsonl` and `.csv` for public
annotation plus `hidden_original_labels.csv` for admin-only sanity checks.
Never upload, display, or train on the hidden-label file.

## Seed Supabase

The seed script loads `.env.local` when it exists; otherwise export
the Supabase variables in the shell. Then run:

    npx tsx scripts/seed_terac_tasks_to_supabase.ts

The seed script upserts only public task fields into `source_claim_tasks`
using `task_id` as the conflict key. It never reads
`hidden_original_labels.csv`.

To fully replace an existing seeded set (e.g. swapping in a re-filtered
dataset), delete the old rows first — `source_claim_tasks` cascades to
`simple_claim_annotations` and `claim_annotations` on delete, so this also
clears any labels collected against the old tasks:

    curl -X DELETE "$NEXT_PUBLIC_SUPABASE_URL/rest/v1/source_claim_tasks?task_id=not.is.null" \
      -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
      -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"

## Deploy and verify

1. Deploy the repo root as the Next.js app (e.g. Vercel) and configure the
   same environment variables.
2. Visit `/annotate` and confirm one question loads with no login.
3. Click Yes or No, confirm "Saved. Loading next question..." and that a new
   question loads automatically.
4. Confirm a row appears in `simple_claim_annotations` in Supabase.
5. Hit `GET /api/progress` and confirm `total_labels_collected` incremented.
6. Hit `GET /api/export` with `x-admin-password: <ADMIN_PASSWORD>` and confirm
   the CSV starts with `task_id,claim,evidence_text_clean,can_ai_cite,reason,created_at`.
   (Pass the password via header, not a query string — it may contain `+`/`/`
   characters that need URL-encoding in a query param.)

Target Terac setup: Captain Ddoski Finance Claim Credibility Labeling; general
population; 20-45 seconds per item; three labels per task
(`TARGET_LABELS_PER_TASK`). Only labels in `simple_claim_annotations` belong
in the Terac-track training story (`claim` + `evidence_text_clean` ->
`can_ai_cite`).

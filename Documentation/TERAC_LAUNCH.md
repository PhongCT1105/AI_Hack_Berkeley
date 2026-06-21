# Launch Captain Ddoski Finance on Terac

This workspace does not have Terac MCP tools configured, so it cannot launch an
opportunity directly. The app exposes a prepared payload at
`POST /api/terac/prepare` (admin-authenticated).

Use the following opportunity settings when Terac MCP is connected:

- Title: **Captain Ddoski Finance Claim Credibility Labeling**
- Audience: general population
- Estimated time: 45-90 seconds per item
- Desired labels per task: 3
- Annotation URL: `https://<deployment>/annotate`
- Instruction: judge source quality and whether an AI can cite the claim; do
  not provide financial advice.

Review the quote before launching. The annotation page writes labels directly
to Supabase's `claim_annotations` table; any Terac submission export is
secondary to that system of record.

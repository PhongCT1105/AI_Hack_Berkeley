# Captain Ddoski: agent knowledge base

## Purpose and boundary

Captain Ddoski is credibility infrastructure for AI agents. Before an agent scrapes, cites, or reasons from a web page, it calls Captain Ddoski with a URL and a task. The service returns a recommendation, trust score, compact evidence, and risk signals.

This is not a generic fake-news detector. It helps a downstream agent decide whether a specific page is suitable for a specific task. A source can be credible in one context and inappropriate in another.

## Non-negotiable MVP

The scoped product must work for roughly 10-25 demonstration URLs and 2-3 research tasks. The required end-to-end path is:

```text
URL + task -> browser trace or saved fixture -> feature extraction
          -> trust score + recommendation -> Credibility Capsule -> UI/API
```

Required output: trust score (0-100); `use`, `use_with_caution`, or `avoid`; risk tags; detected source type; a task-aware Credibility Capsule; and raw versus capsule token counts.

Keep multi-hop crawling, browser extensions, source graphs, advanced RLHF, and a marketplace listing out of the critical path.

## API contract

### `POST /api/score-source`

```json
{
  "url": "https://example.com/article",
  "task": "Should a research agent cite this for medical advice?",
  "mode": "live_or_fixture"
}
```

```json
{
  "url": "https://example.com/article",
  "trust_score": 82,
  "recommendation": "use_with_caution",
  "risk_tags": ["opinion", "secondary_source"],
  "source_type": "news_article",
  "model_version": "heuristic_v1",
  "token_stats": {"raw_tokens": 18420, "capsule_tokens": 1240, "compression_ratio": 0.933},
  "credibility_capsule": {},
  "trace_id": "optional-observability-trace-id"
}
```

Delivery order for follow-on endpoints: `GET /api/evals`, `POST /api/filter-sources`, `POST /api/compress-source`, then `POST /api/terac/webhook`. Claim verification is not an MVP dependency.

## Collection and fixtures

The collector is deterministic. Start from a fixed extraction recipe; use agentic browser actions only to handle consent banners or dynamic pages.

Persist these fields where available: URL, final URL, title, visible text, screenshot path/URL, headings, outbound links, author candidates, date candidates, citation links, ad/popup markers, redirect count, fetch timestamp, and extraction errors.

Every live path needs fixture mode with the same response schema. Save title, text, screenshot, and metadata for at least 15 known demo pages. Fixture mode is a reliability feature, not mock-only UI behavior.

## Credibility features and baseline

| Feature | Signal |
| --- | --- |
| Author transparency | Named author, accountable organization, or clear metadata |
| Citation quality | Primary/official links and support for major claims |
| Task fit | Page topic matches the downstream task |
| Sensational language | Clickbait terms, absolute promises, or manipulative wording |
| Ad/affiliate density | Monetization pressure or repeated affiliate links |
| Source type | Primary, academic, government, news, blog, forum, review, unknown |
| Recency | Published/updated date is present and appropriate for the task |

Initial transparent baseline:

```text
18 * author_present + 20 * primary_source_or_official + 15 * citation_quality
+ 10 * task_relevance + 7 * recency_ok - 15 * sensational_language
- 12 * excessive_ads_or_affiliate - 10 * missing_date - 15 * unsupported_major_claims
```

Use `>= 75` for `use`, `50-74` for `use_with_caution`, and `< 50` for `avoid` unless calibration against real labels supports different thresholds.

## Terac labeling and model improvement

The Terac track requires data collected during the hackathon through Terac to demonstrate improvement. Public examples may seed cases, but do not substitute for that training/evaluation story.

Annotation unit: show two sources for a stated task. Ask general-population annotators which source an AI may cite (`A`, `B`, both, neither); which has clearer evidence; which feels more manipulative; whether each clearly identifies an author/organization; what caused distrust; and whether the capsule supports the same decision.

Training baseline: compute `features(A) - features(B)` and train a logistic-regression pairwise classifier to predict the human-preferred source. Convert pairwise probabilities into a source score. Split labeled pairs before model selection and report results only on held-out pairs.

| Metric | Report |
| --- | --- |
| Labeled pairs | Count and train/held-out split (target 30-80, 70/30) |
| Baseline preference match | Held-out accuracy |
| Terac-trained preference match | Held-out accuracy using the same split |
| Cite/avoid precision | Precision among blocked pages |
| Token reduction | `1 - capsule_tokens / raw_tokens` |
| Recommendation preservation | Full-trace vs capsule decision agreement |
| Reliability | Crawl success rate and latency from real traces |

## Credibility Capsule

The capsule is task-aware compression, not generic summarization. Preserve the minimum evidence a downstream agent needs to decide whether to use a source; remove navigation, duplicated prose, cookie text, scripts, and irrelevant links.

```json
{
  "task": "Should an AI agent cite this page for health advice?",
  "source_identity": {"url": "...", "title": "...", "publisher_or_org": "...", "author": "present|missing|unclear", "date": "..."},
  "main_claims": [{"claim": "...", "support_status": "supported|unsupported|unclear", "evidence": "..."}],
  "credibility_signals": {
    "source_type": "government|academic|news|blog|forum|affiliate|unknown",
    "citation_quality": "strong|medium|weak|none",
    "task_relevance": "high|medium|low",
    "clickbait_or_manipulation": "low|medium|high",
    "ad_or_affiliate_pressure": "low|medium|high"
  },
  "human_feedback": {"terac_preference": "preferred|rejected|not_labeled", "human_reason": "..."},
  "recommendation": "use|use_with_caution|avoid",
  "trust_score": 0
}
```

## Sponsor alignment and observability

- **Terac:** Human comparison data and a usable annotation arena; evaluation improvement is the central proof.
- **The Token Company:** Measure task-aware context compression and decision preservation, not just shorter output.
- **Browserbase/Stagehand:** Capture a real browser trace, screenshot, text, metadata, and redirects; use fixtures when live collection fails.
- **Sentry:** Capture real API errors, latency, and crawl failure diagnostics.
- **Arize/Phoenix:** Trace agent runs and evaluation records when time permits.
- **Redis:** Cache URL traces and source features to avoid repeat crawling.
- **Fetch/Agentverse:** Optional callable wrapper that demonstrates another agent invoking `score_source`.

Only state that an integration is present if it is actually configured and shown in the running product or an exported trace.

## Demo and delivery rules

Start with contrast: a research agent would cite a weak page; with Captain Ddoski, it receives a source decision and evidence capsule first. Then show the trace, capsule/token reduction, annotation arena, before/after evaluation, and reliability evidence.

By hour 6, the vertical slice must work. If it does not, cut scope rather than adding integrations. Before judging, run 10 fixed demo cases, test on the deployment, retain a local fixture flow, and record a backup walkthrough.

## Source materials

This working brief consolidates the supplied Captain Ddoski playbook, Terac guide, hacker guide, Sentry starter pack, and Token Company brief. The original files remain in Downloads; this repository does not copy them, so this document is the project-local reference.

"use client";

import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Loader2, Scale, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { NarrativeBlock } from "@/components/workflow-transcript";
import { recTone, scoreColor } from "@/lib/score-ui";
import { cn } from "@/lib/utils";
import type { ComparisonEvent, ComparisonSide, ComparisonSummary } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const DEFAULT_PROMPT =
  "Research Nvidia's financial outlook using a broad mix of investor-relations materials, SEC filings, " +
  "financial news, and analyst commentary — including some promotional or anonymous stock-pick content — " +
  "so credibility differences between sources are visible.";

interface ComparisonRow {
  url: string;
  domain: string;
  weak: ComparisonSide;
  better: ComparisonSide;
}

export default function ComparePage() {
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [maxSources, setMaxSources] = useState(4);
  const [running, setRunning] = useState(false);
  const [narratives, setNarratives] = useState<string[]>([]);
  const [rows, setRows] = useState<ComparisonRow[]>([]);
  const [summary, setSummary] = useState<ComparisonSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [rows, narratives]);

  useEffect(() => () => sourceRef.current?.close(), []);

  function run() {
    sourceRef.current?.close();
    setError(null);
    setSummary(null);
    setRows([]);
    setNarratives([]);
    setRunning(true);

    const url = `${API_URL}/api/comparison/stream?prompt=${encodeURIComponent(prompt.trim())}&max_sources=${maxSources}`;
    const source = new EventSource(url);
    sourceRef.current = source;

    source.onmessage = (message) => {
      const event = JSON.parse(message.data) as ComparisonEvent;
      if (event.type === "done") {
        source.close();
        setRunning(false);
        return;
      }
      if (event.type === "narrative") {
        setNarratives((prev) => [...prev, event.text]);
      } else if (event.type === "row") {
        setRows((prev) => [...prev, { url: event.url, domain: event.domain, weak: event.weak, better: event.better }]);
      } else if (event.type === "summary") {
        setSummary(event.output);
      }
    };

    source.onerror = () => {
      source.close();
      setRunning(false);
      setError("The comparison stream was interrupted. Is the backend running?");
    };
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-7 sm:px-6 sm:py-10">
      <section className="mb-8 max-w-3xl">
        <div className="mb-3 inline-flex items-center gap-2 rounded border border-primary/20 bg-secondary px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-primary">
          <Scale className="size-3.5" /> Pipeline comparison
        </div>
        <h1 className="text-3xl font-bold tracking-tight">Weak baseline vs. our full pipeline.</h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Same fetched page, two pipelines. <strong className="text-foreground">Weak</strong> ranks with the plain
          heuristic and sends the raw, uncompressed page to Claude. <strong className="text-foreground">Better</strong>{" "}
          compresses that same call with TTC, builds our domain-specific evidence capsule, and — when enough Terac
          labels exist — ranks with a freshly-fit candidate model instead of the heuristic. Every number below is a
          real call, including the actual Anthropic-billed input/output tokens for each side.
        </p>
      </section>

      <Card className="glass-panel">
        <CardContent className="pt-5">
          <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            What do you want to research?
          </label>
          <textarea
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            rows={3}
            className="w-full resize-none rounded border border-border bg-card p-3 text-sm leading-6 outline-none focus:border-primary focus:ring-2 focus:ring-primary/15"
          />
          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              Compare up to
              <select
                value={maxSources}
                onChange={(event) => setMaxSources(Number(event.target.value))}
                className="rounded border border-border bg-card px-2 py-1 text-foreground"
              >
                <option value={2}>2 sources</option>
                <option value={4}>4 sources</option>
                <option value={6}>6 sources</option>
              </select>
            </label>
            <button
              onClick={run}
              disabled={running || prompt.trim().length < 3}
              className="inline-flex h-10 items-center justify-center gap-2 rounded bg-primary px-5 text-sm font-semibold text-primary-foreground active:translate-y-px disabled:opacity-50"
            >
              {running ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              {running ? "Comparing" : "Run comparison"}
            </button>
          </div>
          {error && (
            <p className="mt-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p>
          )}
        </CardContent>
      </Card>

      {narratives.length > 0 && (
        <Card className="mt-5">
          <CardContent className="pt-5">
            {narratives.map((text, i) => (
              <NarrativeBlock key={i} text={text} />
            ))}
            {running && rows.length === 0 && (
              <div className="flex items-center gap-2 py-2 text-xs text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" /> Working…
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {rows.length > 0 && (
        <div className="mt-5 grid grid-cols-1 gap-3 lg:grid-cols-2">
          <div className="px-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Weak — heuristic ranker, no compression
          </div>
          <div className="px-1 text-[11px] font-semibold uppercase tracking-wide text-primary">
            Better — TTC compression + capsule + candidate model
          </div>
          {rows.map((row) => (
            <RowPair key={row.url} row={row} />
          ))}
        </div>
      )}

      {running && rows.length > 0 && (
        <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin" /> Scoring next source…
        </div>
      )}

      <div ref={endRef} />

      {summary && <SummaryPanel summary={summary} />}
    </div>
  );
}

// These signals are still scored on the backend; we just don't surface them
// as standalone badges here since they read as noise on the comparison card.
const HIDDEN_RISK_TAGS = new Set(["no author", "no citations", "insecure transport"]);

function visibleRiskTags(tags: string[]): string[] {
  return tags.filter((tag) => !HIDDEN_RISK_TAGS.has(tag));
}

function RowPair({ row }: { row: ComparisonRow }) {
  const disagree = row.weak.recommendation !== row.better.recommendation;
  return (
    <>
      <SideCard url={row.url} domain={row.domain} side={row.weak} tone="weak" flagged={disagree} />
      <SideCard url={row.url} domain={row.domain} side={row.better} tone="better" flagged={disagree} />
    </>
  );
}

function SideCard({
  url,
  domain,
  side,
  tone,
  flagged,
}: {
  url: string;
  domain: string;
  side: ComparisonSide;
  tone: "weak" | "better";
  flagged: boolean;
}) {
  return (
    <Card
      className={cn(
        "border-l-2",
        tone === "weak" ? "border-l-slate-300" : "border-l-primary/40",
        flagged && "ring-1 ring-amber-300",
      )}
    >
      <CardContent className="pt-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <a href={url} target="_blank" rel="noreferrer" className="truncate text-sm font-semibold hover:underline">
              {domain}
            </a>
            <p className="text-[11px] text-muted-foreground">{side.scorer_mode}</p>
          </div>
          <div className="flex items-center gap-2">
            <Badge tone={recTone(side.recommendation)}>{side.recommendation}</Badge>
            <span className={cn("text-lg font-bold tabular-nums", scoreColor(side.trust_score))}>{side.trust_score}</span>
          </div>
        </div>

        {visibleRiskTags(side.risk_tags).length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {visibleRiskTags(side.risk_tags).map((tag) => (
              <span key={tag} className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                {tag}
              </span>
            ))}
          </div>
        )}

        <p className="mt-2 line-clamp-3 text-xs leading-5 text-muted-foreground">{side.evidence_preview}</p>

        <div className="mt-3 flex flex-wrap items-center gap-2 text-[10px] text-muted-foreground">
          <span className="rounded bg-card px-2 py-1">
            tokens in/out: <strong className="text-foreground">{side.input_tokens}</strong> /{" "}
            <strong className="text-foreground">{side.output_tokens}</strong>
          </span>
          <span className="rounded bg-card px-2 py-1">{side.evidence_chars} evidence chars</span>
          <span className="rounded bg-card px-2 py-1">{side.latency_ms}ms</span>
          {side.compression && (
            <span className="rounded bg-teal-50 px-2 py-1 text-teal-700">
              TTC saved {side.compression.total_tokens_saved} tok ({side.compression.compression_ratio.toFixed(2)}x)
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function SummaryPanel({ summary }: { summary: ComparisonSummary }) {
  const weakTotal = summary.weak_total_tokens;
  const betterTotal = summary.better_total_tokens;
  const pct = weakTotal > 0 ? Math.round((summary.tokens_saved / weakTotal) * 100) : 0;
  const cm = summary.candidate_model;

  return (
    <Card className="mt-6 border-primary/20 bg-primary/5">
      <CardContent className="pt-5">
        <h2 className="flex items-center gap-2 text-lg font-bold">
          <Scale className="size-4 text-primary" /> Comparison summary
        </h2>

        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <Stat label="Sources compared" value={String(summary.sources_compared)} />
          <Stat label="Weak — total tokens" value={weakTotal.toLocaleString()} sub={`${summary.totals.weak_input_tokens} in / ${summary.totals.weak_output_tokens} out`} />
          <Stat label="Better — total tokens" value={betterTotal.toLocaleString()} sub={`${summary.totals.better_input_tokens} in / ${summary.totals.better_output_tokens} out`} />
        </div>

        <p className="mt-4 text-sm">
          {summary.tokens_saved >= 0 ? (
            <>
              The compressed pipeline used <strong className="text-emerald-700">{summary.tokens_saved.toLocaleString()} fewer tokens</strong>{" "}
              ({pct}% less) across {summary.sources_compared} sources than the uncompressed baseline.
            </>
          ) : (
            <>
              The compressed pipeline used <strong className="text-red-700">{Math.abs(summary.tokens_saved).toLocaleString()} more tokens</strong>{" "}
              than the uncompressed baseline on this run.
            </>
          )}
        </p>

        <div className="mt-4 rounded border border-border bg-card p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Candidate model (better side)</p>
          {cm.holdout_accuracy !== undefined ? (
            <p className="mt-1 text-sm">
              Holdout accuracy <strong>{cm.holdout_accuracy}</strong> vs. heuristic baseline{" "}
              <strong>{cm.baseline_accuracy}</strong> (n_holdout={cm.holdout_size}, n_labels={cm.n_labels_used}).{" "}
              {cm.beats_baseline ? (
                <span className="text-emerald-700">Beats the heuristic — this is what production would promote.</span>
              ) : (
                <span className="text-amber-700">Has not proven improvement yet — production keeps the heuristic active.</span>
              )}
            </p>
          ) : (
            <p className="mt-1 text-sm text-muted-foreground">{cm.note ?? "Not enough Terac labels to fit a candidate model yet."}</p>
          )}
        </div>

        {summary.disagreements.length > 0 && (
          <div className="mt-4">
            <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-amber-700">
              <AlertTriangle className="size-3.5" /> Disagreements ({summary.disagreements.length})
            </p>
            <div className="mt-2 space-y-1.5">
              {summary.disagreements.map((d) => (
                <div key={d.url} className="flex items-center justify-between gap-3 rounded bg-amber-50 px-3 py-1.5 text-xs">
                  <span className="truncate font-medium">{d.domain}</span>
                  <span className="shrink-0 text-muted-foreground">
                    weak: <strong>{d.weak}</strong> → better: <strong>{d.better}</strong>
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {summary.discovery_error && (
          <p className="mt-4 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            Discovery issue: {summary.discovery_error}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded border border-border bg-card p-3">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="text-xl font-bold tabular-nums">{value}</p>
      {sub && <p className="text-[10px] text-muted-foreground">{sub}</p>}
    </div>
  );
}

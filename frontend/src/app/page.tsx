"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  CirclePause,
  Download,
} from "lucide-react";
import { ComicBadge } from "@/components/comic/comic-badge";
import { ComicPageHeader } from "@/components/comic/comic-page-header";
import { McpInstall } from "@/components/comic/mcp-install";
import { Card, CardContent } from "@/components/ui/card";
import { getSystemHealth, useResults, type SentryIssue } from "@/lib/api";
import type { Recommendation, ScoreResponse } from "@/lib/types";

const SENTRY_ORG_SLUG = "worcester-polytechnic-insti-6p";

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

const FALLBACK_FEED = [
  { domain: "investor.nvidia.com", score: 96, kind: "USE" as const, note: "Official investor relations portal" },
  { domain: "sec.gov/edgar/filings", score: 98, kind: "USE" as const, note: "Primary regulatory filing" },
  { domain: "bloomberg.com/news", score: 78, kind: "CAUTION" as const, note: "Secondary reporting, review context" },
  { domain: "stock-hype-blog.io/moon", score: 24, kind: "AVOID" as const, note: "Promotion pattern and weak sourcing" },
];

const statusMeta: Record<Recommendation, { label: string; className: string; line: string }> = {
  USE: { label: "Cite", className: "bg-primary/15 text-indigo-200", line: "border-primary/50" },
  CAUTION: { label: "Review", className: "bg-amber-400/15 text-amber-200", line: "border-amber-400/60" },
  AVOID: { label: "Block", className: "bg-red-400/15 text-red-200", line: "border-red-400/60" },
};

function domain(result: ScoreResponse) {
  return result.domain.replace(/^www\./, "") || new URL(result.url).hostname;
}

function formatTime(index: number) {
  // This is display-only console data. Keep it deterministic so the server and
  // client render the same initial HTML during hydration.
  const totalSeconds = 12 * 60 * 60 + 4 * 60 + 20 - index * 34;
  const hours = Math.floor(totalSeconds / 3600).toString().padStart(2, "0");
  const minutes = Math.floor((totalSeconds % 3600) / 60).toString().padStart(2, "0");
  const seconds = (totalSeconds % 60).toString().padStart(2, "0");
  return `${hours}:${minutes}:${seconds}`;
}

export default function MonitorPage() {
  const results = useResults();
  const [paused, setPaused] = useState(false);
  const [health, setHealth] = useState<{ configured: boolean; issues: SentryIssue[] } | null>(null);

  useEffect(() => {
    void getSystemHealth().then(setHealth);
  }, []);

  const visibleResults = useMemo(() => results.slice(0, 6), [results]);
  const feed = visibleResults.length ? visibleResults : FALLBACK_FEED;
  const blocked = results.filter((result) => result.recommendation === "AVOID");
  const averageTrust = results.length
    ? Math.round(results.reduce((sum, result) => sum + result.trust_score, 0) / results.length)
    : 74;
  const averageReduction = results.length
    ? Math.round(results.reduce((sum, result) => sum + (1 - result.evidence_capsule.token_estimate_after / Math.max(result.evidence_capsule.token_estimate_before, 1)) * 100, 0) / results.length)
    : 94.1;
  const reasonCounts = ["unsupported prediction", "weak citations", "policy violation", "domain blacklist"].map((reason, index) => ({
    reason,
    count: blocked.filter((result) => result.risk_tags.some((tag) => tag.toLowerCase().replaceAll("_", " ").includes(reason.split(" ")[0]))).length || (results.length ? 0 : [42, 28, 15, 15][index]),
  }));
  const reasonTotal = Math.max(reasonCounts.reduce((sum, item) => sum + item.count, 0), 1);

  return (
    <div>
      <section className="comic-zone border-b-[3px] border-(--comic-ink) px-4 py-12 sm:px-6 sm:py-16">
        <div className="mx-auto grid max-w-7xl items-center gap-10 lg:grid-cols-2">
          <div>
            <span className="comic-pop mb-4 bg-(--comic-yellow) px-3 py-1.5 text-[11px] text-(--comic-ink)">
              Source trust infrastructure for AI agents
            </span>
            <h1 className="font-comic text-5xl leading-[1.05] text-(--comic-ink) sm:text-6xl">
              Captain Ddoski
            </h1>
            <p className="mt-3 max-w-md text-base leading-7 font-semibold text-(--comic-ink)/80">
              Validates every finance source before an agent cites it &mdash; scoring credibility,
              blocking the junk, and keeping a live trail of receipts.
            </p>
            <div className="mt-6 flex flex-wrap items-center gap-3">
              <Link
                href="/demo"
                className="comic-pop bg-(--comic-red) px-5 py-3 text-sm text-white"
              >
                Run Shield <ArrowRight className="ml-1.5 inline size-4" />
              </Link>
              <Link
                href="/threats"
                className="comic-pop bg-white px-5 py-3 text-sm text-(--comic-ink)"
              >
                Review Threat Feed
              </Link>
            </div>
          </div>
          <div className="comic-panel comic-panel-tilt overflow-hidden">
            <video
              className="aspect-video w-full object-cover"
              src="/Captain_Ddoski_video.mp4"
              autoPlay
              muted
              loop
              playsInline
              controls
            />
          </div>
        </div>
        <div className="mx-auto mt-10 max-w-7xl">
          <McpInstall />
        </div>
      </section>

      <div className="mx-auto max-w-7xl px-4 py-7 sm:px-6 sm:py-10">
        <ComicPageHeader
          title="Live Monitor"
          subtitle="Observe source checks, blocked citations, and model behavior in real time."
          pose="protect"
          bg="var(--comic-blue)"
          light
          right={<ComicBadge tone="green">System stable</ComicBadge>}
        />

      <section className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Metric label="Sources checked" value={results.length || "1,284"} detail="↑ 12%" />
        <Metric label="Blocked" value={blocked.length || "312"} detail="Shield active" tone="danger" />
        <Metric label="Avg trust" value={averageTrust} detail="Session score" bar={averageTrust} />
        <Metric label="Avg reduction" value={`${averageReduction}%`} detail="Hallucination mitigation" />
        <Metric label="Latency" value="420ms" detail="P99 performance" />
        <Metric label="Error rate" value="0.8%" detail="Nominal" tone="warning" />
      </section>

      <section className="grid gap-5 lg:grid-cols-12">
        <div className="space-y-3 lg:col-span-8">
          <div className="flex items-center justify-between gap-3">
            <h2 className="flex items-center gap-2 text-lg font-bold tracking-tight text-foreground">
              Live source checks <span className="size-2 rounded-full bg-primary pulse-dot" />
            </h2>
            <div className="flex gap-2">
              <button onClick={() => setPaused((value) => !value)} className="inline-flex h-8 items-center gap-1.5 rounded border border-border bg-secondary px-2.5 text-[10px] font-semibold uppercase tracking-wide text-secondary-foreground active:translate-y-px">
                <CirclePause className="size-3" /> {paused ? "Resume" : "Pause"}
              </button>
              <button className="inline-flex h-8 items-center gap-1.5 rounded border border-border bg-secondary px-2.5 text-[10px] font-semibold uppercase tracking-wide text-secondary-foreground active:translate-y-px">
                <Download className="size-3" /> Export
              </button>
            </div>
          </div>

          <div className="overflow-hidden rounded-lg border border-slate-800 bg-slate-950 shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-800 bg-slate-900/80 px-4 py-2 font-mono text-[10px] text-slate-400">
              <span>SESSION_ID: TRACE_9921_X</span><span>KERNEL_0.4.1</span>
            </div>
            <div className="max-h-[390px] min-h-[312px] space-y-4 overflow-auto p-4 font-mono text-xs">
              {feed.map((item, index) => {
                const info = "recommendation" in item ? statusMeta[item.recommendation] : statusMeta[item.kind];
                const itemDomain = "recommendation" in item ? domain(item) : item.domain;
                const score = "recommendation" in item ? item.trust_score : item.score;
                const note = "recommendation" in item ? item.risk_tags.slice(0, 2).join(", ") || "Credibility criteria satisfied" : item.note;
                return (
                  <div className={`flex gap-3 border-l-2 ${info.line} pl-3`} key={`${itemDomain}-${index}`}>
                    <span className="shrink-0 text-slate-500">{formatTime(index)}</span>
                    <div className="min-w-0">
                      <p className="text-slate-200"><span className="font-semibold">{itemDomain}</span> <ArrowRight className="mx-1 inline size-3 text-primary" /> <span className={`rounded px-1.5 py-0.5 text-[10px] ${info.className}`}>{info.label}</span></p>
                      <p className="mt-1 text-[10px] text-slate-500">Score: <span className="text-slate-300">{score}</span> <span className="mx-2 text-slate-700">•</span> {note}</p>
                    </div>
                  </div>
                );
              })}
              {!paused && <p className="animate-pulse text-[10px] text-primary">› listening for new source events…</p>}
            </div>
          </div>
        </div>

        <aside className="space-y-5 lg:col-span-4">
          <Card className="glass-panel">
            <CardContent className="pt-5">
              <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Blocked citation reasons</h3>
              <div className="mt-4 space-y-3">
                {reasonCounts.map(({ reason, count }) => {
                  const percent = Math.round((count / reasonTotal) * 100);
                  return <div key={reason}>
                    <div className="mb-1 flex justify-between text-[10px] text-muted-foreground"><span>{reason}</span><span>{percent}%</span></div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-secondary"><div className="h-full rounded-full bg-destructive" style={{ width: `${Math.max(percent, 4)}%`, opacity: percent / 100 + 0.28 }} /></div>
                  </div>;
                })}
              </div>
            </CardContent>
          </Card>

          <Card className={health?.issues.length ? "border-red-200 bg-red-50/30" : undefined}>
            <CardContent className="pt-5">
              <div className="flex items-center justify-between">
                <h3 className={`text-[11px] font-semibold uppercase tracking-wide ${health?.issues.length ? "text-destructive" : "text-muted-foreground"}`}>
                  System health (Sentry)
                </h3>
                {health?.configured && (
                  <span className={`rounded border px-1 text-[9px] font-bold ${health.issues.length ? "border-red-300 text-destructive" : "border-emerald-300 text-emerald-700"}`}>
                    LIVE
                  </span>
                )}
              </div>
              <div className="mt-3 space-y-2 font-mono text-[10px] text-muted-foreground">
                {health === null ? (
                  <p>Checking…</p>
                ) : !health.configured ? (
                  <p>Sentry not configured on the backend (SENTRY_AUTH_TOKEN unset).</p>
                ) : health.issues.length === 0 ? (
                  <p className="text-emerald-700">No unresolved issues in the last 24h.</p>
                ) : (
                  health.issues.map((issue) => (
                    <HealthEvent
                      key={issue.permalink ?? issue.title}
                      tone={issue.level === "error" ? "bg-destructive" : "bg-amber-500"}
                      label={`${issue.title} (${issue.project})`}
                      time={timeAgo(issue.last_seen)}
                    />
                  ))
                )}
              </div>
              <a
                href={`https://${SENTRY_ORG_SLUG}.sentry.io/issues/`}
                target="_blank"
                rel="noreferrer"
                className="mt-4 flex h-8 items-center justify-center rounded bg-red-100 text-[10px] font-semibold uppercase tracking-wide text-destructive active:translate-y-px"
              >
                View Sentry issues
              </a>
            </CardContent>
          </Card>
        </aside>
      </section>
      </div>
    </div>
  );
}

function Metric({ label, value, detail, tone, bar }: { label: string; value: string | number; detail: string; tone?: "danger" | "warning"; bar?: number }) {
  const color = tone === "danger" ? "text-destructive" : tone === "warning" ? "text-amber-700" : "text-foreground";
  return <Card className="min-h-[116px]"><CardContent className="flex h-full flex-col justify-between pt-4"><p className="text-[9px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</p><div><p className={`text-2xl font-bold tracking-tight tabular-nums ${color}`}>{value}</p>{bar ? <div className="mt-2 h-1 w-full overflow-hidden rounded bg-secondary"><div className="h-full bg-primary" style={{ width: `${bar}%` }} /></div> : <p className={`mt-0.5 text-[10px] ${tone ? color : "text-muted-foreground"}`}>{detail}</p>}</div></CardContent></Card>;
}

function HealthEvent({ tone, label, time }: { tone: string; label: string; time: string }) {
  return <div className="flex items-center justify-between gap-3"><span className="flex items-center gap-2"><span className={`size-1.5 rounded-full ${tone}`} />{label}</span><span className="shrink-0 text-slate-400">{time}</span></div>;
}

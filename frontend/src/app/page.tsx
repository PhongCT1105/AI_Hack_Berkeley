"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowRight,
  CirclePause,
  Download,
  ExternalLink,
  Gauge,
  Play,
  Radar,
  ShieldCheck,
  Users,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { useResults } from "@/lib/api";
import type { Recommendation, ScoreResponse } from "@/lib/types";

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
    <div className="mx-auto max-w-7xl px-4 py-7 sm:px-6 sm:py-10">
      <section className="mb-9 max-w-2xl">
        <h1 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">Monitor</h1>
        <p className="mt-1.5 text-sm leading-6 text-muted-foreground sm:text-base">
          Observe source checks, blocked citations, and model behavior in real time. System performance is currently <strong className="font-semibold text-primary">stable</strong>.
        </p>
      </section>

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

          <Card className="border-red-200 bg-red-50/30">
            <CardContent className="pt-5">
              <div className="flex items-center justify-between"><h3 className="text-[11px] font-semibold uppercase tracking-wide text-destructive">System health</h3><span className="rounded border border-red-300 px-1 text-[9px] font-bold text-destructive">LIVE</span></div>
              <div className="mt-3 space-y-2 font-mono text-[10px] text-muted-foreground">
                <HealthEvent tone="bg-destructive" label="API timeout [504]" time="2m ago" />
                <HealthEvent tone="bg-amber-500" label="Crawl failure: Bloomberg" time="15m ago" />
                <HealthEvent tone="bg-primary" label="Kernel refresh" time="1h ago" />
              </div>
              <Link href="/threats" className="mt-4 flex h-8 items-center justify-center rounded bg-red-100 text-[10px] font-semibold uppercase tracking-wide text-destructive active:translate-y-px">View sentry logs</Link>
            </CardContent>
          </Card>
        </aside>
      </section>

      <Card className="glass-panel mt-6 overflow-hidden">
        <CardContent className="pt-6">
          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
            <div><h2 className="text-lg font-bold tracking-tight">Human label queue</h2><p className="mt-1 text-sm text-muted-foreground">Active reinforcement learning from human feedback.</p></div>
            <div className="grid grid-cols-2 divide-x divide-border rounded border border-border bg-muted/60 text-center"><div className="px-5 py-2"><p className="text-lg font-bold text-primary">{results.length || 150}</p><p className="text-[9px] font-semibold uppercase tracking-wide text-muted-foreground">Terac labels</p></div><div className="px-5 py-2"><p className="text-lg font-bold">82%</p><p className="text-[9px] font-semibold uppercase tracking-wide text-muted-foreground">Human agreement</p></div></div>
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <QueueMetric icon={Users} label="Source pairs" value="50" />
            <QueueMetric icon={Gauge} label="Model state" value="Calibrated" />
            <Link href="/arena" className="flex items-center justify-between rounded border border-primary/20 bg-primary/5 p-4 transition-colors hover:bg-primary/10 active:translate-y-px"><span><span className="block text-[10px] font-semibold uppercase tracking-wide text-primary">Pending tasks</span><span className="mt-1 block text-sm font-medium">Start labeling</span></span><Play className="size-4 text-primary" /></Link>
          </div>
        </CardContent>
      </Card>

      <div className="mt-6 flex flex-wrap gap-3 text-xs text-muted-foreground">
        <Link href="/demo" className="inline-flex items-center gap-1 text-primary hover:underline"><ShieldCheck className="size-3.5" /> Run Shield <ExternalLink className="size-3" /></Link>
        <Link href="/eval" className="inline-flex items-center gap-1 hover:text-primary"><Activity className="size-3.5" /> View model evaluation</Link>
        <Link href="/threats" className="inline-flex items-center gap-1 hover:text-primary"><Radar className="size-3.5" /> Review threat feed</Link>
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

function QueueMetric({ icon: Icon, label, value }: { icon: typeof Users; label: string; value: string }) {
  return <div className="rounded border border-border bg-card p-4"><Icon className="size-4 text-primary" /><span className="mt-3 block text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</span><span className="mt-1 block text-lg font-bold">{value}</span></div>;
}

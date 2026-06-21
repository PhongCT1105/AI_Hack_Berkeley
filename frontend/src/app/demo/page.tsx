"use client";

import { useState } from "react";
import {
  Bot, CheckCircle2, ChevronRight, Loader2, Search, ShieldCheck, ShieldX, Sparkles,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { runResearch } from "@/lib/api";
import { scoreColor } from "@/lib/score-ui";
import type { ResearchResponse, ScoreResponse } from "@/lib/types";

const STEPS = [
  { label: "Claude plans the research", icon: Bot },
  { label: "Firecrawl gathers live sources", icon: Search },
  { label: "Shield collects and scores sources", icon: ShieldCheck },
  { label: "Claude writes from validated evidence", icon: Sparkles },
];

const DEFAULT_SHOWCASE_PROMPT = "For a source-trust showcase, compare Nvidia's latest earnings and investment outlook using its investor-relations materials, SEC filings, or Reuters reporting. Contrast them with promotional, anonymous, or guaranteed-return stock-pick claims. Cite only validated evidence and clearly reject weak sources.";

export default function DemoPage() {
  const [prompt, setPrompt] = useState(DEFAULT_SHOWCASE_PROMPT);
  const [maxSources, setMaxSources] = useState(20);
  const [stage, setStage] = useState(-1);
  const [result, setResult] = useState<ResearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setError(null); setResult(null); setStage(0);
    const timer = window.setInterval(() => setStage((value) => Math.min(value + 1, STEPS.length - 1)), 900);
    try { setResult(await runResearch(prompt.trim(), maxSources)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Research run failed"); }
    finally { window.clearInterval(timer); setStage(-1); }
  }

  return <div className="mx-auto max-w-5xl px-4 py-7 sm:px-6 sm:py-10">
    <section className="mb-8 max-w-2xl">
      <div className="mb-3 inline-flex items-center gap-2 rounded border border-primary/20 bg-secondary px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-primary"><ShieldCheck className="size-3.5" /> Research Shield</div>
      <h1 className="text-3xl font-bold tracking-tight">Ask one question. Get evidence you can trust.</h1>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">Claude plans the investigation and synthesizes the answer. Firecrawl gathers live sources. Shield validates every source before it is used.</p>
    </section>

    <Card className="glass-panel">
      <CardContent className="pt-5">
        <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">What do you want to research?</label>
        <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={4} placeholder="Compare credible reporting with promotional investment claims." className="w-full resize-none rounded border border-border bg-card p-3 text-sm leading-6 outline-none focus:border-primary focus:ring-2 focus:ring-primary/15" />
        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <label className="flex items-center gap-2 text-xs text-muted-foreground">Inspect up to <select value={maxSources} onChange={(event) => setMaxSources(Number(event.target.value))} className="rounded border border-border bg-card px-2 py-1 text-foreground"><option value={10}>10 sources</option><option value={20}>20 sources</option><option value={50}>50 sources</option><option value={100}>100 sources</option></select></label>
          <button onClick={run} disabled={stage >= 0 || prompt.trim().length < 3} className="inline-flex h-10 items-center justify-center gap-2 rounded bg-primary px-5 text-sm font-semibold text-primary-foreground active:translate-y-px disabled:opacity-50">{stage >= 0 ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}{stage >= 0 ? "Researching" : "Run research"}</button>
        </div>
        {error && <p className="mt-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p>}
      </CardContent>
    </Card>

    {stage >= 0 && <div className="mt-5 grid gap-3 sm:grid-cols-4">{STEPS.map((step, index) => { const Icon = step.icon; const active = index === stage; const complete = index < stage; return <Card key={step.label} className={active ? "border-primary/30 bg-secondary/30" : complete ? "border-emerald-200 bg-emerald-50" : ""}><CardContent className="flex items-center gap-2.5 pt-4"><span className={complete ? "text-emerald-600" : active ? "text-primary" : "text-muted-foreground"}>{complete ? <CheckCircle2 className="size-4" /> : <Icon className="size-4" />}</span><span className="text-xs font-medium">{step.label}</span></CardContent></Card>; })}</div>}

    {result && <section className="mt-6 space-y-5">
      <Card className="border-primary/20 bg-primary/5"><CardContent className="pt-5"><div className="flex flex-wrap items-center justify-between gap-2"><h2 className="flex items-center gap-2 text-lg font-bold"><Sparkles className="size-4 text-primary" /> Grounded answer</h2><span className="text-xs text-muted-foreground">{result.inspected_count} inspected · {result.cited_sources.length} cited</span></div><p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-foreground">{result.answer}</p><div className="mt-4 flex flex-wrap gap-2 text-[10px] text-muted-foreground"><span className="rounded bg-card px-2 py-1">Query: {result.search_query}</span><span className="rounded bg-card px-2 py-1">{result.agent_mode}</span><span className="rounded bg-card px-2 py-1">{result.search_mode}</span>{result.discovery_error && <span className="rounded border border-amber-300 bg-amber-50 px-2 py-1 text-amber-800">Discovery issue: {result.discovery_error}</span>}</div></CardContent></Card>
      <div className="grid gap-5 lg:grid-cols-2"><SourceGroup title="Validated evidence" icon={ShieldCheck} sources={result.cited_sources} empty="No sources met the citation threshold." /><SourceGroup title="Rejected sources" icon={ShieldX} sources={result.rejected_sources} rejected empty="No sources were rejected in this run." /></div>
    </section>}
  </div>;
}

function SourceGroup({ title, icon: Icon, sources, rejected, empty }: { title: string; icon: typeof ShieldCheck; sources: ScoreResponse[]; rejected?: boolean; empty: string }) {
  return <Card><CardContent className="pt-5"><h2 className={`flex items-center gap-2 text-base font-bold ${rejected ? "text-destructive" : ""}`}><Icon className="size-4" /> {title}</h2><div className="mt-3 space-y-2">{sources.length ? sources.map((source) => <a href={source.url} target="_blank" rel="noreferrer" key={source.trace_id} className="block rounded border border-border bg-card p-3 transition-colors hover:border-primary/30"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="truncate text-sm font-semibold">{source.domain}</p><p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{source.evidence_capsule.compressed_text}</p></div><span className={`text-xl font-bold tabular-nums ${scoreColor(source.trust_score)}`}>{source.trust_score}</span></div><div className="mt-2 flex items-center gap-2"><Badge tone={rejected ? "danger" : "success"}>{rejected ? "Blocked" : "Cite"}</Badge><ChevronRight className="ml-auto size-3.5 text-muted-foreground" /></div></a>) : <p className="rounded bg-muted p-4 text-sm text-muted-foreground">{empty}</p>}</div></CardContent></Card>;
}

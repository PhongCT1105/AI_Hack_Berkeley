"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronRight, Loader2, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { ComicPageHeader } from "@/components/comic/comic-page-header";
import { MascotAvatar } from "@/components/comic/mascot-avatar";
import { NarrativeBlock, ToolCallBlock, ToolResultBlock, Typewriter } from "@/components/workflow-transcript";
import { scoreColor } from "@/lib/score-ui";
import type { ResearchResponse, ScoreResponse, WorkflowEvent } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const DEFAULT_SHOWCASE_PROMPT =
  "For a source-trust showcase, compare Nvidia's latest earnings and investment outlook using its " +
  "investor-relations materials, SEC filings, or Reuters reporting. Contrast them with promotional, " +
  "anonymous, or guaranteed-return stock-pick claims. Cite only validated evidence and clearly reject weak sources.";

export default function DemoPage() {
  const [prompt, setPrompt] = useState(DEFAULT_SHOWCASE_PROMPT);
  const [maxSources, setMaxSources] = useState(6);
  const [running, setRunning] = useState(false);
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [result, setResult] = useState<ResearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [events]);

  useEffect(() => () => sourceRef.current?.close(), []);

  function run() {
    sourceRef.current?.close();
    setError(null);
    setResult(null);
    setEvents([]);
    setRunning(true);

    const url = `${API_URL}/api/workflow/stream?prompt=${encodeURIComponent(prompt.trim())}&max_sources=${maxSources}`;
    const source = new EventSource(url);
    sourceRef.current = source;

    source.onmessage = (message) => {
      const event = JSON.parse(message.data) as WorkflowEvent;
      if (event.type === "done") {
        source.close();
        setRunning(false);
        return;
      }
      if (event.type === "final") {
        setResult(event.output);
      }
      setEvents((prev) => [...prev, event]);
    };

    source.onerror = () => {
      source.close();
      setRunning(false);
      setError("The workflow stream was interrupted. Is the backend running?");
    };
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-7 sm:px-6 sm:py-10">
      <ComicPageHeader
        title="Run Shield!"
        subtitle="Ask one question. Watch Captain Ddoski work — every step below is a real call."
        pose="point"
      />

      <Card className="glass-panel">
        <CardContent className="pt-5">
          <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            What do you want to research?
          </label>
          <textarea
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            rows={4}
            placeholder="Compare credible reporting with promotional investment claims."
            className="w-full resize-none rounded border border-border bg-card p-3 text-sm leading-6 outline-none focus:border-primary focus:ring-2 focus:ring-primary/15"
          />
          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              Inspect up to
              <select
                value={maxSources}
                onChange={(event) => setMaxSources(Number(event.target.value))}
                className="rounded border border-border bg-card px-2 py-1 text-foreground"
              >
                <option value={4}>4 sources</option>
                <option value={6}>6 sources</option>
                <option value={10}>10 sources</option>
                <option value={20}>20 sources</option>
              </select>
            </label>
            <button
              onClick={run}
              disabled={running || prompt.trim().length < 3}
              className="inline-flex h-10 items-center justify-center gap-2 rounded bg-primary px-5 text-sm font-semibold text-primary-foreground active:translate-y-px disabled:opacity-50"
            >
              {running ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              {running ? "Working" : "Run research"}
            </button>
          </div>
          {error && (
            <p className="mt-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p>
          )}
        </CardContent>
      </Card>

      {events.length > 0 && (
        <Card className="mt-5">
          <CardContent className="max-h-[32rem] overflow-y-auto pt-5">
            {events.map((event, index) => (
              <EventBlock key={index} event={event} />
            ))}
            {running && (
              <div className="flex items-center gap-2 py-2 text-xs text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" /> Working…
              </div>
            )}
            <div ref={transcriptEndRef} />
          </CardContent>
        </Card>
      )}

      {result && (
        <section className="mt-6 space-y-5">
          <Card className="border-primary/20 bg-primary/5">
            <CardContent className="pt-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="flex items-center gap-2 text-lg font-bold">
                  <Sparkles className="size-4 text-primary" /> Grounded answer
                </h2>
                <span className="text-xs text-muted-foreground">
                  {result.inspected_count} inspected · {result.cited_sources.length} cited
                </span>
              </div>
              <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-foreground">
                <Typewriter text={result.answer} speedMs={14} />
              </p>
              <div className="mt-4 flex flex-wrap gap-2 text-[10px] text-muted-foreground">
                <span className="rounded bg-card px-2 py-1">Query: {result.search_query}</span>
                <span className="rounded bg-card px-2 py-1">{result.agent_mode}</span>
                <span className="rounded bg-card px-2 py-1">{result.search_mode}</span>
                {result.discovery_error && (
                  <span className="rounded border border-amber-300 bg-amber-50 px-2 py-1 text-amber-800">
                    Discovery issue: {result.discovery_error}
                  </span>
                )}
              </div>
            </CardContent>
          </Card>
          <div className="grid gap-5 lg:grid-cols-2">
            <SourceGroup
              title="Validated evidence"
              pose="goodLike"
              sources={result.cited_sources}
              empty="No sources met the citation threshold."
            />
            <SourceGroup
              title="Rejected sources"
              pose="warningStop"
              sources={result.rejected_sources}
              rejected
              empty="No sources were rejected in this run."
            />
          </div>
        </section>
      )}
    </div>
  );
}

function EventBlock({ event }: { event: WorkflowEvent }) {
  switch (event.type) {
    case "narrative":
      return <NarrativeBlock text={event.text} />;
    case "tool_call":
      return <ToolCallBlock tool={event.tool} input={event.input} />;
    case "tool_result":
      return <ToolResultBlock tool={event.tool} output={event.output} />;
    default:
      return null;
  }
}

function SourceGroup({
  title,
  pose,
  sources,
  rejected,
  empty,
}: {
  title: string;
  pose: "goodLike" | "warningStop";
  sources: ScoreResponse[];
  rejected?: boolean;
  empty: string;
}) {
  return (
    <Card>
      <CardContent className="pt-5">
        <h2 className={`flex items-center gap-2 text-base font-bold ${rejected ? "text-destructive" : ""}`}>
          <MascotAvatar pose={pose} size="xs" /> {title}
        </h2>
        <div className="mt-3 space-y-2">
          {sources.length ? (
            sources.map((source) => (
              <a
                href={source.url}
                target="_blank"
                rel="noreferrer"
                key={source.trace_id}
                className="block rounded border border-border bg-card p-3 transition-colors hover:border-primary/30"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold">{source.domain}</p>
                    <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                      {source.evidence_capsule.compressed_text}
                    </p>
                  </div>
                  <span className={`text-xl font-bold tabular-nums ${scoreColor(source.trust_score)}`}>
                    {source.trust_score}
                  </span>
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <Badge tone={rejected ? "danger" : "success"}>{rejected ? "Blocked" : "Cite"}</Badge>
                  <ChevronRight className="ml-auto size-3.5 text-muted-foreground" />
                </div>
              </a>
            ))
          ) : (
            <p className="rounded bg-muted p-4 text-sm text-muted-foreground">{empty}</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

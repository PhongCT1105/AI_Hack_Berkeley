"use client";

import { useEffect, useState } from "react";
import { Bot, CheckCircle2, ChevronRight, Terminal, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/** One light color family per tool category, so the transcript reads at a
 * glance which kind of work each block is — Claude calls, web fetches,
 * compression, scoring, human-labeling, and model-health checks all look
 * visibly different instead of one uniform indigo chip. */
const TOOL_CATEGORIES: { match: RegExp; chip: string; icon: string; border: string }[] = [
  { match: /^claude_/, chip: "bg-violet-50 text-violet-700", icon: "bg-violet-100 text-violet-700", border: "border-l-violet-300" },
  { match: /^firecrawl_/, chip: "bg-sky-50 text-sky-700", icon: "bg-sky-100 text-sky-700", border: "border-l-sky-300" },
  { match: /compress/, chip: "bg-teal-50 text-teal-700", icon: "bg-teal-100 text-teal-700", border: "border-l-teal-300" },
  { match: /ranker|classifier/, chip: "bg-amber-50 text-amber-700", icon: "bg-amber-100 text-amber-700", border: "border-l-amber-300" },
  { match: /terac/, chip: "bg-rose-50 text-rose-700", icon: "bg-rose-100 text-rose-700", border: "border-l-rose-300" },
  { match: /degradation_monitor|trainer/, chip: "bg-orange-50 text-orange-700", icon: "bg-orange-100 text-orange-700", border: "border-l-orange-300" },
  { match: /score_source/, chip: "bg-secondary text-primary", icon: "bg-secondary text-primary", border: "border-l-primary/30" },
  { match: /cache/, chip: "bg-muted text-muted-foreground", icon: "bg-muted text-muted-foreground", border: "border-l-border" },
];
const DEFAULT_CATEGORY = { chip: "bg-slate-100 text-slate-700", icon: "bg-slate-100 text-slate-700", border: "border-l-slate-300" };

function toolStyle(tool: string) {
  return TOOL_CATEGORIES.find((c) => c.match.test(tool)) ?? DEFAULT_CATEGORY;
}

/** Reveals text word-by-word, the way most chat-style AI UIs stream a
 * generated answer — purely a presentation effect; the words themselves
 * already arrived from the backend as one complete string. Keyed by `text`
 * in the wrapper below so a new string always starts from a fresh mount
 * instead of resetting state inside an effect. */
export function Typewriter({ text, speedMs = 22 }: { text: string; speedMs?: number }) {
  return <TypewriterRun key={text} text={text} speedMs={speedMs} />;
}

function TypewriterRun({ text, speedMs }: { text: string; speedMs: number }) {
  const words = text.split(" ");
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!words.length) return;
    const id = window.setInterval(() => {
      setCount((c) => {
        if (c >= words.length) {
          window.clearInterval(id);
          return c;
        }
        return c + 1;
      });
    }, speedMs);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- words is derived from text, which is the real dependency
  }, [text, speedMs]);

  return <span>{words.slice(0, count).join(" ")}</span>;
}

export function NarrativeBlock({ text }: { text: string }) {
  return (
    <div className="flex items-start gap-3 py-1.5">
      <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
        <Bot className="size-3.5" />
      </span>
      <p className="pt-0.5 text-sm leading-6 text-foreground">
        <Typewriter text={text} />
      </p>
    </div>
  );
}

export function ToolCallBlock({ tool, input }: { tool: string; input: Record<string, unknown> }) {
  const style = toolStyle(tool);
  return (
    <div className="flex items-start gap-3 py-1">
      <span className={cn("mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full", style.icon)}>
        <Terminal className="size-3.5" />
      </span>
      <div className={cn("min-w-0 flex-1 rounded border border-l-2 border-border bg-card/70 px-3 py-2", style.border)}>
        <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          <ChevronRight className="size-3 text-primary" />
          Calling <code className={cn("rounded px-1.5 py-0.5 font-mono", style.chip)}>{tool}</code>
        </div>
        <pre className="mt-1.5 overflow-x-auto whitespace-pre-wrap break-all font-mono text-[11px] leading-5 text-muted-foreground">
          {JSON.stringify(input, null, 2)}
        </pre>
      </div>
    </div>
  );
}

export function ToolResultBlock({ tool, output }: { tool: string; output: Record<string, unknown> }) {
  const isError = "error" in output && output.error != null;
  const skipped = output.skipped === true;
  const style = toolStyle(tool);
  return (
    <div className="flex items-start gap-3 py-1">
      <span
        className={cn(
          "mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full",
          isError ? "bg-red-100 text-red-600" : skipped ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-600",
        )}
      >
        {isError ? <XCircle className="size-3.5" /> : <CheckCircle2 className="size-3.5" />}
      </span>
      <div className={cn("min-w-0 flex-1 rounded border border-l-2 border-border bg-card/70 px-3 py-2", style.border)}>
        <div className="flex items-center justify-between gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Result · <code className={cn("rounded px-1.5 py-0.5 font-mono", style.chip)}>{tool}</code>
          </span>
          {typeof output.trust_score === "number" && typeof output.recommendation === "string" && (
            <Badge
              tone={
                output.recommendation === "USE" ? "success" : output.recommendation === "CAUTION" ? "warning" : "danger"
              }
            >
              {output.recommendation} · {output.trust_score}
            </Badge>
          )}
        </div>
        <pre className="mt-1.5 overflow-x-auto whitespace-pre-wrap break-all font-mono text-[11px] leading-5 text-foreground">
          {JSON.stringify(output, null, 2)}
        </pre>
      </div>
    </div>
  );
}

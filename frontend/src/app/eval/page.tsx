"use client";

import { useEffect, useState } from "react";
import { BarChart3, FileStack, Gauge, Sparkles, TrendingUp } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getEvalMetrics } from "@/lib/api";
import type { EvalMetrics } from "@/lib/types";

const RESULT_TONE: Record<string, "success" | "warning" | "danger"> = {
  both_right: "success",
  base_wrong_trained_right: "warning",
  both_wrong: "danger",
};

const RESULT_LABEL: Record<string, string> = {
  both_right: "Both correct",
  base_wrong_trained_right: "Trained fixed it",
  both_wrong: "Both wrong",
};

export default function EvalPage() {
  const [metrics, setMetrics] = useState<EvalMetrics | null>(null);

  useEffect(() => {
    getEvalMetrics().then(setMetrics);
  }, []);

  if (!metrics) {
    return <div className="mx-auto max-w-7xl px-6 py-20 text-center text-sm text-muted-foreground">Loading evaluation metrics…</div>;
  }

  const maxAccuracy = Math.max(metrics.base_accuracy, metrics.trained_accuracy, 1);

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      {/* Header */}
      <div className="mb-7">
        <h1 className="flex items-center gap-2.5 text-2xl font-bold tracking-tight text-foreground">
          <Gauge className="size-6 text-primary" />
          Model Improvement
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">Base heuristic ranker vs Terac-trained ranker.</p>
      </div>

      {/* Summary cards */}
      <div className="mb-6 grid gap-4 sm:grid-cols-4">
        <MetricCard label="Base heuristic accuracy" value={`${metrics.base_accuracy}%`} accent="gray" />
        <MetricCard label="Terac-trained accuracy" value={`${metrics.trained_accuracy}%`} accent="primary" />
        <MetricCard label="Improvement" value={`+${metrics.improvement_pct}pp`} accent="emerald" icon={<TrendingUp className="size-4 text-emerald-500" />} />
        <MetricCard label="Held-out examples" value={metrics.held_out_examples} accent="gray" icon={<FileStack className="size-4 text-muted-foreground" />} />
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
        {/* Bar chart comparison */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-foreground">
              <BarChart3 className="size-4 text-primary" />
              Base vs Trained Accuracy
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <Bar label="Base heuristic ranker" value={metrics.base_accuracy} max={maxAccuracy} color="#9ca3af" />
            <Bar label="Terac-trained ranker" value={metrics.trained_accuracy} max={maxAccuracy} color="#4648d4" />
            <p className="rounded border border-primary/15 bg-secondary/40 px-3.5 py-3 text-xs text-primary">
              <strong>Base</strong> = hand-written heuristic ranker. <strong>Trained</strong> = model calibrated on Terac
              human labels. Terac labels are the ground truth this comparison is measured against.
            </p>
          </CardContent>
        </Card>

        {/* Detailed metrics */}
        <Card>
          <CardHeader>
            <CardTitle className="text-foreground">Detailed Metrics</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Stat label="Human preference match" value={`${metrics.human_preference_match}%`} />
            <Stat label="Bad-source filtering precision" value={`${metrics.bad_source_filtering_precision}%`} />
            <Stat label="Cite / do-not-cite accuracy" value={`${metrics.cite_do_not_cite_accuracy}%`} />
            <Stat label="Average token reduction" value={`${metrics.avg_token_reduction_pct}%`} />
          </CardContent>
        </Card>
      </div>

      {/* Model comparison cards — Shield Terminal treatment */}
      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <Card className="border-t-4 border-t-muted-foreground/30 bg-muted/30">
          <CardContent className="pt-5">
            <div className="mb-3 flex items-center gap-2">
              <Gauge className="size-5 text-muted-foreground" />
              <h4 className="text-base font-bold text-foreground">Base Heuristic Ranker</h4>
            </div>
            <div className="w-fit rounded bg-card px-3 py-1">
              <span className="text-xs font-bold tracking-wide text-muted-foreground">BRITTLE</span>
            </div>
            <p className="mt-2 text-sm text-muted-foreground">
              Hand-written rules that fail on nuanced language, sarcasm, or novel domains.
            </p>
          </CardContent>
        </Card>
        <Card className="comic-border relative overflow-hidden bg-card">
          <div className="pointer-events-none absolute -right-4 -top-4 opacity-5">
            <Gauge className="size-32 text-primary" />
          </div>
          <CardContent className="relative pt-5">
            <div className="mb-3 flex items-center gap-2">
              <Sparkles className="size-5 text-primary" />
              <h4 className="text-base font-bold text-primary">Terac-Trained Ranker</h4>
            </div>
            <div className="w-fit rounded border border-primary/20 bg-secondary px-3 py-1">
              <span className="text-xs font-bold tracking-wide text-primary">CALIBRATED</span>
            </div>
            <p className="mt-2 text-sm text-foreground">
              Aligned to human preference labels collected in the Terac Arena.
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Held-out example table */}
      <Card className="mt-6 overflow-hidden">
        <div className="flex items-center justify-between border-b border-border bg-muted px-5 py-3">
          <span className="text-sm font-semibold text-foreground">Held-out Examples</span>
          <span className="text-xs text-muted-foreground">{metrics.examples.length} examples</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs font-semibold tracking-wide text-muted-foreground">
                <th className="px-5 py-3">Task</th>
                <th className="px-5 py-3">Source A</th>
                <th className="px-5 py-3">Source B</th>
                <th className="px-5 py-3">Human preferred</th>
                <th className="px-5 py-3">Base predicted</th>
                <th className="px-5 py-3">Trained predicted</th>
                <th className="px-5 py-3">Result</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {metrics.examples.map((ex, i) => (
                <tr key={i} className="hover:bg-secondary/30">
                  <td className="max-w-[28ch] truncate px-5 py-3 text-foreground">{ex.task}</td>
                  <td className="px-5 py-3 font-mono text-xs text-muted-foreground">{ex.source_a}</td>
                  <td className="px-5 py-3 font-mono text-xs text-muted-foreground">{ex.source_b}</td>
                  <td className="px-5 py-3 font-semibold uppercase text-foreground">{ex.human_preferred}</td>
                  <td className={`px-5 py-3 uppercase ${ex.base_predicted === ex.human_preferred ? "text-emerald-600" : "text-red-500"}`}>
                    {ex.base_predicted}
                  </td>
                  <td className={`px-5 py-3 uppercase ${ex.trained_predicted === ex.human_preferred ? "text-emerald-600" : "text-red-500"}`}>
                    {ex.trained_predicted}
                  </td>
                  <td className="px-5 py-3">
                    <Badge tone={RESULT_TONE[ex.result] ?? "warning"}>{RESULT_LABEL[ex.result] ?? ex.result}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Compression section — console-theme terminal treatment */}
      <Card className="mt-6 overflow-hidden">
        <div className="grid grid-cols-1 md:grid-cols-2">
          <div className="flex flex-col justify-center border-r border-border p-6">
            <h3 className="mb-2 flex items-center gap-2 text-lg font-bold text-foreground">
              <Sparkles className="size-4 text-primary" />
              Credibility Capsules
            </h3>
            <p className="mb-4 text-sm text-muted-foreground">
              Messy webpages are distilled into decision-relevant evidence, drastically reducing token
              overhead while retaining the signal an agent needs to decide.
            </p>
            <div className="flex flex-wrap items-end gap-4">
              <div>
                <p className="text-xs font-semibold tracking-wide text-muted-foreground">Raw</p>
                <p className="font-mono text-base font-semibold text-foreground">{metrics.raw_tokens_example.toLocaleString()} tokens</p>
              </div>
              <span className="text-muted-foreground/50">→</span>
              <div>
                <p className="text-xs font-semibold tracking-wide text-primary">Capsule</p>
                <p className="font-mono text-base font-semibold text-primary">{metrics.capsule_tokens_example.toLocaleString()} tokens</p>
              </div>
            </div>
            <div className="mt-4 flex items-center justify-between rounded border border-primary/20 bg-secondary/40 px-3.5 py-2.5">
              <span className="text-xs font-semibold tracking-wide text-primary">Reduction rate</span>
              <Badge tone="purple" className="text-sm">−{metrics.avg_token_reduction_pct}%</Badge>
            </div>
          </div>
          <div className="console-theme p-6 font-mono text-xs">
            <div className="mb-3 flex items-center gap-2 text-white/40">
              <Sparkles className="size-3.5" />
              <span>COMPRESSION_LOG_TRACE</span>
            </div>
            <p className="text-indigo-300">&gt; analyzing_structure...</p>
            <p className="text-white/50">&gt; extracting_critical_entities: [&quot;source&quot;, &quot;claims&quot;, &quot;citations&quot;]</p>
            <p className="text-indigo-300">&gt; distilling_arguments: [{metrics.avg_token_reduction_pct}% reduction]</p>
            <p className="mt-3 text-white/30">NOISY_WEBPAGE_RAW → SAFE_EVIDENCE_CAPSULE</p>
          </div>
        </div>
      </Card>
    </div>
  );
}

function MetricCard({
  label,
  value,
  accent,
  icon,
}: {
  label: string;
  value: React.ReactNode;
  accent: "primary" | "emerald" | "gray";
  icon?: React.ReactNode;
}) {
  const valueColor = accent === "primary" ? "text-primary" : accent === "emerald" ? "text-emerald-600" : "text-foreground";
  return (
    <Card>
      <CardContent className="pt-5">
        <div className="flex items-center gap-2 text-xs font-semibold tracking-wide text-muted-foreground">{icon}{label}</div>
        <p className={`mt-1 text-2xl font-bold tabular-nums ${valueColor}`}>{value}</p>
      </CardContent>
    </Card>
  );
}

function Bar({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-sm font-medium text-foreground">{label}</span>
        <span className="text-sm font-bold tabular-nums text-foreground">{value}%</span>
      </div>
      <div className="h-3 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full transition-all" style={{ width: `${(value / max) * 100}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded border border-border bg-muted/60 px-3.5 py-2.5">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-semibold tabular-nums text-foreground">{value}</span>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { BarChart3, FileStack, Gauge, PieChart as PieChartIcon, Sparkles, TrendingUp } from "lucide-react";
import {
  Bar as RechartsBar,
  BarChart,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ThreeWayCompressionEvaluation } from "@/components/compression/three-way-evaluation";
import { getEvalMetrics } from "@/lib/api";
import type { EvalMetrics } from "@/lib/types";

const RESULT_TONE: Record<string, "success" | "warning" | "danger"> = {
  both_right: "success",
  base_wrong_trained_right: "warning",
  base_right_trained_wrong: "danger",
  both_wrong: "danger",
};

const RESULT_LABEL: Record<string, string> = {
  both_right: "Both correct",
  base_wrong_trained_right: "Trained fixed it",
  base_right_trained_wrong: "Trained regressed",
  both_wrong: "Both wrong",
};

const RESULT_COLOR: Record<string, string> = {
  both_right: "#10b981",
  base_wrong_trained_right: "#4648d4",
  base_right_trained_wrong: "#f59e0b",
  both_wrong: "#ef4444",
};

// Recharts initializes ResponsiveContainer at -1 × -1 until ResizeObserver
// measures its parent. Supplying a valid initial size prevents its development
// warning while the container settles to its actual responsive dimensions.
const BAR_CHART_INITIAL_DIMENSION = { width: 1, height: 224 };
const PIE_CHART_INITIAL_DIMENSION = { width: 1, height: 160 };

export default function EvalPage() {
  const [metrics, setMetrics] = useState<EvalMetrics | null>(null);

  useEffect(() => {
    getEvalMetrics().then(setMetrics);
  }, []);

  if (!metrics) {
    return <div className="mx-auto max-w-7xl px-6 py-20 text-center text-sm text-muted-foreground">Loading evaluation metrics…</div>;
  }

  const accuracyChartData = [
    { name: "Base (Fin-Fact pretrain)", accuracy: metrics.base_accuracy, fill: "#9ca3af" },
    { name: "Terac-trained", accuracy: metrics.trained_accuracy, fill: "#4648d4" },
  ];

  const resultCounts = metrics.examples.reduce<Record<string, number>>((acc, ex) => {
    acc[ex.result] = (acc[ex.result] ?? 0) + 1;
    return acc;
  }, {});
  const resultChartData = Object.entries(resultCounts).map(([result, count]) => ({
    name: RESULT_LABEL[result] ?? result,
    value: count,
    fill: RESULT_COLOR[result] ?? "#9ca3af",
  }));

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      {/* Header */}
      <div className="mb-7">
        <h1 className="flex items-center gap-2.5 text-2xl font-bold tracking-tight text-foreground">
          <Gauge className="size-6 text-primary" />
          Model Improvement
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">Fin-Fact pretrain (no human input) vs Terac-trained model.</p>
      </div>

      {/* Summary cards */}
      <div className="mb-6 grid gap-4 sm:grid-cols-4">
        <MetricCard label="Base: Fin-Fact pretrain" value={`${metrics.base_accuracy}%`} accent="gray" />
        <MetricCard label="Terac-trained (5-fold CV mean)" value={`${metrics.trained_accuracy}%`} accent="primary" />
        <MetricCard label="Improvement" value={`+${metrics.improvement_pct}pp`} accent="emerald" icon={<TrendingUp className="size-4 text-emerald-500" />} />
        <MetricCard label="Held-out examples" value={metrics.held_out_examples} accent="gray" icon={<FileStack className="size-4 text-muted-foreground" />} />
      </div>
      <p className="mb-6 -mt-2 text-xs text-muted-foreground">
        Terac-trained accuracy is a 5-fold cross-validation mean across all {metrics.held_out_examples * 5} labeled
        rows (std ≈ 5.6pp) — more stable than reading off a single small holdout split.
      </p>

      <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
        {/* Bar chart comparison */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-foreground">
              <BarChart3 className="size-4 text-primary" />
              Base vs Trained Accuracy
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-56">
              <ResponsiveContainer
                width="100%"
                height="100%"
                initialDimension={BAR_CHART_INITIAL_DIMENSION}
              >
                <BarChart data={accuracyChartData} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} stroke="currentColor" className="text-muted-foreground" />
                  <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 12 }} stroke="currentColor" className="text-muted-foreground" />
                  <Tooltip
                    formatter={(value) => [`${value}%`, "Accuracy"]}
                    contentStyle={{ borderRadius: 8, fontSize: 12 }}
                  />
                  <RechartsBar dataKey="accuracy" radius={[6, 6, 0, 0]} maxBarSize={90}>
                    {accuracyChartData.map((entry) => (
                      <Cell key={entry.name} fill={entry.fill} />
                    ))}
                  </RechartsBar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-3 rounded border border-primary/15 bg-secondary/40 px-3.5 py-3 text-xs text-primary">
              <strong>Base</strong> = trained only on Fin-Fact&apos;s public true/false verdicts, zero human input.
              <strong> Terac-trained</strong> = trained directly on the human-annotated Terac labels. Both
              evaluated on the same held-out test split.
            </p>
          </CardContent>
        </Card>

        {/* Detailed metrics + results breakdown */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-foreground">
              <PieChartIcon className="size-4 text-primary" />
              Held-out Result Breakdown
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-40">
              <ResponsiveContainer
                width="100%"
                height="100%"
                initialDimension={PIE_CHART_INITIAL_DIMENSION}
              >
                <PieChart>
                  <Pie data={resultChartData} dataKey="value" nameKey="name" innerRadius={36} outerRadius={60} paddingAngle={2}>
                    {resultChartData.map((entry) => (
                      <Cell key={entry.name} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value, name) => [`${value} examples`, name]} contentStyle={{ borderRadius: 8, fontSize: 12 }} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-3 space-y-3">
              <Stat label="Annotator agreement rate" value={`${metrics.human_preference_match}%`} />
              <Stat label="Bad-source filtering precision" value={`${metrics.bad_source_filtering_precision}%`} />
              <Stat label="Citation F1 score" value={`${metrics.cite_do_not_cite_accuracy}%`} />
              <Stat label="Average token reduction" value={`${metrics.avg_token_reduction_pct}%`} />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Model comparison cards use the Captain America treatment. */}
      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <Card className="border-t-4 border-t-muted-foreground/30 bg-muted/30">
          <CardContent className="pt-5">
            <div className="mb-3 flex items-center gap-2">
              <Gauge className="size-5 text-muted-foreground" />
              <h4 className="text-base font-bold text-foreground">Base: Fin-Fact Pretrain</h4>
            </div>
            <div className="w-fit rounded bg-card px-3 py-1">
              <span className="text-xs font-bold tracking-wide text-muted-foreground">NO HUMAN INPUT</span>
            </div>
            <p className="mt-2 text-sm text-muted-foreground">
              Trained only on public Snopes-style true/false verdicts — a different question than
              &quot;would an AI agent cite this,&quot; so it barely beats chance on the real task.
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
              <span className="text-xs font-bold tracking-wide text-primary">HUMAN-LABELED</span>
            </div>
            <p className="mt-2 text-sm text-foreground">
              Trained directly on citation-worthiness verdicts collected from human annotators in Terac.
            </p>
          </CardContent>
        </Card>
      </div>

      <ThreeWayCompressionEvaluation />

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

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded border border-border bg-muted/60 px-3.5 py-2.5">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-semibold tabular-nums text-foreground">{value}</span>
    </div>
  );
}

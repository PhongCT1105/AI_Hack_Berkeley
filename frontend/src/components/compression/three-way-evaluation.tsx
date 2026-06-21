"use client";

import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type EvaluationResult = {
  input_tokens: number;
  output: string;
};

type EvaluationVariant = {
  result?: EvaluationResult;
  llm_input_token_savings_pct?: number;
};

type SummaryVariant = {
  avg_llm_input_tokens: number;
  avg_llm_input_token_savings_pct?: number;
  decision_agreement_rate?: number;
  avg_critical_fact_f1?: number;
};

type EvaluationReport = {
  status: string;
  requested_queries: number;
  summary?: {
    completed_queries: number;
    failed_queries: number;
    variants: Record<string, SummaryVariant>;
  };
  rows: Array<{
    task_id: string;
    variants: {
      raw: EvaluationVariant;
      captain_ddoski?: EvaluationVariant;
      ttc?: EvaluationVariant;
    };
  }>;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const BAR_CHART_INITIAL_DIMENSION = { width: 1, height: 224 };

export function ThreeWayCompressionEvaluation() {
  const [evaluation, setEvaluation] = useState<EvaluationReport | null>(null);
  const [error, setError] = useState("");
  const [selectedTaskId, setSelectedTaskId] = useState("");

  useEffect(() => {
    let cancelled = false;
    void fetch(`${API_BASE}/api/compress/evaluations/latest`)
      .then(async (response) => {
        if (!response.ok) throw new Error("No three-way evaluation has been run yet.");
        return response.json() as Promise<EvaluationReport>;
      })
      .then((report) => {
        if (!cancelled) {
          setEvaluation(report);
          setSelectedTaskId(report.rows[0]?.task_id ?? "");
        }
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "Unable to load compression evaluation.");
      });
    return () => { cancelled = true; };
  }, []);

  const variants = evaluation?.summary?.variants;
  const selected = evaluation?.rows.find((row) => row.task_id === selectedTaskId) ?? evaluation?.rows[0];
  const chartData = variants ? [
    { name: "Raw", tokens: variants.raw?.avg_llm_input_tokens ?? 0, fill: "#a1a1aa" },
    { name: "Captain Ddoski", tokens: variants.captain_ddoski?.avg_llm_input_tokens ?? 0, fill: "#4648d4" },
    { name: "Token Company", tokens: variants.ttc?.avg_llm_input_tokens ?? 0, fill: "#10b981" },
  ] : [];

  return (
    <Card className="mt-6 overflow-hidden">
      <CardHeader className="border-b border-border bg-muted/30">
        <CardTitle className="text-base text-foreground">Compression Quality Evaluation</CardTitle>
        <p className="text-sm font-normal text-muted-foreground">
          Raw prompts, Captain Ddoski capsules, and The Token Company compression evaluated on the same citation tasks.
        </p>
      </CardHeader>
      <CardContent className="p-0">
        {!evaluation || !variants ? (
          <div className="px-6 py-8 text-sm text-muted-foreground">
            {error || "Loading saved compression evaluation."}
          </div>
        ) : (
          <>
            <div className="grid gap-0 border-b border-border lg:grid-cols-[1.1fr_0.9fr]">
              <div className="overflow-x-auto p-5">
                <table className="w-full min-w-[660px] text-left text-sm">
                  <thead className="text-xs font-semibold tracking-wide text-muted-foreground">
                    <tr>
                      <th className="pb-3">Variant</th>
                      <th className="pb-3">Avg input</th>
                      <th className="pb-3">Reduction</th>
                      <th className="pb-3">Decision match</th>
                      <th className="pb-3">Fact F1</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    <SummaryRow label="Raw prompt" data={variants.raw} baseline />
                    <SummaryRow label="Captain Ddoski capsule" data={variants.captain_ddoski} />
                    <SummaryRow label="Token Company" data={variants.ttc} />
                  </tbody>
                </table>
              </div>
              <div className="border-t border-border p-5 lg:border-l lg:border-t-0">
                <p className="text-sm font-semibold text-foreground">Average model input</p>
                <div className="mt-3 h-52">
                  <ResponsiveContainer width="100%" height="100%" initialDimension={BAR_CHART_INITIAL_DIMENSION}>
                    <BarChart data={chartData} margin={{ top: 8, right: 4, left: -16, bottom: 0 }}>
                      <CartesianGrid vertical={false} stroke="currentColor" className="text-border" />
                      <XAxis dataKey="name" tick={{ fontSize: 11 }} stroke="currentColor" className="text-muted-foreground" />
                      <YAxis tick={{ fontSize: 11 }} stroke="currentColor" className="text-muted-foreground" />
                      <Tooltip formatter={(value) => [`${value} tokens`, "Input"]} contentStyle={{ borderRadius: 8, fontSize: 12 }} />
                      <Bar dataKey="tokens" radius={[5, 5, 0, 0]} maxBarSize={70}>
                        {chartData.map((entry) => <Cell key={entry.name} fill={entry.fill} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            {selected ? (
              <div>
                <div className="flex flex-col gap-3 border-b border-border px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-sm font-semibold text-foreground">Saved output comparison</p>
                    <p className="text-xs text-muted-foreground">
                      {evaluation.summary?.completed_queries}/{evaluation.requested_queries} tasks complete · {evaluation.summary?.failed_queries ?? 0} failed
                    </p>
                  </div>
                  <select
                    className="h-9 rounded border border-input bg-background px-3 font-mono text-xs text-foreground outline-none ring-primary/20 focus:ring-4"
                    value={selectedTaskId}
                    onChange={(event) => setSelectedTaskId(event.target.value)}
                    aria-label="Select compression benchmark task"
                  >
                    {evaluation.rows.map((row) => <option key={row.task_id} value={row.task_id}>{row.task_id}</option>)}
                  </select>
                </div>
                <div className="grid divide-y divide-border lg:grid-cols-3 lg:divide-x lg:divide-y-0">
                  <OutputPanel label="Raw prompt" variant={selected.variants.raw} />
                  <OutputPanel label="Captain Ddoski capsule" variant={selected.variants.captain_ddoski} />
                  <OutputPanel label="Token Company" variant={selected.variants.ttc} />
                </div>
              </div>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function SummaryRow({ label, data, baseline = false }: { label: string; data?: SummaryVariant; baseline?: boolean }) {
  return (
    <tr className="text-muted-foreground">
      <td className="py-3 font-medium text-foreground">{label}</td>
      <td className="py-3 font-mono">{Math.round(data?.avg_llm_input_tokens ?? 0).toLocaleString()}</td>
      <td className="py-3 font-mono">{baseline ? "baseline" : `${data?.avg_llm_input_token_savings_pct ?? 0}%`}</td>
      <td className="py-3 font-mono">{baseline ? "reference" : `${Math.round((data?.decision_agreement_rate ?? 0) * 100)}%`}</td>
      <td className="py-3 font-mono">{baseline ? "reference" : `${Math.round((data?.avg_critical_fact_f1 ?? 0) * 100)}%`}</td>
    </tr>
  );
}

function OutputPanel({ label, variant }: { label: string; variant?: EvaluationVariant }) {
  return (
    <div className="min-w-0 p-5">
      <p className="text-xs font-semibold tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-2 font-mono text-xs text-muted-foreground">
        {variant?.result?.input_tokens ?? "--"} input tokens{variant?.llm_input_token_savings_pct != null ? ` · ${variant.llm_input_token_savings_pct}% saved` : ""}
      </p>
      <pre className="mt-3 max-h-52 overflow-auto whitespace-pre-wrap rounded bg-muted p-3 font-mono text-xs leading-5 text-foreground">
        {variant?.result?.output || "Output pending."}
      </pre>
    </div>
  );
}

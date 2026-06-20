"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Loader2, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { saveResult, scoreSource, useResults } from "@/lib/api";
import { recTone, scoreColor } from "@/lib/score-ui";

const SAMPLES = [
  { label: "SEC (trusted)", url: "https://www.sec.gov/investor/pubs/assetallocation.htm" },
  { label: "Investopedia", url: "https://www.investopedia.com/terms/i/indexfund.asp" },
  { label: "Affiliate blog", url: "https://best-stock-picks-now.com/double-your-money" },
];

export default function Dashboard() {
  const router = useRouter();
  const [task, setTask] = useState("Research low-risk retirement investments");
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const results = useResults();

  async function analyze(targetUrl: string) {
    if (!targetUrl.trim() || !task.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const r = await scoreSource(targetUrl.trim(), task.trim());
      saveResult(r);
      setUrl("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  const analyzed = results.length;
  const avg = analyzed ? Math.round(results.reduce((s, r) => s + r.trust_score, 0) / analyzed) : 0;
  const avoided = results.filter((r) => r.recommendation === "AVOID").length;

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">SourceGuard Dashboard</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Give an agent a task and a source URL. AgentShield returns a trust score, a
          USE&nbsp;/&nbsp;CAUTION&nbsp;/&nbsp;AVOID call, risk tags, and a compressed evidence capsule.
        </p>
      </div>

      {/* Input panel */}
      <Card className="mb-6">
        <CardContent className="pt-5">
          <div className="grid gap-4 md:grid-cols-[1fr_1fr_auto] md:items-end">
            <Field label="Task">
              <input
                value={task}
                onChange={(e) => setTask(e.target.value)}
                placeholder="What will the agent do with this source?"
                className="h-9 w-full rounded-lg border border-input bg-background px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
              />
            </Field>
            <Field label="Source URL">
              <input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && analyze(url)}
                placeholder="https://example.com/finance-article"
                className="h-9 w-full rounded-lg border border-input bg-background px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
              />
            </Field>
            <Button onClick={() => analyze(url)} disabled={loading} size="lg">
              {loading ? <Loader2 className="animate-spin" /> : <ShieldAlert />}
              Analyze source
            </Button>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="text-xs text-muted-foreground">Try:</span>
            {SAMPLES.map((s) => (
              <button
                key={s.url}
                onClick={() => analyze(s.url)}
                disabled={loading}
                className="rounded-md border border-border bg-muted/40 px-2 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
              >
                {s.label}
              </button>
            ))}
          </div>
          {error && <p className="mt-3 text-xs text-rose-400">{error}</p>}
        </CardContent>
      </Card>

      {/* KPIs */}
      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <Kpi label="Sources analyzed" value={analyzed} />
        <Kpi
          label="Average trust"
          value={analyzed ? avg : "—"}
          valueClass={analyzed ? scoreColor(avg) : ""}
        />
        <Kpi label="Flagged AVOID" value={avoided} valueClass={avoided ? "text-rose-400" : ""} />
      </div>

      {/* Analyzed sources table */}
      <Card>
        <div className="border-b border-border px-5 py-3 text-sm font-semibold">Analyzed Sources</div>
        {analyzed === 0 ? (
          <div className="p-10 text-center text-sm text-muted-foreground">
            No sources yet. Analyze one above to populate the arena and detail views.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-5 py-2.5 font-medium">Source</th>
                <th className="px-5 py-2.5 font-medium">Trust</th>
                <th className="px-5 py-2.5 font-medium">Recommendation</th>
                <th className="px-5 py-2.5 font-medium">Risk tags</th>
                <th className="px-5 py-2.5 font-medium" />
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr
                  key={r.trace_id}
                  onClick={() => router.push(`/source/${r.trace_id}`)}
                  className="cursor-pointer border-b border-border/60 transition-colors last:border-0 hover:bg-muted/40"
                >
                  <td className="px-5 py-3">
                    <div className="font-medium">{r.domain}</div>
                    <div className="max-w-[28ch] truncate text-xs text-muted-foreground">{r.url}</div>
                  </td>
                  <td className="px-5 py-3">
                    <span className={`text-lg font-semibold tabular-nums ${scoreColor(r.trust_score)}`}>
                      {r.trust_score}
                    </span>
                  </td>
                  <td className="px-5 py-3">
                    <Badge tone={recTone(r.recommendation)}>{r.recommendation}</Badge>
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex flex-wrap gap-1">
                      {r.risk_tags.length === 0 ? (
                        <span className="text-xs text-muted-foreground">—</span>
                      ) : (
                        r.risk_tags.slice(0, 3).map((t) => (
                          <Badge key={t} tone="danger">
                            {t}
                          </Badge>
                        ))
                      )}
                    </div>
                  </td>
                  <td className="px-5 py-3 text-right">
                    <ArrowRight className="ml-auto size-4 text-muted-foreground" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

function Kpi({
  label,
  value,
  valueClass = "",
}: {
  label: string;
  value: React.ReactNode;
  valueClass?: string;
}) {
  return (
    <Card>
      <CardContent className="pt-5">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className={`mt-1 text-3xl font-semibold tabular-nums ${valueClass}`}>{value}</div>
      </CardContent>
    </Card>
  );
}

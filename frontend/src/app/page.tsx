"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  ChevronRight,
  Loader2,
  Search,
  ShieldAlert,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { saveResult, scoreSource, useResults } from "@/lib/api";
import { recLabel, recTone, scoreColor, scoreHex } from "@/lib/score-ui";

const SAMPLES = [
  { label: "SEC.gov", url: "https://www.sec.gov/investor/pubs/assetallocation.htm" },
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
  const avg = analyzed
    ? Math.round(results.reduce((s, r) => s + r.trust_score, 0) / analyzed)
    : 0;
  const avoided = results.filter((r) => r.recommendation === "AVOID").length;
  const trusted = results.filter((r) => r.recommendation === "USE").length;

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">

      {/* Page header */}
      <div className="mb-7 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Source Credibility Dashboard</h1>
          <p className="mt-0.5 text-sm text-gray-500">
            Finance-domain source validation for AI agents.&nbsp;
            <span className="text-violet-600">Paste a URL → get a trust verdict.</span>
          </p>
        </div>
      </div>

      {/* Analyze panel */}
      <Card className="mb-6 border-violet-100 bg-white shadow-md shadow-violet-50">
        <CardContent className="pt-5">
          <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto] md:items-end">
            <Field label="Agent Task">
              <input
                value={task}
                onChange={(e) => setTask(e.target.value)}
                placeholder="What will the agent do with this source?"
                className="h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 placeholder:text-gray-400 outline-none transition-shadow focus:border-violet-400 focus:ring-2 focus:ring-violet-100"
              />
            </Field>
            <Field label="Source URL">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-gray-400" />
                <input
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && analyze(url)}
                  placeholder="https://example.com/finance-article"
                  className="h-10 w-full rounded-lg border border-gray-200 bg-white py-0 pr-3 pl-9 text-sm text-gray-900 placeholder:text-gray-400 outline-none transition-shadow focus:border-violet-400 focus:ring-2 focus:ring-violet-100"
                />
              </div>
            </Field>
            <button
              onClick={() => analyze(url)}
              disabled={loading || !url.trim() || !task.trim()}
              className="flex h-10 cursor-pointer items-center gap-2 rounded-lg bg-violet-600 px-5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? <Loader2 className="size-4 animate-spin" /> : <ShieldAlert className="size-4" />}
              Analyze source
            </button>
          </div>

          {/* Quick samples */}
          <div className="mt-3.5 flex flex-wrap items-center gap-2">
            <span className="text-xs text-gray-400">Try a sample:</span>
            {SAMPLES.map((s) => (
              <button
                key={s.url}
                onClick={() => analyze(s.url)}
                disabled={loading}
                className="cursor-pointer rounded-full border border-gray-200 bg-gray-50 px-3 py-1 text-xs font-medium text-gray-600 transition-colors hover:border-violet-200 hover:bg-violet-50 hover:text-violet-700 disabled:opacity-40"
              >
                {s.label}
              </button>
            ))}
          </div>
          {error && (
            <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">{error}</p>
          )}
        </CardContent>
      </Card>

      {/* KPI row */}
      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <KpiCard
          label="Sources analyzed"
          value={analyzed}
          sub="this session"
          icon={<ShieldAlert className="size-5 text-violet-500" />}
          accent="violet"
        />
        <KpiCard
          label="Average trust score"
          value={analyzed ? avg : "—"}
          sub={analyzed ? (avg >= 70 ? "Healthy" : avg >= 40 ? "Mixed signals" : "Risky pool") : "No data yet"}
          icon={<TrendingUp className="size-5 text-emerald-500" />}
          accent="emerald"
          valueClass={analyzed ? scoreColor(avg) : "text-gray-400"}
        />
        <KpiCard
          label="Flagged AVOID"
          value={avoided}
          sub={trusted ? `${trusted} cleared as USE` : "No trusted sources yet"}
          icon={<TrendingDown className="size-5 text-red-500" />}
          accent="red"
          valueClass={avoided > 0 ? "text-red-600" : "text-gray-900"}
        />
      </div>

      {/* Results table */}
      <Card className="overflow-hidden border-gray-200 shadow-sm">
        {/* Table header */}
        <div className="flex items-center justify-between border-b border-gray-100 bg-gray-50 px-5 py-3">
          <span className="text-sm font-semibold text-gray-800">Analyzed Sources</span>
          {analyzed > 0 && (
            <span className="text-xs text-gray-400">{analyzed} result{analyzed !== 1 ? "s" : ""}</span>
          )}
        </div>

        {analyzed === 0 ? (
          <div className="flex flex-col items-center gap-3 py-16 text-center">
            <span className="flex size-12 items-center justify-center rounded-full bg-violet-50">
              <ShieldAlert className="size-5 text-violet-400" />
            </span>
            <p className="text-sm font-medium text-gray-700">No sources analyzed yet</p>
            <p className="text-xs text-gray-400">
              Paste a finance URL above and click Analyze source to get started.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-left text-xs font-medium uppercase tracking-wide text-gray-400">
                  <th className="px-5 py-3">Source</th>
                  <th className="px-5 py-3">Trust score</th>
                  <th className="px-5 py-3">Verdict</th>
                  <th className="px-5 py-3">Risk tags</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {results.map((r) => (
                  <tr
                    key={r.trace_id}
                    onClick={() => router.push(`/source/${r.trace_id}`)}
                    className="cursor-pointer transition-colors hover:bg-violet-50/60"
                  >
                    <td className="px-5 py-3.5">
                      <div className="font-medium text-gray-900">{r.domain}</div>
                      <div className="max-w-[32ch] truncate text-xs text-gray-400">{r.url}</div>
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-2.5">
                        <span
                          className={`text-xl font-bold tabular-nums leading-none ${scoreColor(r.trust_score)}`}
                        >
                          {r.trust_score}
                        </span>
                        {/* Mini score bar */}
                        <div className="h-1.5 w-16 overflow-hidden rounded-full bg-gray-100">
                          <div
                            className="h-full rounded-full transition-all"
                            style={{
                              width: `${r.trust_score}%`,
                              backgroundColor: scoreHex(r.trust_score),
                            }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3.5">
                      <Badge tone={recTone(r.recommendation)}>
                        {recLabel(r.recommendation)}
                      </Badge>
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="flex flex-wrap gap-1">
                        {r.risk_tags.length === 0 ? (
                          <span className="text-xs text-gray-300">—</span>
                        ) : (
                          r.risk_tags.slice(0, 3).map((t) => (
                            <Badge key={t} tone="danger">{t}</Badge>
                          ))
                        )}
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <ChevronRight className="ml-auto size-4 text-gray-300" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────── //

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium text-gray-600">{label}</span>
      {children}
    </label>
  );
}

function KpiCard({
  label,
  value,
  sub,
  icon,
  accent,
  valueClass = "text-gray-900",
}: {
  label: string;
  value: React.ReactNode;
  sub: string;
  icon: React.ReactNode;
  accent: "violet" | "emerald" | "red";
  valueClass?: string;
}) {
  const bg: Record<typeof accent, string> = {
    violet: "bg-violet-50",
    emerald: "bg-emerald-50",
    red: "bg-red-50",
  };
  return (
    <Card className="border-gray-200 shadow-sm">
      <CardContent className="flex items-start gap-4 pt-5">
        <span className={`flex size-9 shrink-0 items-center justify-center rounded-lg ${bg[accent]}`}>
          {icon}
        </span>
        <div className="min-w-0">
          <p className="text-xs text-gray-500">{label}</p>
          <p className={`mt-0.5 text-2xl font-bold tabular-nums ${valueClass}`}>{value}</p>
          <p className="mt-0.5 text-xs text-gray-400">{sub}</p>
        </div>
      </CardContent>
    </Card>
  );
}

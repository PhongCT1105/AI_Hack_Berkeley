"use client";

import { useEffect, useState } from "react";
import {
  Check,
  Loader2,
  Scale,
  Sparkles,
  Trophy,
  Users,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  createPair,
  getModelStatus,
  nextPair,
  submitLabel,
  trainModel,
} from "@/lib/api";
import { scoreColor, scoreHex } from "@/lib/score-ui";
import type { ComparisonPair, FeedbackForm, ModelStatus } from "@/lib/types";

const CHECKLIST: { key: keyof FeedbackForm; label: string }[] = [
  { key: "domain_trusted",      label: "Domain is trustworthy" },
  { key: "author_credible",     label: "Author is credible" },
  { key: "citations_sufficient",label: "Citations are sufficient" },
  { key: "recency_adequate",    label: "Content is recent enough" },
  { key: "not_clickbait",       label: "Not clickbait or sensational" },
];

const DEFAULT_TASK = "Find reliable, low-risk retirement investment guidance";

export default function Arena() {
  const [task, setTask]         = useState(DEFAULT_TASK);
  const [urlA, setUrlA]         = useState("https://www.sec.gov/investor/pubs/assetallocation.htm");
  const [urlB, setUrlB]         = useState("https://best-stock-picks-now.com/double-your-money");
  const [pair, setPair]         = useState<ComparisonPair | null>(null);
  const [winner, setWinner]     = useState<"a" | "b" | "tie" | null>(null);
  const [checklist, setChecklist] = useState<FeedbackForm>({});
  const [loading, setLoading]   = useState(false);
  const [status, setStatus]     = useState<ModelStatus | null>(null);
  const [msg, setMsg]           = useState<string | null>(null);

  useEffect(() => {
    getModelStatus().then(setStatus).catch(() => {});
    nextPair().then((p) => p && setPair(p)).catch(() => {});
  }, []);

  async function buildPair() {
    setLoading(true); setMsg(null);
    try {
      const p = await createPair(task, urlA, urlB);
      setPair(p); setWinner(null); setChecklist({});
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Failed to build pair");
    } finally { setLoading(false); }
  }

  async function submit() {
    if (!pair || !winner) return;
    setLoading(true);
    try {
      const res = await submitLabel(pair.pair_id, winner, checklist);
      setMsg(`Label recorded — ${res.label_count} total labels for Terac.`);
      const s = await getModelStatus(); setStatus(s);
      const np = await nextPair(); setPair(np);
      setWinner(null); setChecklist({});
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Failed to submit");
    } finally { setLoading(false); }
  }

  async function train() {
    setLoading(true);
    try { setStatus(await trainModel()); }
    finally { setLoading(false); }
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">

      {/* Page header */}
      <div className="mb-7 flex items-start justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2.5 text-xl font-semibold text-gray-900">
            <Scale className="size-5 text-violet-600" />
            Terac Source Comparison Arena
          </h1>
          <p className="mt-0.5 text-sm text-gray-500">
            Human experts pick the more credible source — preference data trains AgentShield&apos;s ranker.
          </p>
        </div>
      </div>

      {/* Model / scorer status */}
      <Card className="mb-6 border-violet-100 bg-violet-50/50 shadow-sm">
        <CardContent className="flex flex-wrap items-center gap-x-8 gap-y-3 pt-5">
          <div className="flex items-center gap-2.5">
            <span className="flex size-8 items-center justify-center rounded-lg bg-violet-100">
              <Sparkles className="size-4 text-violet-600" />
            </span>
            <div>
              <p className="text-xs text-gray-500">Active scorer</p>
              <p className="text-sm font-semibold text-gray-800">{status?.active_scorer ?? "heuristic"}</p>
            </div>
          </div>
          <div className="flex items-center gap-2.5">
            <span className="flex size-8 items-center justify-center rounded-lg bg-violet-100">
              <Users className="size-4 text-violet-600" />
            </span>
            <div>
              <p className="text-xs text-gray-500">Labels collected</p>
              <p className="text-sm font-semibold text-gray-800">{status?.n_labels_used ?? 0}</p>
            </div>
          </div>
          {status?.note && (
            <p className="text-xs text-amber-600 rounded-lg border border-amber-200 bg-amber-50 px-3 py-1.5 max-w-sm">
              {status.note}
            </p>
          )}
          <button
            onClick={train}
            disabled={loading}
            title="Training is wired by a teammate via the Terac API/MCP"
            className="ml-auto flex cursor-pointer items-center gap-2 rounded-lg border border-violet-200 bg-white px-4 py-2 text-sm font-medium text-violet-700 shadow-sm transition-colors hover:bg-violet-50 disabled:opacity-50"
          >
            {loading ? <Loader2 className="size-4 animate-spin" /> : <Trophy className="size-4" />}
            Train ranker
          </button>
        </CardContent>
      </Card>

      {/* Build a pair */}
      <Card className="mb-6 border-gray-200 shadow-sm">
        <CardHeader>
          <CardTitle className="text-gray-900">Build a Comparison Pair</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-600">Task</label>
            <input
              value={task}
              onChange={(e) => setTask(e.target.value)}
              placeholder="Agent task description"
              className="h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none focus:border-violet-400 focus:ring-2 focus:ring-violet-100"
            />
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-gray-600">Source A URL</label>
              <input
                value={urlA}
                onChange={(e) => setUrlA(e.target.value)}
                placeholder="https://trusted-source.com/..."
                className="h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none focus:border-violet-400 focus:ring-2 focus:ring-violet-100"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-gray-600">Source B URL</label>
              <input
                value={urlB}
                onChange={(e) => setUrlB(e.target.value)}
                placeholder="https://unknown-source.com/..."
                className="h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none focus:border-violet-400 focus:ring-2 focus:ring-violet-100"
              />
            </div>
          </div>
          <button
            onClick={buildPair}
            disabled={loading}
            className="flex cursor-pointer items-center gap-2 rounded-lg bg-violet-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-violet-700 disabled:opacity-50"
          >
            {loading ? <Loader2 className="size-4 animate-spin" /> : <Scale className="size-4" />}
            Analyze &amp; compare
          </button>
        </CardContent>
      </Card>

      {/* The arena */}
      {pair && (
        <Card className="border-gray-200 shadow-sm">
          <CardHeader className="border-b border-gray-100 bg-gray-50">
            <CardTitle className="text-gray-900">Which source would you trust?</CardTitle>
            <p className="text-xs text-gray-500">Task: {pair.task}</p>
          </CardHeader>
          <CardContent className="pt-5">
            {/* A vs B */}
            <div className="grid gap-4 md:grid-cols-2">
              <SourceCard
                side="A"
                domain={pair.domain_a}
                url={pair.url_a}
                score={pair.score_a}
                reasons={pair.reasons_a}
                selected={winner === "a"}
                onSelect={() => setWinner("a")}
              />
              <SourceCard
                side="B"
                domain={pair.domain_b}
                url={pair.url_b}
                score={pair.score_b}
                reasons={pair.reasons_b}
                selected={winner === "b"}
                onSelect={() => setWinner("b")}
              />
            </div>

            {/* Tie option */}
            <button
              onClick={() => setWinner("tie")}
              className={`mt-3 w-full cursor-pointer rounded-lg border py-2.5 text-sm font-medium transition-colors ${
                winner === "tie"
                  ? "border-violet-300 bg-violet-50 text-violet-700"
                  : "border-gray-200 text-gray-500 hover:border-gray-300 hover:text-gray-700"
              }`}
            >
              About the same / tie
            </button>

            {/* Feedback checklist */}
            <div className="mt-6">
              <p className="mb-3 text-sm font-semibold text-gray-800 flex items-center gap-2">
                <Check className="size-4 text-violet-500" />
                Annotator checklist
                <span className="text-xs font-normal text-gray-400">(fill for the source you selected)</span>
              </p>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {CHECKLIST.map((c) => (
                  <label
                    key={c.key}
                    className="flex cursor-pointer items-center gap-2.5 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5 text-sm text-gray-700 transition-colors hover:border-violet-200 hover:bg-violet-50/60 has-[:checked]:border-violet-300 has-[:checked]:bg-violet-50 has-[:checked]:text-violet-700"
                  >
                    <input
                      type="checkbox"
                      checked={Boolean(checklist[c.key])}
                      onChange={(e) =>
                        setChecklist((prev) => ({ ...prev, [c.key]: e.target.checked }))
                      }
                      className="size-4 accent-violet-600"
                    />
                    {c.label}
                  </label>
                ))}
              </div>
              <textarea
                value={checklist.free_text ?? ""}
                onChange={(e) =>
                  setChecklist((prev) => ({ ...prev, free_text: e.target.value }))
                }
                placeholder="Optional: why is the model right or wrong here?"
                rows={2}
                className="mt-3 w-full rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 outline-none focus:border-violet-400 focus:ring-2 focus:ring-violet-100"
              />
            </div>

            {/* Submit */}
            <div className="mt-5 flex items-center gap-4 border-t border-gray-100 pt-4">
              <button
                onClick={submit}
                disabled={loading || !winner}
                className="flex cursor-pointer items-center gap-2 rounded-lg bg-violet-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {loading ? <Loader2 className="size-4 animate-spin" /> : <Trophy className="size-4" />}
                Submit label
              </button>
              {msg && (
                <span className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs text-emerald-700">
                  {msg}
                </span>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ── Source choice card ───────────────────────────────────────────────────── //

function SourceCard({
  side,
  domain,
  url,
  score,
  reasons,
  selected,
  onSelect,
}: {
  side: string;
  domain: string;
  url: string;
  score: number;
  reasons: string[];
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className={`cursor-pointer rounded-xl border p-5 text-left transition-all ${
        selected
          ? "border-violet-400 bg-violet-50 shadow-md shadow-violet-100"
          : "border-gray-200 bg-white hover:border-violet-200 hover:bg-violet-50/40"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <span
            className={`flex size-6 items-center justify-center rounded-full text-xs font-bold ${
              selected ? "bg-violet-600 text-white" : "bg-gray-100 text-gray-500"
            }`}
          >
            {side}
          </span>
          <span className="text-xs font-medium uppercase tracking-wide text-gray-400">
            Source {side}
          </span>
        </div>
        {/* Score badge */}
        <div className="flex items-center gap-1.5">
          <span
            className={`text-2xl font-bold tabular-nums ${scoreColor(score)}`}
          >
            {score}
          </span>
          <div className="h-12 w-1.5 overflow-hidden rounded-full bg-gray-100">
            <div
              className="w-full rounded-full transition-all"
              style={{
                height: `${score}%`,
                marginTop: `${100 - score}%`,
                backgroundColor: scoreHex(score),
              }}
            />
          </div>
        </div>
      </div>

      <p className="mt-3 font-semibold text-gray-900">{domain}</p>
      <p className="truncate text-xs text-gray-400">{url}</p>

      <ul className="mt-3 space-y-1">
        {reasons.map((r, i) => (
          <li key={i} className="flex items-start gap-1.5 text-xs text-gray-500">
            <span className="mt-1 size-1 shrink-0 rounded-full bg-gray-300" />
            {r}
          </li>
        ))}
      </ul>

      {selected && (
        <div className="mt-3 flex items-center gap-1 text-xs font-medium text-violet-600">
          <Check className="size-3.5" /> Selected as more credible
        </div>
      )}
    </button>
  );
}

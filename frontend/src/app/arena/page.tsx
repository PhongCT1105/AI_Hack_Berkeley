"use client";

import { useEffect, useState } from "react";
import { Loader2, Scale, Sparkles, Trophy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  createPair,
  getModelStatus,
  nextPair,
  submitLabel,
  trainModel,
} from "@/lib/api";
import { scoreColor } from "@/lib/score-ui";
import type { ComparisonPair, FeedbackForm, ModelStatus } from "@/lib/types";

const CHECKLIST: { key: keyof FeedbackForm; label: string }[] = [
  { key: "domain_trusted", label: "Domain is trustworthy" },
  { key: "author_credible", label: "Author is credible" },
  { key: "citations_sufficient", label: "Citations are sufficient" },
  { key: "recency_adequate", label: "Content is recent enough" },
  { key: "not_clickbait", label: "Not clickbait / sensational" },
];

const DEFAULT_TASK = "Find reliable, low-risk retirement investment guidance";

export default function Arena() {
  const [task, setTask] = useState(DEFAULT_TASK);
  const [urlA, setUrlA] = useState("https://www.sec.gov/investor/pubs/assetallocation.htm");
  const [urlB, setUrlB] = useState("https://best-stock-picks-now.com/double-your-money");
  const [pair, setPair] = useState<ComparisonPair | null>(null);
  const [winner, setWinner] = useState<"a" | "b" | "tie" | null>(null);
  const [checklist, setChecklist] = useState<FeedbackForm>({});
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<ModelStatus | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    getModelStatus().then(setStatus).catch(() => {});
    nextPair().then((p) => p && setPair(p)).catch(() => {});
  }, []);

  async function buildPair() {
    setLoading(true);
    setMsg(null);
    try {
      const p = await createPair(task, urlA, urlB);
      setPair(p);
      setWinner(null);
      setChecklist({});
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Failed to build pair");
    } finally {
      setLoading(false);
    }
  }

  async function submit() {
    if (!pair || !winner) return;
    setLoading(true);
    try {
      const res = await submitLabel(pair.pair_id, winner, checklist);
      setMsg(`Label recorded — ${res.label_count} total for Terac.`);
      const s = await getModelStatus();
      setStatus(s);
      const np = await nextPair();
      setPair(np);
      setWinner(null);
      setChecklist({});
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Failed to submit label");
    } finally {
      setLoading(false);
    }
  }

  async function train() {
    setLoading(true);
    try {
      setStatus(await trainModel());
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <Scale className="size-6 text-sky-400" /> Terac Arena
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Pairwise source-comparison arena. Human experts pick the more credible source and fill a
            checklist — the preference data that trains AgentShield&apos;s ranker beyond its heuristic
            baseline.
          </p>
        </div>
      </div>

      {/* Model status banner */}
      <Card className="mb-6">
        <CardContent className="flex flex-wrap items-center gap-x-6 gap-y-2 pt-5 text-sm">
          <span className="flex items-center gap-2">
            <Sparkles className="size-4 text-amber-400" />
            Active scorer:{" "}
            <Badge tone={status?.loaded ? "success" : "info"}>
              {status?.active_scorer ?? "heuristic"}
            </Badge>
          </span>
          <span className="text-muted-foreground">
            Labels collected: <span className="text-foreground">{status?.n_labels_used ?? 0}</span>
          </span>
          {status?.note && <span className="text-xs text-amber-400/90">{status.note}</span>}
          <Button
            variant="outline"
            size="sm"
            className="ml-auto"
            onClick={train}
            disabled={loading}
            title="Training is wired by a teammate via the Terac API/MCP — see trainer.py"
          >
            {loading ? <Loader2 className="animate-spin" /> : <Trophy />}
            Train ranker
          </Button>
        </CardContent>
      </Card>

      {/* Pair builder */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Build a comparison</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <input
            value={task}
            onChange={(e) => setTask(e.target.value)}
            placeholder="Task"
            className="h-9 w-full rounded-lg border border-input bg-background px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
          />
          <div className="grid gap-3 md:grid-cols-2">
            <input
              value={urlA}
              onChange={(e) => setUrlA(e.target.value)}
              placeholder="Source A URL"
              className="h-9 w-full rounded-lg border border-input bg-background px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
            />
            <input
              value={urlB}
              onChange={(e) => setUrlB(e.target.value)}
              placeholder="Source B URL"
              className="h-9 w-full rounded-lg border border-input bg-background px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
            />
          </div>
          <Button onClick={buildPair} disabled={loading}>
            {loading ? <Loader2 className="animate-spin" /> : <Scale />}
            Build pair
          </Button>
        </CardContent>
      </Card>

      {/* The arena */}
      {pair && (
        <Card>
          <CardHeader>
            <CardTitle>Which source would you trust?</CardTitle>
            <p className="text-xs text-muted-foreground">Task: {pair.task}</p>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-2">
              <SourceChoice
                side="A"
                domain={pair.domain_a}
                url={pair.url_a}
                score={pair.score_a}
                reasons={pair.reasons_a}
                selected={winner === "a"}
                onSelect={() => setWinner("a")}
              />
              <SourceChoice
                side="B"
                domain={pair.domain_b}
                url={pair.url_b}
                score={pair.score_b}
                reasons={pair.reasons_b}
                selected={winner === "b"}
                onSelect={() => setWinner("b")}
              />
            </div>
            <button
              onClick={() => setWinner("tie")}
              className={`mt-3 w-full rounded-lg border py-2 text-sm transition-colors ${
                winner === "tie"
                  ? "border-sky-500/40 bg-sky-500/10 text-sky-400"
                  : "border-border text-muted-foreground hover:text-foreground"
              }`}
            >
              About the same / tie
            </button>

            {/* Checklist */}
            <div className="mt-5">
              <div className="mb-2 text-sm font-medium">Annotator checklist (for the winner)</div>
              <div className="grid gap-2 sm:grid-cols-2">
                {CHECKLIST.map((c) => (
                  <label
                    key={c.key}
                    className="flex cursor-pointer items-center gap-2 rounded-lg border border-border/60 px-3 py-2 text-sm"
                  >
                    <input
                      type="checkbox"
                      checked={Boolean(checklist[c.key])}
                      onChange={(e) =>
                        setChecklist((prev) => ({ ...prev, [c.key]: e.target.checked }))
                      }
                      className="size-4 accent-sky-500"
                    />
                    {c.label}
                  </label>
                ))}
              </div>
              <textarea
                value={checklist.free_text ?? ""}
                onChange={(e) => setChecklist((prev) => ({ ...prev, free_text: e.target.value }))}
                placeholder="Optional: why is the model right or wrong here?"
                rows={2}
                className="mt-2 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
              />
            </div>

            <div className="mt-4 flex items-center gap-3">
              <Button onClick={submit} disabled={loading || !winner}>
                {loading ? <Loader2 className="animate-spin" /> : <Trophy />}
                Submit label
              </Button>
              {msg && <span className="text-xs text-muted-foreground">{msg}</span>}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function SourceChoice({
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
      className={`rounded-xl border p-4 text-left transition-colors ${
        selected ? "border-sky-500/50 bg-sky-500/5" : "border-border hover:bg-muted/40"
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Source {side}
        </span>
        <span className={`text-xl font-bold tabular-nums ${scoreColor(score)}`}>{score}</span>
      </div>
      <div className="mt-1 font-medium">{domain}</div>
      <div className="truncate text-xs text-muted-foreground">{url}</div>
      <ul className="mt-3 space-y-1 text-xs text-muted-foreground">
        {reasons.map((r, i) => (
          <li key={i}>• {r}</li>
        ))}
      </ul>
    </button>
  );
}

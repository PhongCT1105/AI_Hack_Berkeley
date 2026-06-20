"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  Check,
  FileText,
  Gauge,
  ShieldCheck,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useResults } from "@/lib/api";
import { recTone, scoreColor } from "@/lib/score-ui";

export default function SourceDetail() {
  const params = useParams<{ id: string }>();
  const r = useResults().find((x) => x.trace_id === params.id) ?? null;

  if (r === null) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-16 text-center">
        <p className="text-sm text-muted-foreground">
          This result isn&apos;t in the current session.
        </p>
        <Link href="/" className="mt-3 inline-block text-sm text-sky-400 hover:underline">
          ← Back to dashboard
        </Link>
      </div>
    );
  }

  const f = r.source_features;
  const capsule = r.evidence_capsule;
  const reduction =
    capsule.token_estimate_before > 0
      ? Math.max(0, Math.round((1 - capsule.token_estimate_after / capsule.token_estimate_before) * 100))
      : 0;

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <Link
        href="/"
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Dashboard
      </Link>

      {/* Header / recommendation banner */}
      <Card className="mb-6 overflow-hidden">
        <div className="flex flex-col gap-4 p-6 md:flex-row md:items-center md:justify-between">
          <div className="min-w-0">
            <div className="text-lg font-semibold">{r.domain}</div>
            <a
              href={r.url}
              target="_blank"
              rel="noreferrer"
              className="block max-w-[60ch] truncate text-sm text-muted-foreground hover:text-foreground"
            >
              {r.url}
            </a>
            <div className="mt-1 text-xs text-muted-foreground">Task: {r.task}</div>
          </div>
          <div className="flex items-center gap-6">
            <div className="text-center">
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                <Gauge className="size-3.5" /> Trust score
              </div>
              <div className={`text-5xl font-bold tabular-nums ${scoreColor(r.trust_score)}`}>
                {r.trust_score}
              </div>
            </div>
            <Badge tone={recTone(r.recommendation)} className="px-3 py-1.5 text-sm">
              {r.recommendation === "USE" ? "USE" : r.recommendation === "CAUTION" ? "USE WITH CAUTION" : "DO NOT USE"}
            </Badge>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-border bg-muted/30 px-6 py-2 text-xs text-muted-foreground">
          <span>scorer: <span className="text-foreground">{r.scorer_mode}</span></span>
          <span>collector: <span className="text-foreground">{f.collector_mode}</span></span>
          <span>extractor: <span className="text-foreground">{f.extractor_mode}</span></span>
          <span>latency: <span className="text-foreground">{r.latency_ms}ms</span></span>
          <span>trace: <span className="font-mono text-foreground">{r.trace_id.slice(0, 8)}</span></span>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Verdicts */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="size-4 text-sky-400" /> Verdicts
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {r.verdicts.map((v, i) => (
              <div key={i} className="flex items-start gap-3 rounded-lg border border-border/60 p-3">
                <span
                  className={`mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full ${
                    v.passed ? "bg-emerald-500/15 text-emerald-400" : "bg-rose-500/15 text-rose-400"
                  }`}
                >
                  {v.passed ? <Check className="size-3.5" /> : <X className="size-3.5" />}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium capitalize">{v.dimension}</span>
                    <span className="text-xs text-muted-foreground">weight {v.weight}</span>
                  </div>
                  <p className="text-xs text-muted-foreground">{v.detail}</p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Risk reasons + features */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Risk reasons</CardTitle>
            </CardHeader>
            <CardContent>
              {r.risk_tags.length === 0 ? (
                <p className="text-sm text-muted-foreground">No risk tags raised.</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {r.risk_tags.map((t) => (
                    <Badge key={t} tone="danger">{t}</Badge>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Source signals</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <Signal label="HTTPS" ok={f.https} />
              <Signal label="Author" ok={f.has_author} />
              <Signal label="Citations" ok={f.has_citations} extra={`${f.citation_count}`} />
              <Signal label="Domain" ok={f.domain_listed !== "block"} extra={f.domain_listed ?? "neutral"} />
              <Metric label="Ad density" value={`${Math.round(f.ad_density * 100)}%`} bad={f.ad_density > 0.5} />
              <Metric label="Clickbait" value={`${Math.round(f.clickbait_score * 100)}%`} bad={f.clickbait_score > 0.6} />
              <Metric label="Words" value={`${f.word_count}`} />
              <Metric label="Recency" value={f.recency_days == null ? "—" : `${f.recency_days}d`} />
            </CardContent>
          </Card>
        </div>

        {/* Claims */}
        <Card>
          <CardHeader>
            <CardTitle>Claims found</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {r.claims.length === 0 ? (
              <p className="text-sm text-muted-foreground">No notable claims extracted.</p>
            ) : (
              r.claims.map((c, i) => (
                <div key={i} className="rounded-lg border border-border/60 p-3">
                  <p className="text-sm">&ldquo;{c.text}&rdquo;</p>
                  <div className="mt-2 flex items-center gap-2">
                    <Badge tone={c.supported ? "success" : "danger"}>
                      {c.supported ? "Supported" : "Unsupported"}
                    </Badge>
                    {c.evidence_snippet && (
                      <span className="truncate text-xs text-muted-foreground">{c.evidence_snippet}</span>
                    )}
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* Credibility Capsule */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="size-4 text-sky-400" /> Credibility Capsule
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="mb-3 flex items-center gap-3 text-xs">
              <span className="rounded-md bg-muted px-2 py-1 tabular-nums">
                {capsule.token_estimate_before} tok
              </span>
              <span className="text-muted-foreground">→</span>
              <span className="rounded-md bg-emerald-500/10 px-2 py-1 tabular-nums text-emerald-400">
                {capsule.token_estimate_after} tok
              </span>
              <Badge tone="info">−{reduction}% context</Badge>
              <span className="ml-auto text-muted-foreground">{capsule.method}</span>
            </div>
            <p className="rounded-lg border border-border/60 bg-muted/20 p-3 text-sm leading-relaxed">
              {capsule.compressed_text || "—"}
            </p>
            {capsule.key_reasons.length > 0 && (
              <ul className="mt-3 space-y-1 text-xs text-muted-foreground">
                {capsule.key_reasons.map((reason, i) => (
                  <li key={i}>• {reason}</li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      {r.degradations.length > 0 && (
        <p className="mt-6 text-xs text-muted-foreground">
          Degradations this run: {r.degradations.join(" · ")}
        </p>
      )}
    </div>
  );
}

function Signal({ label, ok, extra }: { label: string; ok: boolean; extra?: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className={`flex items-center gap-1 ${ok ? "text-emerald-400" : "text-rose-400"}`}>
        {ok ? <Check className="size-3.5" /> : <X className="size-3.5" />}
        {extra && <span className="text-xs text-muted-foreground">{extra}</span>}
      </span>
    </div>
  );
}

function Metric({ label, value, bad }: { label: string; value: string; bad?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className={bad ? "text-rose-400" : "text-foreground"}>{value}</span>
    </div>
  );
}

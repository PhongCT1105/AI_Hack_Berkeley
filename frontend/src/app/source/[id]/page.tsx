"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  Check,
  ChevronRight,
  Cpu,
  ExternalLink,
  FileText,
  ShieldCheck,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useResults } from "@/lib/api";
import { recLabel, scoreHex } from "@/lib/score-ui";

export default function SourceDetail() {
  const params = useParams<{ id: string }>();
  const r = useResults().find((x) => x.trace_id === params.id) ?? null;

  if (r === null) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-20 text-center">
        <span className="flex size-14 mx-auto items-center justify-center rounded-full bg-secondary">
          <ShieldCheck className="size-6 text-primary" />
        </span>
        <p className="mt-4 text-base font-medium text-foreground">Result not found in this session</p>
        <p className="mt-1 text-sm text-muted-foreground">Navigate back to the dashboard and analyze a source first.</p>
        <Link
          href="/"
          className="mt-5 inline-flex items-center gap-1.5 text-sm font-semibold text-primary hover:brightness-110"
        >
          <ArrowLeft className="size-4" /> Back to Dashboard
        </Link>
      </div>
    );
  }

  const f = r.source_features;
  const capsule = r.evidence_capsule;
  const citation = r.citation_assessment;
  const reduction =
    capsule.token_estimate_before > 0
      ? Math.max(0, Math.round((1 - capsule.token_estimate_after / capsule.token_estimate_before) * 100))
      : 0;

  const recColors = {
    USE:     { bg: "bg-emerald-50", border: "border-emerald-200", text: "text-emerald-700" },
    CAUTION: { bg: "bg-amber-50",   border: "border-amber-200",   text: "text-amber-700"  },
    AVOID:   { bg: "bg-red-50",     border: "border-red-200",     text: "text-red-700"    },
  }[r.recommendation];

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">

      {/* Breadcrumb */}
      <nav className="mb-5 flex items-center gap-1.5 text-sm text-muted-foreground">
        <Link href="/" className="hover:text-primary transition-colors">Dashboard</Link>
        <ChevronRight className="size-3.5" />
        <span className="text-foreground font-medium">{r.domain}</span>
      </nav>

      {/* Hero card */}
      <Card className="mb-6 overflow-hidden">
        {/* Top section */}
        <div className="flex flex-col gap-6 p-6 md:flex-row md:items-center">

          {/* Score ring */}
          <ScoreRing score={r.trust_score} />

          {/* Domain + meta */}
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-start gap-3">
              <div>
                <h1 className="text-xl font-bold text-foreground">{r.domain}</h1>
                <a
                  href={r.url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-primary transition-colors"
                >
                  <span className="max-w-[52ch] truncate">{r.url}</span>
                  <ExternalLink className="size-3 shrink-0" />
                </a>
              </div>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              Task: <span className="text-foreground">{r.task}</span>
            </p>

            {/* Recommendation badge */}
            <div className={`mt-4 inline-flex items-center gap-2 rounded border px-4 py-2 ${recColors.bg} ${recColors.border}`}>
              <span className={`text-sm font-semibold ${recColors.text}`}>
                {recLabel(r.recommendation)}
              </span>
            </div>
          </div>
        </div>

        {/* Metadata bar */}
        <div className="flex flex-wrap gap-x-5 gap-y-1 border-t border-border bg-muted px-6 py-2.5 text-xs text-muted-foreground">
          {[
            ["Scorer",    r.scorer_mode],
            ["Collector", f.collector_mode],
            ["Extractor", f.extractor_mode],
            ["Latency",   `${r.latency_ms}ms`],
            ["Trace",     r.trace_id.slice(0, 12)],
          ].map(([k, v]) => (
            <span key={k}>
              {k}:{" "}
              <span className="font-mono text-foreground">{v}</span>
            </span>
          ))}
        </div>
      </Card>

      {/* Content grid */}
      <div className="grid gap-5 lg:grid-cols-2">

        {/* Verdicts */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-foreground">
              <ShieldCheck className="size-4 text-primary" />
              Credibility Verdicts
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {r.verdicts.map((v, i) => (
              <div
                key={i}
                className="flex items-start gap-3 rounded border border-border bg-muted/60 p-3 hover:border-foreground/20 transition-colors"
              >
                <span
                  className={`mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full ${
                    v.passed ? "bg-emerald-100 text-emerald-600" : "bg-red-100 text-red-600"
                  }`}
                >
                  {v.passed ? <Check className="size-3.5" /> : <X className="size-3.5" />}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium capitalize text-foreground">{v.dimension}</span>
                    <span className="shrink-0 text-xs text-muted-foreground">weight {v.weight}</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">{v.detail}</p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Right column: Risk + Source signals */}
        <div className="space-y-5">
          <Card>
            <CardHeader>
              <CardTitle className="text-foreground">Risk Flags</CardTitle>
            </CardHeader>
            <CardContent>
              {r.risk_tags.length === 0 ? (
                <div className="flex items-center gap-2 text-sm text-emerald-600">
                  <Check className="size-4" /> No risk flags raised.
                </div>
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
              <CardTitle className="flex items-center gap-2 text-foreground">
                <FileText className="size-4 text-primary" />
                Citation eligibility
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm">
              {!citation?.available ? (
                <p className="text-muted-foreground">No trained citation classifier is available for this result.</p>
              ) : (
                <div className="space-y-1.5">
                  <p className={citation.eligible ? "font-medium text-emerald-700" : "font-medium text-amber-700"}>
                    {citation.eligible ? "Eligible for citation" : "Held for review"}
                  </p>
                  <p className="text-muted-foreground">
                    Usability confidence {Math.round((citation.usable_probability ?? 0) * 100)}%.
                    Required threshold {Math.round((citation.threshold ?? 0) * 100)}%.
                  </p>
                  {citation.model_version && <p className="font-mono text-xs text-muted-foreground">Model {citation.model_version}</p>}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-foreground">
                <Cpu className="size-4 text-primary" />
                Source Signals
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-x-4 gap-y-2.5 text-sm">
                <Signal label="HTTPS"     ok={f.https} />
                <Signal label="Author"    ok={f.has_author} />
                <Signal label="Citations" ok={f.has_citations} extra={`${f.citation_count}`} />
                <Signal
                  label="Domain"
                  ok={f.domain_listed !== "block"}
                  extra={f.domain_listed ?? "neutral"}
                />
                <Metric label="Ad density" value={`${Math.round(f.ad_density * 100)}%`}      bad={f.ad_density > 0.5} />
                <Metric label="Clickbait"  value={`${Math.round(f.clickbait_score * 100)}%`} bad={f.clickbait_score > 0.6} />
                <Metric label="Words"      value={`${f.word_count.toLocaleString()}`} />
                <Metric label="Recency"    value={f.recency_days == null ? "—" : `${f.recency_days}d`} />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Claims */}
        <Card>
          <CardHeader>
            <CardTitle className="text-foreground">Extracted Claims</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {r.claims.length === 0 ? (
              <p className="text-sm text-muted-foreground">No notable claims extracted from this source.</p>
            ) : (
              r.claims.map((c, i) => (
                <div key={i} className="rounded border border-border bg-muted/60 p-3">
                  <p className="text-sm text-foreground">&ldquo;{c.text}&rdquo;</p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <Badge tone={c.supported ? "success" : "danger"}>
                      {c.supported ? "Evidence found" : "Unsupported"}
                    </Badge>
                    {c.evidence_snippet && (
                      <span className="truncate text-xs text-muted-foreground/70">{c.evidence_snippet}</span>
                    )}
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* Credibility Capsule */}
        <Card className="overflow-hidden">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-foreground">
              <FileText className="size-4 text-primary" />
              Credibility Capsule
              <Badge tone="purple" className="ml-auto">Token Company</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {/* Token compression stats */}
            <div className="mb-4 flex items-center gap-2.5">
              <div className="rounded border border-border bg-muted px-3 py-2 text-center">
                <p className="text-xs text-muted-foreground">Before</p>
                <p className="font-mono text-sm font-semibold text-foreground">{capsule.token_estimate_before} tok</p>
              </div>
              <div className="text-muted-foreground/50">→</div>
              <div className="rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-center">
                <p className="text-xs text-emerald-600">After</p>
                <p className="font-mono text-sm font-semibold text-emerald-700">{capsule.token_estimate_after} tok</p>
              </div>
              {reduction > 0 && (
                <Badge tone="success" className="ml-1">−{reduction}% context saved</Badge>
              )}
              <span className="ml-auto text-xs text-muted-foreground">{capsule.method}</span>
            </div>

            <p className="console-theme rounded p-3.5 text-sm leading-relaxed font-mono">
              {capsule.compressed_text || "—"}
            </p>
            {capsule.key_reasons.length > 0 && (
              <ul className="mt-3 space-y-1.5">
                {capsule.key_reasons.map((reason, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-muted-foreground">
                    <span className="mt-0.5 size-1.5 shrink-0 rounded-full bg-primary/60" />
                    {reason}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      {r.degradations.length > 0 && (
        <div className="mt-5 rounded border border-amber-100 bg-amber-50 px-4 py-2.5 text-xs text-amber-700">
          <span className="font-medium">Fallbacks used:</span> {r.degradations.join(" · ")}
        </div>
      )}
    </div>
  );
}

// ── Score ring (SVG) ─────────────────────────────────────────────────────── //

function ScoreRing({ score }: { score: number }) {
  const r = 38;
  const circ = 2 * Math.PI * r;
  const fill = (score / 100) * circ;
  const color = scoreHex(score);
  const label = score >= 70 ? "Trusted" : score >= 40 ? "Caution" : "Avoid";

  return (
    <div className="flex shrink-0 flex-col items-center gap-1">
      <svg width="100" height="100" viewBox="0 0 100 100" className="-rotate-90">
        <circle cx="50" cy="50" r={r} fill="none" stroke="var(--muted)" strokeWidth="9" />
        <circle
          cx="50" cy="50" r={r}
          fill="none"
          stroke={color}
          strokeWidth="9"
          strokeDasharray={`${fill} ${circ - fill}`}
          strokeLinecap="round"
          style={{ transition: "stroke-dasharray 0.5s ease" }}
        />
      </svg>
      {/* Score number overlaid */}
      <div className="absolute flex flex-col items-center" style={{ marginTop: 22 }}>
        <span className="text-2xl font-bold tabular-nums" style={{ color }}>{score}</span>
      </div>
      <span className="text-xs font-medium text-muted-foreground -mt-1">{label}</span>
    </div>
  );
}

// ── Row helpers ───────────────────────────────────────────────────────────── //

function Signal({ label, ok, extra }: { label: string; ok: boolean; extra?: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-muted-foreground">{label}</span>
      <span className={`flex items-center gap-1 font-medium ${ok ? "text-emerald-600" : "text-red-500"}`}>
        {ok ? <Check className="size-3.5" /> : <X className="size-3.5" />}
        {extra && <span className="text-xs text-muted-foreground/70">{extra}</span>}
      </span>
    </div>
  );
}

function Metric({ label, value, bad }: { label: string; value: string; bad?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-muted-foreground">{label}</span>
      <span className={`font-medium ${bad ? "text-red-500" : "text-foreground"}`}>{value}</span>
    </div>
  );
}

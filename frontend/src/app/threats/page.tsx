"use client";

import { AlertTriangle, Ban } from "lucide-react";
import { ComicBadge, toneForRiskTag } from "@/components/comic/comic-badge";
import { ComicBurst } from "@/components/comic/comic-burst";
import { ComicPanel, ComicPanelHeader } from "@/components/comic/comic-panel";
import { ComicPageHeader } from "@/components/comic/comic-page-header";
import { MascotAvatar } from "@/components/comic/mascot-avatar";
import { useResults } from "@/lib/api";
import type { ScoreResponse } from "@/lib/types";

const FINANCE_BLOCKLIST: { domain: string; reputation: number }[] = [
  { domain: "best-stock-picks-now.com", reputation: 0.08 },
  { domain: "crypto-millionaire-secrets.com", reputation: 0.05 },
  { domain: "guaranteed-returns-blog.com", reputation: 0.07 },
  { domain: "hot-penny-stocks.net", reputation: 0.06 },
  { domain: "affiliate-finance-deals.com", reputation: 0.12 },
];

type ResultWithOptionalTime = ScoreResponse & {
  analyzed_at?: string | number | null;
  created_at?: string | number | null;
  scored_at?: string | number | null;
  timestamp?: string | number | null;
};

interface DomainThreat {
  domain: string;
  riskTags: string[];
  trustScore: number | null;
  timesSeen: number;
  firstSeen: number | null;
}

function normalizeDomain(input?: string | null): string | null {
  if (!input || typeof input !== "string") return null;
  const value = input.trim().toLowerCase();
  if (!value) return null;

  try {
    const hostname = value.includes("://")
      ? new URL(value).hostname
      : new URL(`https://${value}`).hostname;
    return hostname.replace(/^www\./, "") || null;
  } catch {
    const cleaned = value
      .replace(/^https?:\/\//, "")
      .split("/")[0]
      .split("?")[0]
      .split("#")[0]
      .replace(/^www\./, "");
    return cleaned && /^[a-z0-9.-]+$/i.test(cleaned) ? cleaned : null;
  }
}

function domainForResult(result: ScoreResponse): string {
  return normalizeDomain(result.domain) ?? normalizeDomain(result.url) ?? "unknown domain";
}

function timestampForResult(result: ScoreResponse): number | null {
  const withTime = result as ResultWithOptionalTime;
  const raw =
    withTime.analyzed_at ?? withTime.created_at ?? withTime.scored_at ?? withTime.timestamp ?? null;
  if (raw === null || raw === undefined || raw === "") return null;

  const time = typeof raw === "number" ? raw : Date.parse(raw);
  return Number.isFinite(time) ? time : null;
}

function formatFirstSeen(time: number | null): string {
  if (time === null) return "—";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(time));
}

function safeScore(score: unknown): number | null {
  return typeof score === "number" && Number.isFinite(score)
    ? Math.max(0, Math.min(100, Math.round(score)))
    : null;
}

function groupThreats(results: ScoreResponse[]): DomainThreat[] {
  const groups = new Map<string, DomainThreat & { scoreTotal: number; scoreCount: number }>();

  results.forEach((result) => {
    if (result.recommendation !== "AVOID") return;

    const domain = domainForResult(result);
    const score = safeScore(result.trust_score);
    const firstSeen = timestampForResult(result);
    const tags = Array.isArray(result.risk_tags) ? result.risk_tags.filter(Boolean) : [];
    const existing = groups.get(domain);

    if (!existing) {
      groups.set(domain, {
        domain,
        riskTags: [...new Set(tags)],
        trustScore: score,
        timesSeen: 1,
        firstSeen,
        scoreTotal: score ?? 0,
        scoreCount: score === null ? 0 : 1,
      });
      return;
    }

    existing.timesSeen += 1;
    existing.riskTags = [...new Set([...existing.riskTags, ...tags])];
    if (score !== null) {
      existing.scoreTotal += score;
      existing.scoreCount += 1;
      existing.trustScore = Math.round(existing.scoreTotal / existing.scoreCount);
    }
    if (firstSeen !== null) {
      existing.firstSeen =
        existing.firstSeen === null ? firstSeen : Math.min(existing.firstSeen, firstSeen);
    }
  });

  return [...groups.values()]
    .map((group) => ({
      domain: group.domain,
      riskTags: group.riskTags,
      trustScore: group.trustScore,
      timesSeen: group.timesSeen,
      firstSeen: group.firstSeen,
    }))
    .sort((a, b) => b.timesSeen - a.timesSeen || a.domain.localeCompare(b.domain));
}

function topRiskTags(results: ScoreResponse[]) {
  const counts = new Map<string, number>();
  results.forEach((result) => {
    if (result.recommendation !== "AVOID") return;
    const tags = Array.isArray(result.risk_tags) ? result.risk_tags : [];
    tags.filter(Boolean).forEach((tag) => counts.set(tag, (counts.get(tag) ?? 0) + 1));
  });

  return [...counts.entries()]
    .map(([tag, count]) => ({ tag, count }))
    .sort((a, b) => b.count - a.count || a.tag.localeCompare(b.tag))
    .slice(0, 5);
}

function toneForScore(score: number | null): "red" | "orange" | "yellow" {
  if (score === null) return "red";
  if (score <= 20) return "red";
  if (score <= 45) return "orange";
  return "yellow";
}

export default function ThreatFeedPage() {
  const results = useResults();
  const flagged = results.filter((result) => result.recommendation === "AVOID");
  const threats = groupThreats(results);
  const commonTags = topRiskTags(results);
  const maxTagCount = Math.max(...commonTags.map((item) => item.count), 1);

  return (
    <div className="comic-zone min-h-[calc(100vh-3.5rem)] px-6 py-10">
      <div className="mx-auto max-w-7xl">
        <ComicPageHeader
          title="Threat Feed!"
          subtitle="Captain Ddoski's session monitor for finance sources agents should AVOID."
          pose="warningStop"
          right={
            <>
              <ComicBurst value={flagged.length} tone={flagged.length > 0 ? "red" : "green"} size="lg" />
              <span className="font-comic text-sm text-(--comic-ink)">
                flagged
                <br />
                source{flagged.length === 1 ? "" : "s"}
              </span>
            </>
          }
        />

        {flagged.length === 0 ? (
          <ComicPanel className="flex flex-col items-center gap-3 py-16 text-center">
            <MascotAvatar pose="goodLike" size="xl" />
            <p className="font-comic text-xl text-(--comic-ink)">All clear, citizen!</p>
            <p className="max-w-md text-xs text-muted-foreground">
              Sources marked AVOID will appear here as grouped domain threats after analysis.
            </p>
          </ComicPanel>
        ) : (
          <div className="grid gap-8">
            <div>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="font-comic text-2xl text-(--comic-ink)">Flagged Domains</h2>
                <span className="comic-pop bg-white px-2.5 py-1 text-[11px] text-(--comic-ink)">
                  {threats.length} domain{threats.length === 1 ? "" : "s"}
                </span>
              </div>
              <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                {threats.map((threat, i) => (
                  <ComicPanel
                    key={threat.domain}
                    tilt={i % 2 === 0}
                    className="flex flex-col gap-3 p-4"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="truncate font-comic text-lg text-(--comic-ink)">
                          {threat.domain}
                        </div>
                        <div className="text-[11px] font-semibold text-muted-foreground">
                          seen {threat.timesSeen}x &middot; first {formatFirstSeen(threat.firstSeen)}
                        </div>
                      </div>
                      <ComicBurst
                        value={threat.trustScore ?? "—"}
                        tone={toneForScore(threat.trustScore)}
                        size="sm"
                      />
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {threat.riskTags.length === 0 ? (
                        <span className="text-xs text-muted-foreground/60">No risk tags</span>
                      ) : (
                        threat.riskTags.slice(0, 4).map((tag) => (
                          <ComicBadge key={tag} tone={toneForRiskTag(tag)}>
                            {tag}
                          </ComicBadge>
                        ))
                      )}
                    </div>
                  </ComicPanel>
                ))}
              </div>
            </div>

            <div className="grid gap-6 lg:grid-cols-[1fr_0.9fr]">
              <ComicPanel>
                <ComicPanelHeader color="var(--comic-blue)">
                  <span className="flex items-center gap-2 font-comic text-lg text-white">
                    <AlertTriangle className="size-4" />
                    Common patterns
                  </span>
                </ComicPanelHeader>
                <div className="p-5">
                  {commonTags.length === 0 ? (
                    <p className="rounded border-2 border-(--comic-ink) bg-(--comic-yellow)/30 px-3 py-6 text-center text-sm font-semibold text-(--comic-ink)">
                      No risk tags were attached to flagged sources.
                    </p>
                  ) : (
                    <div className="space-y-4">
                      {commonTags.map((item) => {
                        const percent = Math.round((item.count / flagged.length) * 100);
                        const width = `${Math.max(6, (item.count / maxTagCount) * 100)}%`;
                        const tone = toneForRiskTag(item.tag);

                        return (
                          <div key={item.tag}>
                            <div className="mb-1.5 flex items-center justify-between gap-3">
                              <span className="font-comic text-sm text-(--comic-ink)">{item.tag}</span>
                              <span className="text-xs font-semibold text-muted-foreground">
                                {percent}% of flagged sources
                              </span>
                            </div>
                            <div className="h-3 overflow-hidden rounded-full border-2 border-(--comic-ink) bg-white">
                              <div
                                className="h-full"
                                style={{ width, backgroundColor: `var(--comic-${tone})` }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </ComicPanel>

              <ComicPanel>
                <ComicPanelHeader color="var(--comic-red)">
                  <span className="flex items-center gap-2 font-comic text-lg text-white">
                    <Ban className="size-4" />
                    Finance blocklist domains
                  </span>
                </ComicPanelHeader>
                <ul className="divide-y-2 divide-(--comic-ink)/10">
                  {FINANCE_BLOCKLIST.map((item) => (
                    <li
                      key={item.domain}
                      className="flex items-center justify-between gap-3 px-5 py-3.5"
                    >
                      <span className="font-semibold text-(--comic-ink)">{item.domain}</span>
                      <ComicBadge tone="red">{Math.round(item.reputation * 100)}%</ComicBadge>
                    </li>
                  ))}
                </ul>
              </ComicPanel>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

"use client";

import { AlertTriangle, Ban, Radar, ShieldAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useResults } from "@/lib/api";
import { scoreColor, scoreHex } from "@/lib/score-ui";
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

export default function ThreatFeedPage() {
  const results = useResults();
  const flagged = results.filter((result) => result.recommendation === "AVOID");
  const threats = groupThreats(results);
  const commonTags = topRiskTags(results);
  const maxTagCount = Math.max(...commonTags.map((item) => item.count), 1);

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="mb-7 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2.5 text-xl font-semibold text-gray-900">
            <Radar className="size-5 text-violet-600" />
            Threat Feed
          </h1>
          <p className="mt-0.5 text-sm text-gray-500">
            Session monitor for finance sources AgentShield recommends agents avoid.
          </p>
        </div>
        <Badge tone={flagged.length > 0 ? "danger" : "success"}>
          {flagged.length} flagged source{flagged.length === 1 ? "" : "s"}
        </Badge>
      </div>

      {flagged.length === 0 ? (
        <Card className="border-violet-100 bg-white shadow-sm">
          <CardContent className="flex flex-col items-center gap-3 py-16 text-center">
            <span className="flex size-12 items-center justify-center rounded-full bg-violet-50">
              <ShieldAlert className="size-5 text-violet-400" />
            </span>
            <p className="text-sm font-medium text-gray-700">No flagged sources yet</p>
            <p className="max-w-md text-xs text-gray-400">
              Sources marked AVOID will appear here as grouped domain threats after analysis.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6">
          <Card className="overflow-hidden border-gray-200 shadow-sm">
            <div className="flex items-center justify-between border-b border-gray-100 bg-gray-50 px-5 py-3">
              <span className="text-sm font-semibold text-gray-800">Flagged Domains</span>
              <span className="text-xs text-gray-400">
                {threats.length} domain{threats.length === 1 ? "" : "s"}
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 text-left text-xs font-medium uppercase tracking-wide text-gray-400">
                    <th className="px-5 py-3">Domain</th>
                    <th className="px-5 py-3">Risk tags</th>
                    <th className="px-5 py-3">Trust score</th>
                    <th className="px-5 py-3">Times seen</th>
                    <th className="px-5 py-3">First seen</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {threats.map((threat) => (
                    <tr key={threat.domain} className="transition-colors hover:bg-violet-50/60">
                      <td className="px-5 py-3.5">
                        <div className="font-medium text-gray-900">{threat.domain}</div>
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex max-w-lg flex-wrap gap-1">
                          {threat.riskTags.length === 0 ? (
                            <span className="text-xs text-gray-300">—</span>
                          ) : (
                            threat.riskTags.slice(0, 4).map((tag) => (
                              <Badge key={tag} tone="danger">
                                {tag}
                              </Badge>
                            ))
                          )}
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        {threat.trustScore === null ? (
                          <span className="text-xs text-gray-300">—</span>
                        ) : (
                          <div className="flex items-center gap-2.5">
                            <span
                              className={`text-xl font-bold tabular-nums leading-none ${scoreColor(
                                threat.trustScore,
                              )}`}
                            >
                              {threat.trustScore}
                            </span>
                            <div className="h-1.5 w-16 overflow-hidden rounded-full bg-gray-100">
                              <div
                                className="h-full rounded-full"
                                style={{
                                  width: `${threat.trustScore}%`,
                                  backgroundColor: scoreHex(threat.trustScore),
                                }}
                              />
                            </div>
                          </div>
                        )}
                      </td>
                      <td className="px-5 py-3.5 font-medium tabular-nums text-gray-700">
                        {threat.timesSeen}
                      </td>
                      <td className="px-5 py-3.5 text-gray-500">
                        {formatFirstSeen(threat.firstSeen)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <div className="grid gap-6 lg:grid-cols-[1fr_0.9fr]">
            <Card className="border-gray-200 shadow-sm">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-gray-900">
                  <AlertTriangle className="size-4 text-red-500" />
                  Common patterns
                </CardTitle>
              </CardHeader>
              <CardContent>
                {commonTags.length === 0 ? (
                  <p className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-6 text-center text-sm text-gray-400">
                    No risk tags were attached to flagged sources.
                  </p>
                ) : (
                  <div className="space-y-4">
                    {commonTags.map((item) => {
                      const percent = Math.round((item.count / flagged.length) * 100);
                      const width = `${Math.max(6, (item.count / maxTagCount) * 100)}%`;

                      return (
                        <div key={item.tag}>
                          <div className="mb-1.5 flex items-center justify-between gap-3">
                            <span className="text-sm font-medium text-gray-800">{item.tag}</span>
                            <span className="text-xs text-gray-500">
                              {percent}% of flagged sources
                            </span>
                          </div>
                          <div className="h-2.5 overflow-hidden rounded-full bg-gray-100">
                            <div
                              className="h-full rounded-full bg-linear-to-r from-red-500 to-violet-600"
                              style={{ width }}
                            />
                          </div>
                          <p className="mt-1 text-xs text-gray-400">
                            {item.tag}: {percent}% of flagged sources
                          </p>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="overflow-hidden border-gray-200 shadow-sm">
              <CardHeader className="border-b border-gray-100 bg-gray-50">
                <CardTitle className="flex items-center gap-2 text-gray-900">
                  <Ban className="size-4 text-red-500" />
                  Finance blocklist domains
                </CardTitle>
              </CardHeader>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100 text-left text-xs font-medium uppercase tracking-wide text-gray-400">
                      <th className="px-5 py-3">Domain</th>
                      <th className="px-5 py-3">Prior</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {FINANCE_BLOCKLIST.map((item) => (
                      <tr key={item.domain}>
                        <td className="px-5 py-3.5 font-medium text-gray-900">{item.domain}</td>
                        <td className="px-5 py-3.5 text-red-600 tabular-nums">
                          {Math.round(item.reputation * 100)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}

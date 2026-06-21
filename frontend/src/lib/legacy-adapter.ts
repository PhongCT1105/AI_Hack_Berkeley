// Adapts the original /api/score-source ScoreResponse (used by the "/" dashboard,
// which still runs the real collector/extractor/ranker pipeline) into the
// DemoSource shape so /source/[id] can render either a demo-run result or a
// real single-source analysis with the same UI.
import type { DemoRecommendation, DemoSource, Quality, ScoreResponse } from "./types";

const REC_MAP: Record<ScoreResponse["recommendation"], DemoRecommendation> = {
  USE: "cite",
  CAUTION: "use_with_caution",
  AVOID: "do_not_cite",
};

export function adaptScoreResponse(r: ScoreResponse): DemoSource {
  const f = r.source_features;
  const before = r.evidence_capsule.token_estimate_before;
  const after = r.evidence_capsule.token_estimate_after;
  const compressionPct = before > 0 ? Math.round((1 - after / before) * 1000) / 10 : 0;

  const evidenceQuality: Quality = f.has_citations && f.citation_count >= 3 ? "strong" : f.has_citations ? "medium" : "weak";
  const citationQuality: Quality = f.citation_count >= 5 ? "strong" : f.citation_count >= 1 ? "medium" : "weak";

  return {
    id: r.trace_id,
    url: r.url,
    domain: r.domain,
    title: `Live analysis — ${r.domain}`,
    sourceType: f.domain_listed === "allow" ? "financial_news" : f.domain_listed === "block" ? "promotional_blog" : "general_web",
    trustScore: r.trust_score,
    baseScore: r.trust_score,
    trainedScore: r.trust_score,
    recommendation: REC_MAP[r.recommendation],
    riskTags: r.risk_tags,
    claims: r.claims.map((c) => c.text),
    evidenceQuality,
    citationQuality,
    capsule: {
      compressed_text: r.evidence_capsule.compressed_text,
      key_reasons: r.evidence_capsule.key_reasons,
      method: r.evidence_capsule.method,
    },
    rawTokens: before,
    capsuleTokens: after,
    compressionPct,
  };
}

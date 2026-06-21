// Client-side mock data + classifier for the Captain America demo pipeline.
// Mirrors backend/app/api/demo.py so the UI behaves identically whether the
// FastAPI backend is reachable or not — see lib/api.ts for the fetch-then-fallback
// wiring. TODO(real-pipeline): once Browserbase + the trained ranker are wired,
// this file becomes dead code and runDemo() always hits the real backend.
import type {
  ArenaPair,
  DemoRecommendation,
  DemoSource,
  EvalMetrics,
  Quality,
} from "./types";

export const DEFAULT_DEMO_TASK =
  "Which sources should an AI agent cite when analyzing Nvidia revenue growth?";

export const DEFAULT_DEMO_URLS = [
  "https://investor.nvidia.com/financial-info/quarterly-results/",
  "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=nvidia",
  "https://www.reuters.com/technology/nvidia-revenue-growth-ai-chips",
  "https://best-stock-picks-now.com/nvidia-going-to-the-moon",
];

const NEWS_DOMAINS = [
  "reuters.com", "bloomberg.com", "wsj.com", "ft.com", "cnbc.com",
  "marketwatch.com", "investopedia.com", "barrons.com",
];
const HYPE_KEYWORDS = ["stock-picks", "moon", "secrets", "guaranteed", "10x", "millionaire", "hot-penny"];
const ALLOW_DOMAINS = [
  "sec.gov", "consumerfinance.gov", "finra.org", "fdic.gov", "federalreserve.gov",
  "treasury.gov", "bls.gov", "bea.gov", "investor.gov", "irs.gov", "fidelity.com",
  "vanguard.com", "morningstar.com", "reuters.com", "bloomberg.com", "wsj.com", "ft.com",
];
const BLOCK_DOMAINS = ["best-stock-picks-now.com"];

function domainOf(url: string): string {
  try {
    const host = new URL(url.includes("://") ? url : `https://${url}`).hostname;
    return host.toLowerCase().replace(/^www\./, "");
  } catch {
    return url.toLowerCase();
  }
}

function sourceType(domain: string, url: string): string {
  const lower = url.toLowerCase();
  if (domain.endsWith(".gov")) return "regulatory_filing";
  if (lower.includes("investor.") || lower.includes("ir.") || lower.includes("/investor")) return "company_ir";
  if (NEWS_DOMAINS.some((n) => domain === n || domain.endsWith(`.${n}`))) return "financial_news";
  if (HYPE_KEYWORDS.some((k) => lower.includes(k))) return "promotional_blog";
  return "general_web";
}

function reputationOf(domain: string): { reputation: number; listed: "allow" | "block" | null } {
  if (BLOCK_DOMAINS.some((d) => domain === d || domain.endsWith(`.${d}`))) return { reputation: 0.1, listed: "block" };
  if (ALLOW_DOMAINS.some((d) => domain === d || domain.endsWith(`.${d}`))) return { reputation: 0.9, listed: "allow" };
  return { reputation: 0.5, listed: null };
}

function titleFor(domain: string, type: string): string {
  switch (type) {
    case "regulatory_filing": return `SEC EDGAR filing — ${domain}`;
    case "company_ir": return `Investor Relations — ${domain}`;
    case "financial_news": return `Market coverage — ${domain}`;
    case "promotional_blog": return `"Guaranteed returns" blog post — ${domain}`;
    default: return `Web page — ${domain}`;
  }
}

function hashId(input: string): string {
  let h = 0;
  for (let i = 0; i < input.length; i++) h = (h * 31 + input.charCodeAt(i)) >>> 0;
  return h.toString(16).padStart(8, "0") + input.length.toString(16);
}

export function classifyUrl(url: string, task: string, idx: number): DemoSource {
  const domain = domainOf(url);
  const type = sourceType(domain, url);
  const { reputation, listed } = reputationOf(domain);

  let baseScore = Math.round(reputation * 100);
  let riskTags: string[] = [];
  let evidenceQuality: Quality = "medium";
  let citationQuality: Quality = "medium";

  if (type === "regulatory_filing") {
    baseScore = Math.max(baseScore, 92);
    riskTags = ["primary_source"];
    evidenceQuality = citationQuality = "strong";
  } else if (type === "company_ir") {
    baseScore = Math.max(baseScore, 78);
    riskTags = ["primary_source", "commercial_pressure"];
    evidenceQuality = "strong"; citationQuality = "medium";
  } else if (type === "financial_news") {
    baseScore = Math.max(baseScore, 74);
    riskTags = ["reputable_publisher"];
    evidenceQuality = citationQuality = "strong";
  } else if (type === "promotional_blog" || listed === "block") {
    baseScore = Math.min(baseScore, 14);
    riskTags = ["unsupported_prediction", "weak_citations", "anonymous_author", "sensational_language", "commercial_pressure"];
    evidenceQuality = citationQuality = "weak";
  } else {
    baseScore = 50;
    riskTags = ["weak_citations"];
    evidenceQuality = "medium"; citationQuality = "weak";
  }

  let trainedScore: number;
  if (baseScore >= 70) trainedScore = Math.min(99, baseScore + 8);
  else if (baseScore <= 30) trainedScore = Math.max(1, baseScore - 8);
  else trainedScore = baseScore;

  const trustScore = Math.round(trainedScore * 0.65 + baseScore * 0.35);

  let recommendation: DemoRecommendation;
  if (trustScore >= 70) recommendation = "cite";
  else if (trustScore >= 40) recommendation = "use_with_caution";
  else recommendation = "do_not_cite";

  const claimsByType: Record<string, string[]> = {
    regulatory_filing: [`Official filing data relevant to: ${task}`],
    company_ir: [`Company-reported figures relevant to: ${task}`],
    financial_news: [`Third-party reported analysis relevant to: ${task}`],
    promotional_blog: [`Unverified prediction about: ${task}`],
    general_web: [`General claim relevant to: ${task}`],
  };

  const rawTokensByType: Record<string, number> = {
    regulatory_filing: 21400,
    company_ir: 15800,
    financial_news: 9200,
    promotional_blog: 6100,
    general_web: 8000,
  };
  const rawTokens = rawTokensByType[type];
  const capsuleTokens = Math.max(120, Math.round(rawTokens * (recommendation === "cite" ? 0.03 : 0.05)));
  const compressionPct = Math.round((1 - capsuleTokens / rawTokens) * 1000) / 10;

  return {
    id: hashId(`${url}|${idx}`),
    url,
    domain,
    title: titleFor(domain, type),
    sourceType: type,
    trustScore,
    baseScore,
    trainedScore,
    recommendation,
    riskTags,
    claims: claimsByType[type],
    evidenceQuality,
    citationQuality,
    capsule: {
      compressed_text: `${titleFor(domain, type)}. Recommendation: ${recommendation.replace(/_/g, " ")}. Key reasons: ${riskTags.length ? riskTags.join(", ") : "none flagged"}.`,
      key_reasons: riskTags.length ? riskTags : ["reputable_publisher"],
      method: "mock_synthetic",
    },
    rawTokens,
    capsuleTokens,
    compressionPct,
  };
}

export const MOCK_DEMO_SOURCES: DemoSource[] = DEFAULT_DEMO_URLS.map((u, i) =>
  classifyUrl(u, DEFAULT_DEMO_TASK, i),
);

export const MOCK_EVAL: EvalMetrics = {
  base_accuracy: 78.0,
  trained_accuracy: 94.0,
  improvement_pct: 16.0,
  held_out_examples: 10,
  human_preference_match: 94.0,
  bad_source_filtering_precision: 97.0,
  cite_do_not_cite_accuracy: 91.0,
  avg_token_reduction_pct: 96.0,
  raw_tokens_example: 18420,
  capsule_tokens_example: 742,
  examples: [
    { task: "Cite a source for Nvidia data-center revenue", source_a: "investor.nvidia.com", source_b: "best-stock-picks-now.com", human_preferred: "a", base_predicted: "a", trained_predicted: "a", result: "both_right" },
    { task: "Cite a source for Fed rate decision impact", source_a: "federalreserve.gov", source_b: "hot-penny-stocks.net", human_preferred: "a", base_predicted: "a", trained_predicted: "a", result: "both_right" },
    { task: "Cite a source for retirement allocation guidance", source_a: "vanguard.com", source_b: "guaranteed-returns-blog.com", human_preferred: "a", base_predicted: "b", trained_predicted: "a", result: "base_wrong_trained_right" },
    { task: "Cite a source for quarterly earnings beat", source_a: "reuters.com", source_b: "crypto-millionaire-secrets.com", human_preferred: "a", base_predicted: "a", trained_predicted: "a", result: "both_right" },
    { task: "Cite a source for SEC filing detail", source_a: "sec.gov", source_b: "affiliate-finance-deals.com", human_preferred: "a", base_predicted: "a", trained_predicted: "a", result: "both_right" },
    { task: "Cite a source for analyst price target", source_a: "morningstar.com", source_b: "best-stock-picks-now.com", human_preferred: "a", base_predicted: "b", trained_predicted: "a", result: "base_wrong_trained_right" },
    { task: "Cite a source for inflation data", source_a: "bls.gov", source_b: "hot-penny-stocks.net", human_preferred: "a", base_predicted: "a", trained_predicted: "a", result: "both_right" },
    { task: "Cite a source for company 10-K risk factors", source_a: "sec.gov", source_b: "unknown-finance-blog.net", human_preferred: "a", base_predicted: "b", trained_predicted: "a", result: "base_wrong_trained_right" },
    { task: "Cite a source for IPO valuation context", source_a: "wsj.com", source_b: "affiliate-finance-deals.com", human_preferred: "a", base_predicted: "a", trained_predicted: "a", result: "both_right" },
    { task: "Cite a source for dividend yield claim", source_a: "fidelity.com", source_b: "crypto-millionaire-secrets.com", human_preferred: "a", base_predicted: "a", trained_predicted: "a", result: "both_right" },
  ],
};

// Annotation queue for the Terac Source Duel Arena — cycles, but the UI
// displays progress against a target of 50 (the human-labeling story).
export const ARENA_ANNOTATION_TARGET = 50;

const ARENA_TASKS: [string, string, string][] = [
  ["Research low-risk retirement investments", "vanguard.com", "guaranteed-returns-blog.com"],
  ["Cite Nvidia's quarterly revenue figures", "investor.nvidia.com", "best-stock-picks-now.com"],
  ["Find guidance on Fed rate decisions", "federalreserve.gov", "hot-penny-stocks.net"],
  ["Research SEC filing details for a company", "sec.gov", "affiliate-finance-deals.com"],
  ["Evaluate an analyst price target claim", "morningstar.com", "crypto-millionaire-secrets.com"],
  ["Check inflation data for a financial report", "bls.gov", "unknown-finance-blog.net"],
  ["Verify a dividend yield claim", "fidelity.com", "best-stock-picks-now.com"],
  ["Research an IPO valuation", "wsj.com", "hot-penny-stocks.net"],
];

function arenaCardFor(domain: string, task: string) {
  const isGood = ALLOW_DOMAINS.includes(domain) || domain.endsWith(".gov") || domain.startsWith("investor.");
  return {
    domain,
    title: titleFor(domain, isGood ? "financial_news" : "promotional_blog"),
    capsuleSummary: isGood
      ? `Primary or reputable data relevant to: ${task}`
      : `Unverified, promotional claim relevant to: ${task}`,
    riskTags: isGood ? ["reputable_publisher"] : ["unsupported_prediction", "sensational_language"],
    citationQuality: (isGood ? "strong" : "weak") as Quality,
  };
}

export const MOCK_ARENA_QUEUE: ArenaPair[] = ARENA_TASKS.map(([task, a, b], i) => ({
  pair_id: hashId(`${task}|${a}|${b}|${i}`),
  task,
  a: arenaCardFor(a, task),
  b: arenaCardFor(b, task),
}));

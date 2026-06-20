// TypeScript mirrors of the FastAPI `ScoreResponse` contract (app/schemas/score.py).

export type Recommendation = "USE" | "CAUTION" | "AVOID";

export interface Claim {
  text: string;
  supported: boolean;
  evidence_snippet: string | null;
  confidence: number;
}

export interface Verdict {
  dimension: string;
  passed: boolean;
  detail: string;
  weight: number;
}

export interface SourceFeatures {
  https: boolean;
  has_author: boolean;
  has_citations: boolean;
  citation_count: number;
  ad_density: number;
  domain_reputation: number;
  domain_listed: string | null;
  clickbait_score: number;
  recency_days: number | null;
  word_count: number;
  outbound_link_count: number;
  collector_mode: string;
  extractor_mode: string;
}

export interface FeatureContribution {
  feature: string;
  value: number | boolean | string | null;
  points: number;
}

export interface EvidenceCapsule {
  compressed_text: string;
  key_reasons: string[];
  token_estimate_before: number;
  token_estimate_after: number;
  method: string;
}

export interface ScoreResponse {
  url: string;
  task: string;
  domain: string;
  trust_score: number;
  recommendation: Recommendation;
  risk_tags: string[];
  verdicts: Verdict[];
  claims: Claim[];
  evidence_capsule: EvidenceCapsule;
  source_features: SourceFeatures;
  contributions: FeatureContribution[];
  scorer_mode: string;
  degradations: string[];
  latency_ms: number;
  trace_id: string;
}

// Terac arena
export interface ComparisonPair {
  pair_id: string;
  task: string;
  url_a: string;
  url_b: string;
  domain_a: string;
  domain_b: string;
  score_a: number;
  score_b: number;
  reasons_a: string[];
  reasons_b: string[];
  labeled: boolean;
}

export interface FeedbackForm {
  author_credible?: boolean | null;
  citations_sufficient?: boolean | null;
  recency_adequate?: boolean | null;
  not_clickbait?: boolean | null;
  domain_trusted?: boolean | null;
  free_text?: string | null;
}

export interface ModelStatus {
  loaded: boolean;
  trained_at: string | null;
  n_labels_used: number;
  coefficients: Record<string, number> | null;
  active_scorer: string;
  note: string | null;
}

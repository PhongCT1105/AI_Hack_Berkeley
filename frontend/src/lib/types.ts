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

export interface CitationAssessment {
  available: boolean;
  usable_probability: number | null;
  threshold: number | null;
  eligible: boolean | null;
  model_version: string | null;
  error: string | null;
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
  citation_assessment: CitationAssessment;
  evidence_capsule: EvidenceCapsule;
  source_features: SourceFeatures;
  contributions: FeatureContribution[];
  scorer_mode: string;
  degradations: string[];
  latency_ms: number;
  trace_id: string;
}


// Demo pipeline
export type DemoRecommendation = "cite" | "use_with_caution" | "do_not_cite";
export type Quality = "strong" | "medium" | "weak";

export interface DemoSource {
  id: string;
  url: string;
  domain: string;
  title: string;
  sourceType: string;
  trustScore: number;
  baseScore: number;
  trainedScore: number;
  recommendation: DemoRecommendation;
  riskTags: string[];
  claims: string[];
  evidenceQuality: Quality;
  citationQuality: Quality;
  capsule: {
    compressed_text: string;
    key_reasons: string[];
    method: string;
  };
  rawTokens: number;
  capsuleTokens: number;
  compressionPct: number;
}

export interface EvalExample {
  task: string;
  source_a: string;
  source_b: string;
  human_preferred: "a" | "b";
  base_predicted: "a" | "b";
  trained_predicted: "a" | "b";
  result: "both_right" | "base_wrong_trained_right" | "both_wrong";
}

export interface EvalMetrics {
  base_accuracy: number;
  trained_accuracy: number;
  improvement_pct: number;
  held_out_examples: number;
  human_preference_match: number;
  bad_source_filtering_precision: number;
  cite_do_not_cite_accuracy: number;
  avg_token_reduction_pct: number;
  raw_tokens_example: number;
  capsule_tokens_example: number;
  examples: EvalExample[];
}

export interface ArenaSource {
  domain: string;
  title: string;
  capsuleSummary: string;
  riskTags: string[];
  citationQuality: Quality;
}

export interface ArenaPair {
  pair_id: string;
  task: string;
  a: ArenaSource;
  b: ArenaSource;
}

export interface ResearchResponse {
  prompt: string;
  search_query: string;
  discovered_count: number;
  inspected_count: number;
  agent_mode: string;
  search_mode: string;
  discovery_error: string | null;
  answer: string;
  cited_sources: ScoreResponse[];
  rejected_sources: ScoreResponse[];
}

// Mirrors the SSE events streamed by GET /api/workflow/stream
// (app/services/workflow_demo.py) — each one is a real backend step, not a
// scripted replay.
export type WorkflowEvent =
  | { type: "narrative"; text: string }
  | { type: "tool_call"; tool: string; input: Record<string, unknown> }
  | { type: "tool_result"; tool: string; output: Record<string, unknown> }
  | { type: "final"; output: ResearchResponse }
  | { type: "done" };

// Mirrors the SSE events streamed by GET /api/comparison/stream
// (app/services/comparison_demo.py) — heuristic + no compression ("weak")
// vs. compression + a freshly-fit candidate model ("better"), scored on the
// same collected page so only the pipeline differs, not the input data.
export interface ComparisonSide {
  label: "weak" | "better";
  domain: string;
  trust_score: number;
  recommendation: Recommendation;
  risk_tags: string[];
  scorer_mode: string;
  input_tokens: number;
  output_tokens: number;
  compression: { compression_ratio: number; total_tokens_saved: number; total_input_tokens: number; total_output_tokens: number; calls: number; page_chars_sent?: number } | null;
  evidence_preview: string;
  evidence_chars: number;
  latency_ms: number;
}

export interface ComparisonSummary {
  sources_compared: number;
  totals: {
    weak_input_tokens: number;
    weak_output_tokens: number;
    better_input_tokens: number;
    better_output_tokens: number;
  };
  weak_total_tokens: number;
  better_total_tokens: number;
  tokens_saved: number;
  disagreements: { url: string; domain: string; weak: string; better: string }[];
  candidate_model: {
    trained?: boolean;
    note?: string;
    n_labels_used?: number;
    holdout_accuracy?: number;
    baseline_accuracy?: number;
    holdout_size?: number;
    beats_baseline?: boolean;
  };
  discovery_error?: string | null;
}

export type ComparisonEvent =
  | { type: "narrative"; text: string }
  | { type: "tool_result"; tool?: string; output: Record<string, unknown> }
  | { type: "row"; url: string; domain: string; weak: ComparisonSide; better: ComparisonSide }
  | { type: "row_error"; url: string; error: string }
  | { type: "summary"; output: ComparisonSummary }
  | { type: "done" };

// Score → color/tone mapping — calibrated for a white/light background.
import type { Recommendation } from "./types";

type Tone = "neutral" | "success" | "warning" | "danger" | "info" | "purple";

export function scoreTone(score: number): Tone {
  if (score >= 70) return "success";
  if (score >= 40) return "warning";
  return "danger";
}

/** Tailwind text-color class for the score number itself. */
export function scoreColor(score: number): string {
  if (score >= 70) return "text-emerald-600";
  if (score >= 40) return "text-amber-600";
  return "text-red-600";
}

/** Hex value for SVG strokes / inline styles. */
export function scoreHex(score: number): string {
  if (score >= 70) return "#059669"; // emerald-600
  if (score >= 40) return "#d97706"; // amber-600
  return "#dc2626";                  // red-600
}

export function recTone(rec: Recommendation): Tone {
  return rec === "USE" ? "success" : rec === "CAUTION" ? "warning" : "danger";
}

export function recLabel(rec: Recommendation): string {
  return rec === "USE" ? "USE" : rec === "CAUTION" ? "USE WITH CAUTION" : "DO NOT USE";
}

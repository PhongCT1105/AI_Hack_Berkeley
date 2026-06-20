// Shared score -> color/label mapping used across all screens.
import type { Recommendation } from "./types";

type Tone = "neutral" | "success" | "warning" | "danger" | "info";

export function scoreTone(score: number): Tone {
  if (score >= 70) return "success";
  if (score >= 40) return "warning";
  return "danger";
}

export function scoreColor(score: number): string {
  if (score >= 70) return "text-emerald-400";
  if (score >= 40) return "text-amber-400";
  return "text-rose-400";
}

export function recTone(rec: Recommendation): Tone {
  return rec === "USE" ? "success" : rec === "CAUTION" ? "warning" : "danger";
}

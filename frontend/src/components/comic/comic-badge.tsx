import { cn } from "@/lib/utils";

export type ComicTone = "red" | "yellow" | "blue" | "orange" | "purple" | "green";

const TONE_BG: Record<ComicTone, string> = {
  red: "bg-(--comic-red) text-white",
  yellow: "bg-(--comic-yellow) text-(--comic-ink)",
  blue: "bg-(--comic-blue) text-white",
  orange: "bg-(--comic-orange) text-white",
  purple: "bg-(--comic-purple) text-white",
  green: "bg-(--comic-green) text-(--comic-ink)",
};

/** A "POW!"-style pill badge: bold ink border, offset shadow, saturated fill. */
export function ComicBadge({
  tone = "red",
  className,
  ...props
}: React.ComponentProps<"span"> & { tone?: ComicTone }) {
  return (
    <span
      className={cn(
        "comic-pop px-2.5 py-1 text-[11px] font-comic",
        TONE_BG[tone],
        className,
      )}
      {...props}
    />
  );
}

const RISK_TAG_TONES: Record<string, ComicTone> = {
  "untrusted domain": "red",
  "no author": "orange",
  "no citations": "orange",
  "insecure transport": "purple",
  "high ad density": "purple",
  "clickbait title": "red",
  "stale content": "yellow",
  "thin content": "yellow",
  "citation classifier rejected": "red",
};

export function toneForRiskTag(tag: string): ComicTone {
  return RISK_TAG_TONES[tag] ?? "blue";
}

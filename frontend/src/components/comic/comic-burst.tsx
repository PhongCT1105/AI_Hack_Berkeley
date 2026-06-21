import { cn } from "@/lib/utils";
import type { ComicTone } from "./comic-badge";

const TONE_BG: Record<ComicTone, string> = {
  red: "bg-(--comic-red) text-white",
  yellow: "bg-(--comic-yellow) text-(--comic-ink)",
  blue: "bg-(--comic-blue) text-white",
  orange: "bg-(--comic-orange) text-white",
  purple: "bg-(--comic-purple) text-white",
  green: "bg-(--comic-green) text-(--comic-ink)",
};

/** A round comic "impact" badge for a single headline number (trust score,
 * flagged count). Wiggles gently so the page doesn't feel static. */
export function ComicBurst({
  value,
  tone = "blue",
  size = "md",
  className,
}: {
  value: React.ReactNode;
  tone?: ComicTone;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const dims = size === "lg" ? "size-20 text-2xl" : size === "sm" ? "size-10 text-sm" : "size-14 text-lg";
  return (
    <span
      className={cn(
        "comic-burst comic-wiggle font-bold tabular-nums",
        dims,
        TONE_BG[tone],
        className,
      )}
    >
      {value}
    </span>
  );
}

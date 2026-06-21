import { cn } from "@/lib/utils";
import { MascotAvatar } from "./mascot-avatar";
import type { MascotPose } from "./mascot";

/** The same bold ink-panel banner used on the Threat Feed, factored out so
 * every route can open with the same Captain Ddoski comic beat instead of a
 * plain text heading. */
export function ComicPageHeader({
  title,
  subtitle,
  pose = "standing",
  bg = "var(--comic-yellow)",
  light = false,
  right,
  className,
}: {
  title: string;
  subtitle?: string;
  pose?: MascotPose;
  bg?: string;
  /** Use white text/subtitle — for darker accent backgrounds (e.g. comic-blue, comic-red). */
  light?: boolean;
  right?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn("comic-panel mb-8 flex flex-wrap items-center justify-between gap-4 px-6 py-5", className)}
      style={{ backgroundColor: bg }}
    >
      <div className="flex items-center gap-3">
        <MascotAvatar pose={pose} size="lg" />
        <div>
          <h1 className={cn("font-comic text-3xl leading-none sm:text-4xl", light ? "text-white" : "text-(--comic-ink)")}>
            {title}
          </h1>
          {subtitle && (
            <p className={cn("mt-1 text-sm font-semibold", light ? "text-white/90" : "text-(--comic-ink)/80")}>
              {subtitle}
            </p>
          )}
        </div>
      </div>
      {right && <div className="flex items-center gap-3">{right}</div>}
    </div>
  );
}

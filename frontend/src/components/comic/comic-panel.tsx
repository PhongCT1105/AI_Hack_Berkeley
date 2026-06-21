import { cn } from "@/lib/utils";

/** Comic-book panel: thick ink border, offset drop shadow, white paper fill.
 * Drop-in replacement for `Card` on mascot-themed pages. */
export function ComicPanel({ className, tilt = false, ...props }: React.ComponentProps<"div"> & { tilt?: boolean }) {
  return (
    <div
      className={cn("comic-panel overflow-hidden bg-white", tilt && "comic-panel-tilt", className)}
      {...props}
    />
  );
}

export function ComicPanelHeader({
  className,
  color = "var(--comic-ink)",
  ...props
}: React.ComponentProps<"div"> & { color?: string }) {
  return (
    <div
      className={cn("flex items-center justify-between gap-3 border-b-[3px] border-(--comic-ink) px-5 py-3", className)}
      style={{ backgroundColor: color }}
      {...props}
    />
  );
}

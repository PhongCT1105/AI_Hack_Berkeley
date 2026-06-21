import { cn } from "@/lib/utils";

type Tone = "neutral" | "success" | "warning" | "danger" | "info" | "purple";

const tones: Record<Tone, string> = {
  neutral: "border-border       bg-muted        text-muted-foreground",
  success: "border-emerald-200 bg-emerald-50   text-emerald-700",
  warning: "border-amber-200   bg-amber-50     text-amber-700",
  danger:  "border-red-200     bg-red-50       text-red-700",
  info:    "border-sky-200     bg-sky-50       text-sky-700",
  purple:  "border-primary/20  bg-secondary    text-primary",
};

export function Badge({
  tone = "neutral",
  className,
  ...props
}: React.ComponentProps<"span"> & { tone?: Tone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded border px-2.5 py-0.5 text-[11px] font-bold tracking-wide whitespace-nowrap",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}

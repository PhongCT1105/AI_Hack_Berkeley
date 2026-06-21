import Image from "next/image";
import { cn } from "@/lib/utils";
import { MASCOT, type MascotPose } from "./mascot";

const SIZES = {
  xs: 20,
  sm: 28,
  md: 40,
  lg: 64,
  xl: 112,
} as const;

/** Drop-in replacement for a circular icon badge (tool-call markers, status
 * dots, empty states) using a Captain Ddoski action pose instead of a
 * generic lucide icon. */
export function MascotAvatar({
  pose,
  size = "sm",
  ring = true,
  className,
}: {
  pose: MascotPose;
  size?: keyof typeof SIZES;
  ring?: boolean;
  className?: string;
}) {
  const px = SIZES[size];
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-white",
        ring && "ring-2 ring-(--comic-ink)/80",
        className,
      )}
      style={{ width: px, height: px }}
    >
      <Image
        src={MASCOT[pose]}
        alt=""
        width={px * 2}
        height={px * 2}
        className="size-full scale-125 object-cover"
        unoptimized
      />
    </span>
  );
}

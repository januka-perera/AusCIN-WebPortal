import { cn } from "@/lib/cn";

export type StatusTone = "positive" | "neutral" | "caution" | "restricted";

const dotStyles: Record<StatusTone, string> = {
  positive: "bg-accent",
  neutral: "bg-muted",
  caution: "bg-secondary-accent",
  restricted: "bg-foreground",
};

type StatusLabelProps = {
  label: string;
  tone?: StatusTone;
  className?: string;
};

/**
 * A quiet text-and-dot indicator for operating status (active, offline,
 * processing) and visibility class (public, embargoed, restricted).
 * Deliberately not a filled pill badge, to stay editorial rather than SaaS.
 */
export function StatusLabel({ label, tone = "neutral", className }: StatusLabelProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 text-meta uppercase tracking-label text-muted",
        className,
      )}
    >
      <span aria-hidden="true" className={cn("h-1.5 w-1.5 rounded-full", dotStyles[tone])} />
      {label}
    </span>
  );
}

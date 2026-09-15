import Link from "next/link";
import { cn } from "@/lib/cn";

type EmptyStateProps = {
  title: string;
  description?: string;
  action?: { label: string; href: string };
  className?: string;
};

/** Shown when a filtered view (search, archive, gallery) has no results. */
export function EmptyState({ title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-start gap-3 rounded-sm border border-dashed border-border px-6 py-12",
        className,
      )}
    >
      <p className="font-display text-heading-md text-foreground">{title}</p>
      {description && <p className="max-w-md text-small text-muted">{description}</p>}
      {action && (
        <Link href={action.href} className="text-small font-medium text-accent hover:text-accent-strong">
          {action.label} <span aria-hidden="true">&rarr;</span>
        </Link>
      )}
    </div>
  );
}

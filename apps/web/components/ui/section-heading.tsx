import Link from "next/link";
import { cn } from "@/lib/cn";

type SectionHeadingProps = {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: { label: string; href: string };
  /** Use "h1" when this is a page's only top-level heading. Defaults to "h2". */
  level?: "h1" | "h2";
};

export function SectionHeading({
  eyebrow,
  title,
  description,
  action,
  level = "h2",
}: SectionHeadingProps) {
  const Heading = level;
  return (
    <div className="flex flex-col gap-4 border-b border-border pb-6 sm:flex-row sm:items-end sm:justify-between">
      <div>
        {eyebrow && <p className="text-meta uppercase tracking-label text-accent">{eyebrow}</p>}
        <Heading className={cn("font-display text-heading-lg text-foreground", eyebrow && "mt-2")}>
          {title}
        </Heading>
        {description && <p className="mt-2 max-w-xl text-small text-muted">{description}</p>}
      </div>
      {action && (
        <Link
          href={action.href}
          className="shrink-0 text-small font-medium text-accent hover:text-accent-strong"
        >
          {action.label} <span aria-hidden="true">&rarr;</span>
        </Link>
      )}
    </div>
  );
}

"use client";

import { Button } from "@/components/ui/button";

type ErrorStateProps = {
  title?: string;
  description?: string;
  onRetry?: () => void;
};

/** Shown when a request for stations, media or metadata fails to load. */
export function ErrorState({
  title = "Something went wrong",
  description = "The request could not be completed. Please try again.",
  onRetry,
}: ErrorStateProps) {
  return (
    <div className="flex flex-col items-start gap-3 rounded-sm border border-border bg-surface px-6 py-12">
      <p className="font-display text-heading-md text-foreground">{title}</p>
      <p className="max-w-md text-small text-muted">{description}</p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

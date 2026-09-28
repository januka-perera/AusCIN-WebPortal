"use client";

import { ErrorState } from "@/components/ui/error-state";

/**
 * Error boundary for every /coastsnap route. When the catalogue API is
 * unreachable, times out, returns a server error or sends an invalid response,
 * the HTTP repository throws a `CoastSnapApiError`, and visitors see this
 * controlled state instead of a crash page. In production, Next.js replaces
 * server error messages with a digest, so no API host or request detail
 * reaches the browser.
 */
export default function CoastSnapError({ retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      <p className="text-meta uppercase tracking-label text-accent">CoastSnap</p>
      <div className="mt-6">
        <ErrorState
          title="CoastSnap catalogue unavailable"
          description="The CoastSnap catalogue couldn't be reached just now, so sites and photos can't be shown. Please try again shortly."
          onRetry={retry}
        />
      </div>
    </div>
  );
}

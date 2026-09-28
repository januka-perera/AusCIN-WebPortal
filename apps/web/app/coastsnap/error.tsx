"use client";

import { ErrorState } from "@/components/ui/error-state";
import { COASTSNAP_ERROR_TITLE } from "@/lib/coastsnap-presentation";

/**
 * Error boundary for every /coastsnap route. When the catalogue API is
 * unreachable, times out, returns a server error or sends an invalid response,
 * the HTTP repository throws a `CoastSnapApiError`, and visitors see this
 * controlled state instead of a crash page.
 *
 * Everything shown here, including the document title, is fixed text. The
 * `error` prop is deliberately never rendered: in development it carries the
 * server message, which names the request path. In production, Next.js
 * replaces server error messages with a digest anyway.
 *
 * A client error boundary can't export `metadata`, and the failing page's own
 * `generateMetadata` may have thrown too. The React 19 `<title>` element below
 * is hoisted into `<head>`, so the tab shows a stable title rather than the URL.
 */
export default function CoastSnapError({ retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      <title>{COASTSNAP_ERROR_TITLE}</title>
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

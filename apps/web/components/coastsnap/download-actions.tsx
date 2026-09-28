import { Button } from "@/components/ui/button";
import { StatusLabel } from "@/components/ui/status-label";
import type { CoastSnapDownloadView } from "@/lib/coastsnap-presentation";

/**
 * The "Data access" actions on a CoastSnap observation page.
 *
 * - API records get one explicit action per permitted product level
 *   (Level 0 and/or Level 1), each with a plain-language explanation and its
 *   published SHA-256. If only one level is permitted, the other is named with
 *   the reason it isn't offered.
 * - Sample records keep their single, clearly labelled prototype demo.
 * - Otherwise one of the explicit processing, failed, restricted or
 *   unavailable states is shown.
 *
 * Pure presentation: every decision is made in `getCoastSnapDownloadView`.
 */
export function CoastSnapDownloadActions({ view }: { view: CoastSnapDownloadView }) {
  if (view.kind === "sample-demo") {
    return (
      <>
        <Button href={view.url}>Download original (prototype demo)</Button>
        <p className="mt-2 max-w-sm text-small text-muted">
          This is a local placeholder file used to demonstrate the download-available state, not a
          real CoastSnap photo or a production download.
        </p>
      </>
    );
  }

  if (view.kind === "none") {
    return (
      <>
        <StatusLabel label={view.label} tone="neutral" />
        <p className="mt-2 max-w-sm text-small text-muted">{view.description}</p>
      </>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {view.offered.map((download) => (
        <div key={download.level} data-download-level={download.level}>
          <Button href={download.url}>{download.action}</Button>
          <p className="mt-2 max-w-sm text-small text-muted">{download.description}</p>
          {download.checksumSha256 && (
            <p className="mt-1 max-w-sm text-meta text-muted">
              SHA-256 <code className="break-all font-mono">{download.checksumSha256}</code>
            </p>
          )}
        </div>
      ))}
      {view.withheld.map((item) => (
        <p key={item.level} className="max-w-sm text-small text-muted" data-withheld-level={item.level}>
          {item.reason}
        </p>
      ))}
    </div>
  );
}

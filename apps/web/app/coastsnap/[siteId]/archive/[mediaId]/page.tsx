import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Button } from "@/components/ui/button";
import { MetadataList } from "@/components/ui/metadata-list";
import { StatusLabel } from "@/components/ui/status-label";
import { coastSnapRepository } from "@/data";
import {
  formatCoordinates,
  formatLocalDate,
  formatLocalTime,
  formatUtcTimestamp,
} from "@/lib/format";
import { getPreviewAvailability, type PreviewAvailability } from "@/lib/media-access";
import { formatMediaTypeLabel, formatPublicationLabel } from "@/lib/observation-badge";
import { getProcessingStatusTone, getPublicationStatusTone } from "@/lib/status-tone";

export async function generateMetadata({
  params,
}: PageProps<"/coastsnap/[siteId]/archive/[mediaId]">): Promise<Metadata> {
  const { siteId, mediaId } = await params;
  const site = await coastSnapRepository.getSite(siteId);
  const observation = site ? await coastSnapRepository.getObservationForSite(site.id, mediaId) : undefined;
  if (!site || !observation) return { title: "Observation not found" };
  return { title: `${formatMediaTypeLabel(observation.mediaType)} — ${site.name}` };
}

function unavailableReason(previewAvailability: PreviewAvailability): string {
  if (previewAvailability === "processing") {
    return "This observation is still processing. A preview isn't available yet.";
  }
  if (previewAvailability === "failed") {
    return "This capture failed. No preview is available for this observation.";
  }
  return "No preview is available for this observation.";
}

export default async function CoastSnapMediaDetailPage({
  params,
}: PageProps<"/coastsnap/[siteId]/archive/[mediaId]">) {
  const { siteId, mediaId } = await params;
  const site = await coastSnapRepository.getSite(siteId);

  if (!site) {
    notFound();
  }

  // Scoped to this site: an observation ID that belongs to a different
  // CoastSnap site is never returned here, even if it exists elsewhere.
  const observation = await coastSnapRepository.getObservationForSite(site.id, mediaId);

  if (!observation) {
    notFound();
  }

  const previewSrc = observation.previewUrl ?? observation.thumbnailUrl;
  const previewAvailability = getPreviewAvailability(observation);

  const dimensions =
    observation.width && observation.height ? `${observation.width} × ${observation.height}` : "Not recorded";

  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-small">
        <Link
          href={`/coastsnap/${site.id}/archive`}
          className="font-medium text-accent hover:text-accent-strong"
        >
          <span aria-hidden="true">&larr;</span> {site.name} archive
        </Link>
        <span className="text-muted" aria-hidden="true">
          /
        </span>
        <span className="text-muted">{formatMediaTypeLabel(observation.mediaType)}</span>
      </div>

      <p className="mt-6 text-meta uppercase tracking-label text-accent">CoastSnap observation</p>
      <h1 className="mt-2 font-display text-display-md text-foreground">{observation.caption}</h1>
      <p className="mt-2 text-meta text-muted">
        Sample development record &mdash; not an operational AusCIN feed. This is synthetic
        development imagery, not a real CoastSnap contribution.
      </p>

      <div className="mt-8 grid gap-10 lg:grid-cols-[3fr_2fr] lg:items-start">
        <div>
          <div className="relative aspect-video overflow-hidden bg-border/40">
            {previewSrc ? (
              <Image
                src={previewSrc}
                alt={observation.altText}
                fill
                sizes="(min-width: 1024px) 60vw, 100vw"
                className="object-cover"
              />
            ) : (
              <div className="absolute inset-0 flex items-center justify-center px-6 text-center text-small text-muted">
                {unavailableReason(previewAvailability)}
              </div>
            )}
            <span className="absolute left-3 top-3 bg-surface/90 px-2 py-1 text-meta uppercase tracking-label text-foreground">
              {formatMediaTypeLabel(observation.mediaType)}
            </span>
          </div>
          <p className="mt-3 text-small text-muted">{observation.altText}</p>
        </div>

        <div>
          <h2 className="font-display text-heading-md text-foreground">Capture information</h2>
          <div className="mt-4">
            <MetadataList
              items={[
                { label: "Site", value: site.name },
                { label: "Source", value: "CoastSnap (Spotteron)" },
                { label: "Contributor", value: observation.contributor.displayName },
                { label: "Attribution", value: observation.contributor.attributionText },
                { label: "Media type", value: formatMediaTypeLabel(observation.mediaType) },
                { label: "Capture date", value: formatLocalDate(observation.capturedAtUtc, observation.displayTimeZone) },
                { label: "Capture time", value: formatLocalTime(observation.capturedAtUtc, observation.displayTimeZone) },
                { label: "Local time zone", value: observation.displayTimeZone },
                { label: "UTC timestamp", value: formatUtcTimestamp(observation.capturedAtUtc) },
                { label: "Location", value: formatCoordinates(site.latitude, site.longitude) },
                { label: "Dimensions", value: dimensions },
                {
                  label: "Processing status",
                  value: (
                    <StatusLabel
                      label={observation.processingStatus}
                      tone={getProcessingStatusTone(observation.processingStatus)}
                    />
                  ),
                },
                {
                  label: "Publication status",
                  value: (
                    <StatusLabel
                      label={formatPublicationLabel(observation.publicationStatus)}
                      tone={getPublicationStatusTone(observation.publicationStatus)}
                    />
                  ),
                },
              ]}
            />
          </div>

          <h2 className="mt-8 font-display text-heading-md text-foreground">Data access</h2>
          <div className="mt-3">
            {observation.isOriginalAvailable && observation.originalUrl ? (
              <>
                <Button href={observation.originalUrl}>Download original (prototype demo)</Button>
                <p className="mt-2 max-w-sm text-small text-muted">
                  This is a local placeholder file used to demonstrate the download-available
                  state, not a real CoastSnap photo or a production download.
                </p>
              </>
            ) : (
              <>
                <StatusLabel label="Original unavailable" tone="neutral" />
                <p className="mt-2 max-w-sm text-small text-muted">
                  This development prototype does not mark this observation&apos;s original as
                  available. Once real observations are ingested from Spotteron, availability here
                  will follow the record&apos;s actual publication status.
                </p>
              </>
            )}
          </div>

          <div className="mt-4">
            <Link
              href={`/coastsnap/${site.id}`}
              className="text-small font-medium text-accent hover:text-accent-strong"
            >
              View site record &rarr;
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Button } from "@/components/ui/button";
import { MetadataList } from "@/components/ui/metadata-list";
import { ObservationThumbnail } from "@/components/ui/observation-thumbnail";
import { StatusLabel } from "@/components/ui/status-label";
import {
  getAdjacentMedia,
  getCamerasForStation,
  getMediaById,
  getMediaForCamera,
  getMediaForStation,
  getRelatedMedia,
  getStationById,
  sortMediaByCaptureTime,
  type Camera,
} from "@/data";
import {
  formatCoordinates,
  formatFileSize,
  formatLocalDate,
  formatLocalTime,
  formatUtcTimestamp,
} from "@/lib/format";
import { formatMediaTypeLabel, formatPublicationLabel } from "@/lib/observation-badge";
import { getProcessingStatusTone, getPublicationStatusTone } from "@/lib/status-tone";
import {
  applyArchiveFilters,
  buildArchiveHref,
  buildMediaDetailHref,
  filtersToParamState,
  parseArchiveFilters,
  type SearchParams,
} from "../filters";

export async function generateMetadata({
  params,
}: PageProps<"/stations/[stationId]/archive/[mediaId]">): Promise<Metadata> {
  const { stationId, mediaId } = await params;
  const station = getStationById(stationId);
  const item = station ? getMediaById(mediaId, getMediaForStation(station.id)) : undefined;
  if (!station || !item) return { title: "Observation not found" };
  return { title: `${formatMediaTypeLabel(item.mediaType)} — ${station.name}` };
}

function unavailableReason(processingStatus: string): string {
  if (processingStatus === "processing") {
    return "This observation is still processing. A preview isn't available yet.";
  }
  if (processingStatus === "failed") {
    return "This capture failed. No preview is available for this observation.";
  }
  return "No preview is available for this observation.";
}

export default async function MediaDetailPage({
  params,
  searchParams,
}: PageProps<"/stations/[stationId]/archive/[mediaId]">) {
  const { stationId, mediaId } = await params;
  const search: SearchParams = await searchParams;
  const station = getStationById(stationId);

  if (!station) {
    notFound();
  }

  const allStationMedia = getMediaForStation(station.id);
  const item = getMediaById(mediaId, allStationMedia);

  if (!item) {
    notFound();
  }

  const cameras = getCamerasForStation(station.id);
  const cameraById = new Map<string, Camera>(cameras.map((camera) => [camera.id, camera]));
  const camera = cameraById.get(item.cameraId);

  const filters = parseArchiveFilters(search, cameras);
  const paramState = filtersToParamState(filters);
  const filteredSorted = sortMediaByCaptureTime(applyArchiveFilters(allStationMedia, filters), "asc");
  const { previous, next } = getAdjacentMedia(filteredSorted, item.id);

  let relatedItems = getRelatedMedia(item.id, allStationMedia);
  let relatedHeading = "Related media";
  if (relatedItems.length === 0) {
    const cameraSorted = sortMediaByCaptureTime(getMediaForCamera(item.cameraId, allStationMedia), "asc");
    const index = cameraSorted.findIndex((candidate) => candidate.id === item.id);
    if (index !== -1) {
      relatedItems = [...cameraSorted.slice(Math.max(0, index - 2), index), ...cameraSorted.slice(index + 1, index + 3)];
      relatedHeading = "Nearby observations";
    }
  }

  const previewSrc = item.previewUrl ?? item.thumbnailUrl;
  const isTimelapse = item.mediaType === "timelapse";

  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-small">
        <Link
          href={buildArchiveHref(station.id, { ...paramState, selected: item.id })}
          className="font-medium text-accent hover:text-accent-strong"
        >
          <span aria-hidden="true">&larr;</span> {station.name} archive
        </Link>
        <span className="text-muted" aria-hidden="true">
          /
        </span>
        <span className="text-muted">{camera?.name ?? item.cameraId}</span>
        <span className="text-muted" aria-hidden="true">
          /
        </span>
        <span className="text-muted">{formatMediaTypeLabel(item.mediaType)}</span>
      </div>

      <p className="mt-6 text-meta uppercase tracking-label text-accent">Observation record</p>
      <h1 className="mt-2 font-display text-display-md text-foreground">{item.caption}</h1>
      <p className="mt-2 text-meta text-muted">
        Sample development record &mdash; not an operational AusCIN feed.
      </p>

      <div className="mt-8 grid gap-10 lg:grid-cols-[3fr_2fr] lg:items-start">
        <div>
          <div className="relative aspect-video overflow-hidden bg-border/40">
            {previewSrc ? (
              <Image
                src={previewSrc}
                alt={item.altText}
                fill
                sizes="(min-width: 1024px) 60vw, 100vw"
                className="object-cover"
              />
            ) : (
              <div className="absolute inset-0 flex items-center justify-center px-6 text-center text-small text-muted">
                {unavailableReason(item.processingStatus)}
              </div>
            )}
            <span className="absolute left-3 top-3 bg-surface/90 px-2 py-1 text-meta uppercase tracking-label text-foreground">
              {formatMediaTypeLabel(item.mediaType)}
            </span>
          </div>
          {isTimelapse && (
            <p className="mt-3 border border-dashed border-border px-4 py-3 text-small text-muted">
              Development placeholder: this prototype does not implement time-lapse playback. The
              image above is a synthetic poster frame, not a playable video.
            </p>
          )}
          <p className="mt-3 text-small text-muted">{item.altText}</p>
        </div>

        <div>
          <h2 className="font-display text-heading-md text-foreground">Capture information</h2>
          <div className="mt-4">
            <MetadataList
              items={[
                { label: "Station", value: station.name },
                { label: "Camera", value: camera?.name ?? item.cameraId },
                { label: "Media type", value: formatMediaTypeLabel(item.mediaType) },
                { label: "Capture date", value: formatLocalDate(item.capturedAtUtc, item.displayTimeZone) },
                { label: "Capture time", value: formatLocalTime(item.capturedAtUtc, item.displayTimeZone) },
                { label: "Local time zone", value: item.displayTimeZone },
                { label: "UTC timestamp", value: formatUtcTimestamp(item.capturedAtUtc) },
                { label: "Dimensions", value: `${item.width} × ${item.height}` },
                ...(item.durationSeconds !== undefined
                  ? [{ label: "Duration", value: `${item.durationSeconds}s` }]
                  : []),
                { label: "File size", value: formatFileSize(item.fileSizeBytes) },
                {
                  label: "Processing status",
                  value: (
                    <StatusLabel
                      label={item.processingStatus}
                      tone={getProcessingStatusTone(item.processingStatus)}
                    />
                  ),
                },
                {
                  label: "Publication status",
                  value: (
                    <StatusLabel
                      label={formatPublicationLabel(item.publicationStatus)}
                      tone={getPublicationStatusTone(item.publicationStatus)}
                    />
                  ),
                },
                { label: "Caption", value: item.caption },
                { label: "Description", value: item.altText },
              ]}
            />
          </div>

          <h2 className="mt-8 font-display text-heading-md text-foreground">Data access</h2>
          <div className="mt-3">
            {item.originalUrl ? (
              <Button href={item.originalUrl}>Download original</Button>
            ) : item.publicationStatus === "restricted" ? (
              <>
                <StatusLabel label="Download restricted" tone="restricted" />
                <p className="mt-2 max-w-sm text-small text-muted">
                  This observation&apos;s publication status does not permit downloading the
                  original file.
                </p>
              </>
            ) : (
              <>
                <StatusLabel label="Original unavailable" tone="neutral" />
                <p className="mt-2 max-w-sm text-small text-muted">
                  This development prototype does not yet serve original files.
                </p>
              </>
            )}
          </div>

          <h2 className="mt-8 font-display text-heading-md text-foreground">Station</h2>
          <div className="mt-3">
            <MetadataList
              items={[
                { label: "Station", value: station.name },
                { label: "Region", value: station.region },
                { label: "State/territory", value: station.state },
                { label: "Station ID", value: station.id },
                { label: "Coordinates", value: formatCoordinates(station.latitude, station.longitude) },
                { label: "Camera view direction", value: camera?.viewDirection ?? station.viewDirection },
              ]}
            />
          </div>
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2">
            <Link
              href={`/stations/${station.id}`}
              className="text-small font-medium text-accent hover:text-accent-strong"
            >
              View station record <span aria-hidden="true">&rarr;</span>
            </Link>
            <Link
              href={buildArchiveHref(station.id, { ...paramState, selected: item.id })}
              className="text-small font-medium text-accent hover:text-accent-strong"
            >
              Return to filtered archive <span aria-hidden="true">&rarr;</span>
            </Link>
          </div>
        </div>
      </div>

      <section className="mt-16 border-t border-border pt-10">
        <h2 className="font-display text-heading-lg text-foreground">Nearby in this view</h2>
        <div className="mt-6 grid grid-cols-1 gap-6 sm:grid-cols-3">
          <div>
            <p className="text-meta uppercase tracking-label text-muted">Previous observation</p>
            {previous ? (
              <Link
                href={buildMediaDetailHref(station.id, previous.id, paramState)}
                className="mt-1 block text-small font-medium text-accent hover:text-accent-strong"
              >
                &larr; {formatLocalTime(previous.capturedAtUtc, previous.displayTimeZone)},{" "}
                {formatLocalDate(previous.capturedAtUtc, previous.displayTimeZone)}
                {previous.cameraId !== item.cameraId
                  ? ` — ${cameraById.get(previous.cameraId)?.name ?? previous.cameraId}`
                  : ""}
              </Link>
            ) : (
              <p className="mt-1 text-small text-muted">No earlier observation in this view.</p>
            )}
          </div>
          <div>
            <p className="text-meta uppercase tracking-label text-muted">Next observation</p>
            {next ? (
              <Link
                href={buildMediaDetailHref(station.id, next.id, paramState)}
                className="mt-1 block text-small font-medium text-accent hover:text-accent-strong"
              >
                {formatLocalTime(next.capturedAtUtc, next.displayTimeZone)},{" "}
                {formatLocalDate(next.capturedAtUtc, next.displayTimeZone)}
                {next.cameraId !== item.cameraId
                  ? ` — ${cameraById.get(next.cameraId)?.name ?? next.cameraId}`
                  : ""}{" "}
                &rarr;
              </Link>
            ) : (
              <p className="mt-1 text-small text-muted">No later observation in this view.</p>
            )}
          </div>
          <div>
            <p className="text-meta uppercase tracking-label text-muted">This camera</p>
            <Link
              href={buildArchiveHref(station.id, { camera: item.cameraId })}
              className="mt-1 block text-small font-medium text-accent hover:text-accent-strong"
            >
              View all observations from {camera?.name ?? item.cameraId} <span aria-hidden="true">&rarr;</span>
            </Link>
          </div>
        </div>
      </section>

      <section className="mt-16 border-t border-border pt-10">
        <h2 className="font-display text-heading-lg text-foreground">{relatedHeading}</h2>
        {relatedItems.length === 0 ? (
          <p className="mt-4 text-small text-muted">
            No related observations are recorded for this capture in the sample dataset.
          </p>
        ) : (
          <div className="mt-6 grid grid-cols-2 gap-6 sm:grid-cols-3 lg:grid-cols-5">
            {relatedItems.map((related) => (
              <Link
                key={related.id}
                href={buildMediaDetailHref(station.id, related.id, paramState)}
                className="block border-t border-border pt-3"
              >
                <ObservationThumbnail item={related} sizes="(min-width: 1024px) 20vw, 33vw" />
                <p className="mt-2 text-small font-medium text-foreground">
                  {formatMediaTypeLabel(related.mediaType)}
                </p>
                <p className="mt-1 text-meta uppercase tracking-label text-muted">
                  {formatLocalDate(related.capturedAtUtc, related.displayTimeZone)}
                  {", "}
                  {formatLocalTime(related.capturedAtUtc, related.displayTimeZone)}
                </p>
                <p className="mt-1 text-meta uppercase tracking-label text-muted">
                  {cameraById.get(related.cameraId)?.name ?? related.cameraId}
                </p>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

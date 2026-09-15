import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { MetadataList } from "@/components/ui/metadata-list";
import { SectionHeading } from "@/components/ui/section-heading";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusLabel, type StatusTone } from "@/components/ui/status-label";
import {
  getCamerasForStation,
  getMediaForCamera,
  getMediaForStation,
  getStationById,
  sortMediaByCaptureTime,
  type MediaItem,
  type MediaType,
  type PublicationStatus,
} from "@/data";
import { formatCoordinates, formatLocalDateTime, formatOperationalDate } from "@/lib/format";
import {
  getOperatingStatusTone,
  getProcessingStatusTone,
  getPublicationStatusTone,
} from "@/lib/status-tone";

const LATEST_OBSERVATIONS_LIMIT = 6;

export async function generateMetadata({
  params,
}: PageProps<"/stations/[stationId]">): Promise<Metadata> {
  const { stationId } = await params;
  const station = getStationById(stationId);
  return { title: station ? station.name : "Station not found" };
}

function formatMediaTypeLabel(type: MediaType): string {
  return type === "timelapse" ? "Time-lapse" : type.charAt(0).toUpperCase() + type.slice(1);
}

function formatPublicationLabel(status: PublicationStatus): string {
  return status.charAt(0).toUpperCase() + status.slice(1).replace("-", " ");
}

/** Only surfaces a badge when there's something worth flagging; ordinary public, processed items stay unbadged. */
function getObservationBadge(item: MediaItem): { label: string; tone: StatusTone } | null {
  if (item.processingStatus === "processing") {
    return { label: "Processing", tone: getProcessingStatusTone(item.processingStatus) };
  }
  if (item.processingStatus === "failed") {
    return { label: "Failed", tone: getProcessingStatusTone(item.processingStatus) };
  }
  if (item.publicationStatus !== "public") {
    return {
      label: formatPublicationLabel(item.publicationStatus),
      tone: getPublicationStatusTone(item.publicationStatus),
    };
  }
  return null;
}

export default async function StationDetailPage({
  params,
}: PageProps<"/stations/[stationId]">) {
  const { stationId } = await params;
  const station = getStationById(stationId);

  if (!station) {
    notFound();
  }

  const cameras = getCamerasForStation(station.id);
  const media = getMediaForStation(station.id);
  const latestObservations = sortMediaByCaptureTime(media, "desc").slice(
    0,
    LATEST_OBSERVATIONS_LIMIT,
  );

  const stationMetadata = [
    { label: "Station ID", value: station.id },
    { label: "Coordinates", value: formatCoordinates(station.latitude, station.longitude) },
    { label: "Region", value: station.region },
    { label: "Elevation", value: `${station.elevationMetres} m AHD` },
    { label: "View direction", value: station.viewDirection },
    { label: "Operational since", value: formatOperationalDate(station.operationalSince) },
    { label: "Cameras", value: String(cameras.length) },
    { label: "Observations", value: String(media.length) },
  ];

  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      <Link href="/stations" className="text-small font-medium text-accent hover:text-accent-strong">
        <span aria-hidden="true">&larr;</span> Station records
      </Link>

      <div className="mt-6 grid gap-10 lg:grid-cols-[3fr_2fr] lg:items-start">
        <div>
          <p className="text-meta uppercase tracking-label text-accent">
            {station.state} &middot; {station.region}
          </p>
          <h1 className="mt-2 font-display text-display-md text-foreground">{station.name}</h1>

          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
            <StatusLabel
              label={station.operationalStatus}
              tone={getOperatingStatusTone(station.operationalStatus)}
            />
            <span className="text-meta uppercase tracking-label text-muted">
              Station ID &middot; {station.id}
            </span>
          </div>
          <p className="mt-2 text-meta text-muted">
            Sample development record &mdash; not an operational AusCIN feed.
          </p>

          <p className="mt-6 max-w-xl text-body text-muted">
            {station.description} Since {formatOperationalDate(station.operationalSince)}, its{" "}
            {cameras.length} camera{cameras.length === 1 ? "" : "s"} have logged {media.length}{" "}
            observation{media.length === 1 ? "" : "s"} for the archive.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Button disabled title="The full archive view is still being built.">
              Browse station archive
            </Button>
            <StatusLabel label="Archive view in development" tone="caution" />
          </div>
        </div>

        <div>
          {station.representativeImageUrl ? (
            <div className="relative aspect-video overflow-hidden bg-border/40">
              <Image
                src={station.representativeImageUrl}
                alt={`Representative sample image for ${station.name}, a ${station.viewDirection}-facing coastal observation station in ${station.region}`}
                fill
                sizes="(min-width: 1024px) 40vw, 100vw"
                className="object-cover"
              />
            </div>
          ) : (
            <div className="flex aspect-video items-center justify-center border border-dashed border-border text-small text-muted">
              Image unavailable
            </div>
          )}
        </div>
      </div>

      <section className="mt-16 border-t border-border pt-10">
        <h2 className="font-display text-heading-lg text-foreground">Station record</h2>
        <div className="mt-6 max-w-xl">
          <MetadataList items={stationMetadata} />
        </div>
      </section>

      <section className="mt-16 border-t border-border pt-10">
        <h2 className="font-display text-heading-lg text-foreground">Cameras</h2>
        {cameras.length === 0 ? (
          <EmptyState
            className="mt-6"
            title="No cameras recorded"
            description="This station does not yet have any camera records in the sample dataset."
          />
        ) : (
          <div className="mt-6 grid grid-cols-1 gap-8 sm:grid-cols-2">
            {cameras.map((camera) => {
              const cameraMediaCount = getMediaForCamera(camera.id).length;
              return (
                <div key={camera.id} className="border-t border-border pt-4">
                  <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
                    <h3 className="font-display text-heading-md text-foreground">{camera.name}</h3>
                    <StatusLabel label={camera.status} tone={getOperatingStatusTone(camera.status)} />
                  </div>
                  <div className="mt-3">
                    <MetadataList
                      items={[
                        { label: "Camera ID", value: camera.id },
                        { label: "Type", value: camera.type },
                        {
                          label: "Resolution",
                          value: `${camera.resolution.width} × ${camera.resolution.height}`,
                        },
                        { label: "View direction", value: camera.viewDirection },
                        { label: "Capture interval", value: `${camera.captureIntervalMinutes} min` },
                        { label: "Observations", value: String(cameraMediaCount) },
                      ]}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <section className="mt-16 border-t border-border pt-10">
        <SectionHeading
          eyebrow="Latest observations"
          title={`Recent captures at ${station.name}`}
          description="The most recent images, composites and time-lapse video from this station's cameras, newest first."
        />
        {latestObservations.length === 0 ? (
          <EmptyState
            className="mt-8"
            title="No observations yet"
            description="This station has no media records in the sample dataset yet."
          />
        ) : (
          <div className="mt-8 grid grid-cols-2 gap-6 sm:grid-cols-3">
            {latestObservations.map((item) => {
              const badge = getObservationBadge(item);
              return (
                <div key={item.id} className="border-t border-border pt-3">
                  <div className="relative aspect-[4/3] overflow-hidden bg-border/40">
                    {item.thumbnailUrl ? (
                      <Image
                        src={item.thumbnailUrl}
                        alt={item.altText}
                        fill
                        sizes="(min-width: 640px) 33vw, 50vw"
                        className="object-cover"
                      />
                    ) : item.processingStatus === "processing" ? (
                      <Skeleton className="absolute inset-0" />
                    ) : (
                      <div className="absolute inset-0 flex items-center justify-center px-2 text-center text-meta uppercase tracking-label text-muted">
                        Unavailable
                      </div>
                    )}
                    {badge && (
                      <span className="absolute left-2 top-2 bg-surface/90 px-2 py-1">
                        <StatusLabel label={badge.label} tone={badge.tone} />
                      </span>
                    )}
                  </div>
                  <p className="mt-2 text-small font-medium text-foreground">
                    {formatMediaTypeLabel(item.mediaType)}
                  </p>
                  <p className="mt-1 text-meta uppercase tracking-label text-muted">
                    {formatLocalDateTime(item.capturedAtUtc, item.displayTimeZone)}
                  </p>
                  <p className="mt-1 text-small text-muted">{item.caption}</p>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <section className="mt-16 border-t border-border pt-10">
        <h2 className="font-display text-heading-md text-foreground">Related data products</h2>
        <p className="mt-2 max-w-xl text-small text-muted">
          Not yet linked in this prototype. Future station records are intended to reference the
          coastal datasets and research products this station&apos;s imagery supports.
        </p>
      </section>
    </div>
  );
}

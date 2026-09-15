import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { MetadataList } from "@/components/ui/metadata-list";
import { ObservationThumbnail } from "@/components/ui/observation-thumbnail";
import { StatusLabel } from "@/components/ui/status-label";
import {
  filterMediaByLocalDate,
  filterMediaByDateRange,
  filterMediaByProcessingStatus,
  filterMediaByPublicationStatus,
  filterMediaByTimeOfDay,
  filterMediaByType,
  getCamerasForStation,
  getMediaForCamera,
  getMediaForStation,
  getRelatedMedia,
  getStationById,
  groupMediaByLocalDate,
  sortMediaByCaptureTime,
  type Camera,
  type MediaType,
  type ProcessingStatus,
  type PublicationStatus,
} from "@/data";
import {
  formatDayHeading,
  formatFileSize,
  formatLocalDateTime,
  formatLocalTime,
  formatShortDate,
} from "@/lib/format";
import { formatMediaTypeLabel, formatPublicationLabel } from "@/lib/observation-badge";
import { getProcessingStatusTone, getPublicationStatusTone } from "@/lib/status-tone";
import { getTimeOfDayOption, TIME_OF_DAY_OPTIONS } from "./time-of-day";

const MEDIA_TYPES: MediaType[] = ["image", "composite", "timelapse"];
const PROCESSING_STATUSES: ProcessingStatus[] = ["processed", "processing", "failed"];
const PUBLICATION_STATUSES: PublicationStatus[] = ["public", "embargoed", "project-only", "restricted"];
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

const controlClassName = "w-full rounded-sm border border-border bg-surface px-3 py-2 text-small text-foreground";
const labelClassName = "flex flex-col gap-1 text-small text-foreground";

type SearchParams = Record<string, string | string[] | undefined>;

function firstParam(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function isValidDate(value: string | undefined): value is string {
  return value !== undefined && DATE_PATTERN.test(value);
}

type FilterState = {
  camera?: string;
  mediaType?: string;
  date?: string;
  from?: string;
  to?: string;
  timeOfDay?: string;
  processingStatus?: string;
  publicationStatus?: string;
  selected?: string;
};

function buildArchiveHref(stationId: string, state: FilterState): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(state)) {
    if (value) params.set(key, value);
  }
  const query = params.toString();
  return `/stations/${stationId}/archive${query ? `?${query}` : ""}`;
}

export async function generateMetadata({
  params,
}: PageProps<"/stations/[stationId]/archive">): Promise<Metadata> {
  const { stationId } = await params;
  const station = getStationById(stationId);
  return { title: station ? `${station.name} archive` : "Station not found" };
}

export default async function StationArchivePage({
  params,
  searchParams,
}: PageProps<"/stations/[stationId]/archive">) {
  const { stationId } = await params;
  const search: SearchParams = await searchParams;
  const station = getStationById(stationId);

  if (!station) {
    notFound();
  }

  const cameras = getCamerasForStation(station.id);
  const cameraById = new Map<string, Camera>(cameras.map((camera) => [camera.id, camera]));
  const allStationMedia = getMediaForStation(station.id);

  // --- parse and validate filters (invalid or foreign values are ignored, not rejected) ---
  const cameraParam = firstParam(search.camera);
  const selectedCamera = cameraParam ? cameraById.get(cameraParam) : undefined;

  const mediaTypeParam = firstParam(search.mediaType);
  const selectedMediaType = MEDIA_TYPES.find((type) => type === mediaTypeParam);

  const dateParam = firstParam(search.date);
  const selectedDate = isValidDate(dateParam) ? dateParam : undefined;

  const fromParam = firstParam(search.from);
  const toParam = firstParam(search.to);
  const validFrom = isValidDate(fromParam) ? fromParam : undefined;
  const validTo = isValidDate(toParam) ? toParam : undefined;

  const timeOfDayParam = firstParam(search.timeOfDay);
  const selectedTimeOfDay = getTimeOfDayOption(timeOfDayParam);

  const processingParam = firstParam(search.processingStatus);
  const selectedProcessingStatus = PROCESSING_STATUSES.find((status) => status === processingParam);

  const publicationParam = firstParam(search.publicationStatus);
  const selectedPublicationStatus = PUBLICATION_STATUSES.find((status) => status === publicationParam);

  // --- apply filters in sequence, each built from an existing typed query helper ---
  let filtered = selectedCamera ? getMediaForCamera(selectedCamera.id, allStationMedia) : allStationMedia;
  if (selectedMediaType) filtered = filterMediaByType(filtered, selectedMediaType);
  if (selectedDate) {
    filtered = filterMediaByLocalDate(filtered, selectedDate);
  } else if (validFrom || validTo) {
    filtered = filterMediaByDateRange(
      filtered,
      validFrom ? `${validFrom}T00:00:00.000Z` : "0001-01-01T00:00:00.000Z",
      validTo ? `${validTo}T23:59:59.999Z` : "9999-12-31T23:59:59.999Z",
    );
  }
  if (selectedTimeOfDay) {
    filtered = filterMediaByTimeOfDay(filtered, selectedTimeOfDay.startMinutes, selectedTimeOfDay.endMinutes);
  }
  if (selectedProcessingStatus) filtered = filterMediaByProcessingStatus(filtered, selectedProcessingStatus);
  if (selectedPublicationStatus) filtered = filterMediaByPublicationStatus(filtered, selectedPublicationStatus);

  const hasActiveFilters = Boolean(
    selectedCamera ||
      selectedMediaType ||
      selectedDate ||
      validFrom ||
      validTo ||
      selectedTimeOfDay ||
      selectedProcessingStatus ||
      selectedPublicationStatus,
  );

  const baseFilterState: FilterState = {
    camera: selectedCamera?.id,
    mediaType: selectedMediaType,
    date: selectedDate,
    from: validFrom,
    to: validTo,
    timeOfDay: selectedTimeOfDay?.key,
    processingStatus: selectedProcessingStatus,
    publicationStatus: selectedPublicationStatus,
  };

  // --- selected observation (must exist and belong to this station) ---
  const selectedParam = firstParam(search.selected);
  const selectedObservation = selectedParam
    ? allStationMedia.find((item) => item.id === selectedParam)
    : undefined;

  // --- grouped, chronological results: most recent day first, each day oldest-to-newest ---
  const groups = groupMediaByLocalDate(sortMediaByCaptureTime(filtered, "asc"));
  const dayKeys = [...groups.keys()].sort().reverse();

  // --- date navigation always reflects the full station record, independent of other filters ---
  const availableDates = [...groupMediaByLocalDate(allStationMedia).keys()].sort();

  // --- results summary ---
  const summaryParts: string[] = [selectedCamera ? selectedCamera.name : "all cameras"];
  if (selectedMediaType) summaryParts.push(formatMediaTypeLabel(selectedMediaType).toLowerCase());
  if (selectedDate) {
    summaryParts.push(formatDayHeading(selectedDate));
  } else if (validFrom || validTo) {
    summaryParts.push(`${validFrom ? formatShortDate(validFrom) : "start"} to ${validTo ? formatShortDate(validTo) : "now"}`);
  }
  if (selectedTimeOfDay) summaryParts.push(selectedTimeOfDay.label);
  if (selectedProcessingStatus) summaryParts.push(`processing: ${selectedProcessingStatus}`);
  if (selectedPublicationStatus) summaryParts.push(`publication: ${formatPublicationLabel(selectedPublicationStatus).toLowerCase()}`);

  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      <Link
        href={`/stations/${station.id}`}
        className="text-small font-medium text-accent hover:text-accent-strong"
      >
        <span aria-hidden="true">&larr;</span> {station.name}
      </Link>

      <p className="mt-6 text-meta uppercase tracking-label text-accent">Observation archive</p>
      <h1 className="mt-2 font-display text-display-md text-foreground">
        Captures through time at {station.name}
      </h1>
      <p className="mt-1 text-meta uppercase tracking-label text-muted">
        {station.state} &middot; {station.region} &middot; Station ID {station.id}
      </p>
      <p className="mt-2 text-meta text-muted">
        Sample development record &mdash; not an operational AusCIN feed.
      </p>

      <p className="mt-6 max-w-2xl text-body text-muted">
        {station.description} This camera record holds repeated observations from{" "}
        {station.name}&apos;s cameras. Capture times are stored in UTC and displayed below in this
        station&apos;s local time zone.
      </p>

      <form
        method="get"
        action={`/stations/${station.id}/archive`}
        className="mt-10 border-t border-b border-border py-6"
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <label className={labelClassName}>
            Camera
            <select name="camera" defaultValue={selectedCamera?.id ?? ""} className={controlClassName}>
              <option value="">All cameras</option>
              {cameras.map((camera) => (
                <option key={camera.id} value={camera.id}>
                  {camera.name}
                  {camera.status !== "active" ? ` (${camera.status})` : ""}
                </option>
              ))}
            </select>
          </label>

          <label className={labelClassName}>
            Media type
            <select name="mediaType" defaultValue={selectedMediaType ?? ""} className={controlClassName}>
              <option value="">All types</option>
              {MEDIA_TYPES.map((type) => (
                <option key={type} value={type}>
                  {formatMediaTypeLabel(type)}
                </option>
              ))}
            </select>
          </label>

          <label className={labelClassName}>
            Time of day
            <select name="timeOfDay" defaultValue={selectedTimeOfDay?.key ?? ""} className={controlClassName}>
              <option value="">All times of day</option>
              {TIME_OF_DAY_OPTIONS.map((option) => (
                <option key={option.key} value={option.key}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className={labelClassName}>
            From date
            <input type="date" name="from" defaultValue={validFrom ?? ""} className={controlClassName} />
          </label>

          <label className={labelClassName}>
            To date
            <input type="date" name="to" defaultValue={validTo ?? ""} className={controlClassName} />
          </label>

          <label className={labelClassName}>
            Processing status
            <select
              name="processingStatus"
              defaultValue={selectedProcessingStatus ?? ""}
              className={controlClassName}
            >
              <option value="">All processing statuses</option>
              {PROCESSING_STATUSES.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </label>

          <label className={labelClassName}>
            Publication status
            <select
              name="publicationStatus"
              defaultValue={selectedPublicationStatus ?? ""}
              className={controlClassName}
            >
              <option value="">All publication statuses</option>
              {PUBLICATION_STATUSES.map((status) => (
                <option key={status} value={status}>
                  {formatPublicationLabel(status)}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-4">
          <Button type="submit">Apply filters</Button>
          {hasActiveFilters && (
            <Link
              href={`/stations/${station.id}/archive`}
              className="text-small font-medium text-accent hover:text-accent-strong"
            >
              Clear filters
            </Link>
          )}
        </div>
      </form>

      <div className="mt-6 flex flex-wrap items-center gap-x-2 gap-y-2 border-b border-border pb-6">
        <span className="text-meta uppercase tracking-label text-muted">Jump to date:</span>
        <Link
          href={buildArchiveHref(station.id, { ...baseFilterState, date: undefined, from: undefined, to: undefined })}
          className={`text-small ${!selectedDate && !validFrom && !validTo ? "font-medium text-accent" : "text-muted hover:text-accent"}`}
        >
          All dates
        </Link>
        {availableDates.map((dateKey) => (
          <Link
            key={dateKey}
            href={buildArchiveHref(station.id, { ...baseFilterState, date: dateKey, from: undefined, to: undefined })}
            className={`text-small ${selectedDate === dateKey ? "font-medium text-accent" : "text-muted hover:text-accent"}`}
          >
            {formatShortDate(dateKey)}
          </Link>
        ))}
      </div>

      <p className="mt-6 text-small text-foreground">
        <span className="font-medium">{filtered.length}</span> observation
        {filtered.length === 1 ? "" : "s"} &middot; {summaryParts.join(" · ")}
      </p>

      {selectedObservation && (
        <div className="mt-8 border border-border p-6">
          <div className="grid gap-8 lg:grid-cols-[3fr_2fr]">
            <div className="relative aspect-video overflow-hidden bg-border/40">
              {selectedObservation.previewUrl || selectedObservation.thumbnailUrl ? (
                <Image
                  src={(selectedObservation.previewUrl ?? selectedObservation.thumbnailUrl) as string}
                  alt={selectedObservation.altText}
                  fill
                  sizes="(min-width: 1024px) 60vw, 100vw"
                  className="object-cover"
                />
              ) : (
                <div className="absolute inset-0 flex items-center justify-center text-small text-muted">
                  {selectedObservation.processingStatus === "processing"
                    ? "Still processing"
                    : "Preview unavailable"}
                </div>
              )}
            </div>
            <div>
              <p className="text-meta uppercase tracking-label text-accent">Selected observation</p>
              <h2 className="mt-1 font-display text-heading-md text-foreground">
                {formatMediaTypeLabel(selectedObservation.mediaType)}
              </h2>
              <p className="mt-1 text-small text-muted">{selectedObservation.caption}</p>
              <div className="mt-4">
                <MetadataList
                  items={[
                    { label: "Station", value: station.name },
                    {
                      label: "Camera",
                      value: cameraById.get(selectedObservation.cameraId)?.name ?? selectedObservation.cameraId,
                    },
                    { label: "Media type", value: formatMediaTypeLabel(selectedObservation.mediaType) },
                    {
                      label: "Capture time",
                      value: formatLocalDateTime(
                        selectedObservation.capturedAtUtc,
                        selectedObservation.displayTimeZone,
                      ),
                    },
                    {
                      label: selectedObservation.mediaType === "timelapse" ? "Duration" : "Dimensions",
                      value:
                        selectedObservation.mediaType === "timelapse"
                          ? `${selectedObservation.durationSeconds}s`
                          : `${selectedObservation.width} × ${selectedObservation.height}`,
                    },
                    { label: "File size", value: formatFileSize(selectedObservation.fileSizeBytes) },
                    {
                      label: "Processing status",
                      value: (
                        <StatusLabel
                          label={selectedObservation.processingStatus}
                          tone={getProcessingStatusTone(selectedObservation.processingStatus)}
                        />
                      ),
                    },
                    {
                      label: "Publication status",
                      value: (
                        <StatusLabel
                          label={formatPublicationLabel(selectedObservation.publicationStatus)}
                          tone={getPublicationStatusTone(selectedObservation.publicationStatus)}
                        />
                      ),
                    },
                  ]}
                />
              </div>
              {selectedObservation.relatedMediaIds.length > 0 && (
                <div className="mt-4">
                  <p className="text-meta uppercase tracking-label text-muted">Related media</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {getRelatedMedia(selectedObservation.id, allStationMedia).map((related) => (
                      <Link
                        key={related.id}
                        href={buildArchiveHref(station.id, { ...baseFilterState, selected: related.id })}
                        className="border border-border px-2 py-1 text-meta text-foreground hover:border-accent hover:text-accent"
                      >
                        {formatMediaTypeLabel(related.mediaType)} &middot;{" "}
                        {formatLocalTime(related.capturedAtUtc, related.displayTimeZone)}
                      </Link>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {filtered.length === 0 ? (
        <EmptyState
          className="mt-10"
          title="No observations match these filters"
          description="Try a different camera, date or status, or clear the filters to see everything recorded for this station."
          action={hasActiveFilters ? { label: "Clear filters", href: `/stations/${station.id}/archive` } : undefined}
        />
      ) : (
        <div className="mt-10 space-y-12">
          {dayKeys.map((dayKey) => (
            <section key={dayKey}>
              <h2 className="font-display text-heading-md text-foreground">
                {formatDayHeading(dayKey)}
              </h2>
              <div className="mt-4 grid grid-cols-2 gap-6 sm:grid-cols-3 lg:grid-cols-4">
                {groups.get(dayKey)!.map((item) => (
                  <Link
                    key={item.id}
                    href={buildArchiveHref(station.id, { ...baseFilterState, selected: item.id })}
                    className="block border-t border-border pt-3"
                  >
                    <ObservationThumbnail item={item} sizes="(min-width: 1024px) 25vw, 50vw" />
                    <p className="mt-2 text-small font-medium text-foreground">
                      {formatMediaTypeLabel(item.mediaType)}
                    </p>
                    <p className="mt-1 text-meta uppercase tracking-label text-muted">
                      {formatLocalDateTime(item.capturedAtUtc, item.displayTimeZone)}
                    </p>
                    <p className="mt-1 text-meta uppercase tracking-label text-muted">
                      {cameraById.get(item.cameraId)?.name ?? item.cameraId}
                    </p>
                    <p className="mt-1 text-small text-muted">{item.caption}</p>
                  </Link>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

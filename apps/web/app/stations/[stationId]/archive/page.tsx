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
  getCamerasForStation,
  getMediaForStation,
  getRelatedMedia,
  getStationById,
  groupMediaByLocalDate,
  sortMediaByCaptureTime,
  type Camera,
} from "@/data";
import { formatDayHeading, formatFileSize, formatLocalDateTime, formatLocalTime, formatShortDate } from "@/lib/format";
import { formatMediaTypeLabel, formatPublicationLabel } from "@/lib/observation-badge";
import { getProcessingStatusTone, getPublicationStatusTone } from "@/lib/status-tone";
import {
  applyArchiveFilters,
  buildArchiveHref,
  buildMediaDetailHref,
  countActiveFilters,
  filtersToParamState,
  firstParam,
  hasActiveFilters,
  MEDIA_TYPES,
  parseArchiveFilters,
  PROCESSING_STATUSES,
  PUBLICATION_STATUSES,
  summariseFilters,
  type SearchParams,
} from "./filters";
import { TIME_OF_DAY_OPTIONS } from "./time-of-day";

const controlClassName =
  "w-full rounded-sm border border-border bg-surface px-3 py-2 text-small text-foreground";
const labelClassName = "flex flex-col gap-1 text-small text-foreground";

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

  const filters = parseArchiveFilters(search, cameras);
  const filtered = applyArchiveFilters(allStationMedia, filters);
  const activeFilters = hasActiveFilters(filters);
  const activeFilterCount = countActiveFilters(filters);
  const paramState = filtersToParamState(filters);
  const summaryParts = summariseFilters(filters);

  // --- selected observation: an explicit ?selected= wins; otherwise fall
  // back to the most recent item in the current results, so there is
  // always something to preview on first load rather than a blank panel ---
  const selectedParam = firstParam(search.selected);
  const explicitSelection = selectedParam
    ? allStationMedia.find((item) => item.id === selectedParam)
    : undefined;
  const defaultSelection = !explicitSelection && filtered.length > 0
    ? sortMediaByCaptureTime(filtered, "desc")[0]
    : undefined;
  const selectedObservation = explicitSelection ?? defaultSelection;

  // --- grouped, chronological results: most recent day first, each day oldest-to-newest ---
  const groups = groupMediaByLocalDate(sortMediaByCaptureTime(filtered, "asc"));
  const dayKeys = [...groups.keys()].sort().reverse();

  // --- date navigation always reflects the full station record, independent of other filters ---
  const availableDates = [...groupMediaByLocalDate(allStationMedia).keys()].sort();

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

      <details className="mt-10 border-t border-b border-border" open={activeFilters}>
        <summary className="cursor-pointer select-none py-4 text-small font-medium text-foreground">
          Filters{activeFilterCount > 0 ? ` (${activeFilterCount} active)` : ""}
        </summary>
        <form method="get" action={`/stations/${station.id}/archive`} className="pb-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <label className={labelClassName}>
              Camera
              <select name="camera" defaultValue={filters.camera?.id ?? ""} className={controlClassName}>
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
              <select name="mediaType" defaultValue={filters.mediaType ?? ""} className={controlClassName}>
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
              <select name="timeOfDay" defaultValue={filters.timeOfDay?.key ?? ""} className={controlClassName}>
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
              <input type="date" name="from" defaultValue={filters.from ?? ""} className={controlClassName} />
            </label>

            <label className={labelClassName}>
              To date
              <input type="date" name="to" defaultValue={filters.to ?? ""} className={controlClassName} />
            </label>

            <label className={labelClassName}>
              Processing status
              <select
                name="processingStatus"
                defaultValue={filters.processingStatus ?? ""}
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
                defaultValue={filters.publicationStatus ?? ""}
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
            {activeFilters && (
              <Link
                href={`/stations/${station.id}/archive`}
                className="text-small font-medium text-accent hover:text-accent-strong"
              >
                Clear filters
              </Link>
            )}
          </div>
        </form>
      </details>

      <div className="mt-6 flex flex-wrap items-center gap-x-2 gap-y-2 border-b border-border pb-6">
        <span className="text-meta uppercase tracking-label text-muted">Jump to date:</span>
        <Link
          href={buildArchiveHref(station.id, { ...paramState, date: undefined, from: undefined, to: undefined })}
          className={`text-small ${!filters.date && !filters.from && !filters.to ? "font-medium text-accent" : "text-muted hover:text-accent"}`}
        >
          All dates
        </Link>
        {availableDates.map((dateKey) => (
          <Link
            key={dateKey}
            href={buildArchiveHref(station.id, { ...paramState, date: dateKey, from: undefined, to: undefined })}
            className={`text-small ${filters.date === dateKey ? "font-medium text-accent" : "text-muted hover:text-accent"}`}
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
              <p className="text-meta uppercase tracking-label text-accent">
                {explicitSelection ? "Selected observation" : "Most recent observation"}
              </p>
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
              <div className="mt-4">
                <Link
                  href={buildMediaDetailHref(station.id, selectedObservation.id, paramState)}
                  className="text-small font-medium text-accent hover:text-accent-strong"
                >
                  View full details <span aria-hidden="true">&rarr;</span>
                </Link>
              </div>
              {selectedObservation.relatedMediaIds.length > 0 && (
                <div className="mt-4">
                  <p className="text-meta uppercase tracking-label text-muted">Related media</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {getRelatedMedia(selectedObservation.id, allStationMedia).map((related) => (
                      <Link
                        key={related.id}
                        href={buildArchiveHref(station.id, { ...paramState, selected: related.id })}
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
          action={activeFilters ? { label: "Clear filters", href: `/stations/${station.id}/archive` } : undefined}
        />
      ) : (
        <div className="mt-10 space-y-12">
          {dayKeys.map((dayKey) => (
            <section key={dayKey}>
              <h2 className="font-display text-heading-md text-foreground">
                {formatDayHeading(dayKey)}
              </h2>
              <div className="mt-4 grid grid-cols-2 gap-6 sm:grid-cols-3 lg:grid-cols-4">
                {groups.get(dayKey)!.map((item) => {
                  const isSelected = selectedObservation?.id === item.id;
                  return (
                    <Link
                      key={item.id}
                      href={buildArchiveHref(station.id, { ...paramState, selected: item.id })}
                      aria-current={isSelected ? "true" : undefined}
                      className={`block border-t-2 pt-3 ${isSelected ? "border-accent" : "border-border"}`}
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
                      {isSelected && (
                        <p className="mt-1 text-meta uppercase tracking-label text-accent">
                          Currently previewed above
                        </p>
                      )}
                    </Link>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

import type { Metadata } from "next";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ObservationThumbnail } from "@/components/ui/observation-thumbnail";
import {
  getAllCameras,
  getAllMedia,
  getAllStations,
  sortMediaByCaptureTime,
  type Camera,
  type Station,
} from "@/data";
import { formatLocalDateTime } from "@/lib/format";
import { formatMediaTypeLabel, formatPublicationLabel } from "@/lib/observation-badge";
import {
  applyObservationFilters,
  buildObservationsHref,
  countActiveFilters,
  filtersToParamState,
  hasActiveFilters,
  MEDIA_TYPES,
  PAGE_SIZE,
  parseObservationFilters,
  PROCESSING_STATUSES,
  PUBLICATION_STATUSES,
  summariseFilters,
  TIME_OF_DAY_OPTIONS,
  type SearchParams,
} from "./filters";

export const metadata: Metadata = {
  title: "Observations",
};

const controlClassName =
  "w-full rounded-sm border border-border bg-surface px-3 py-2 text-small text-foreground";
const labelClassName = "flex flex-col gap-1 text-small text-foreground";

export default async function ObservationsPage({
  searchParams,
}: PageProps<"/observations">) {
  const search: SearchParams = await searchParams;

  const stations = getAllStations();
  const cameras = getAllCameras();
  const allMedia = getAllMedia();
  const stationById = new Map<string, Station>(stations.map((station) => [station.id, station]));
  const cameraById = new Map<string, Camera>(cameras.map((camera) => [camera.id, camera]));

  const availableStates = [...new Set(stations.map((station) => station.state))].sort();
  const availableRegions = [...new Set(stations.map((station) => station.region))].sort();

  const filters = parseObservationFilters(search, stations, cameras);
  const filtered = sortMediaByCaptureTime(applyObservationFilters(allMedia, filters, stations), "desc");
  const activeFilters = hasActiveFilters(filters);
  const activeFilterCount = countActiveFilters(filters);
  const paramState = filtersToParamState(filters);
  const summaryParts = summariseFilters(filters);

  const cameraOptions = filters.station ? cameras.filter((camera) => camera.stationId === filters.station!.id) : cameras;

  const totalCount = filtered.length;
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));
  const page = Math.min(Math.max(1, filters.page), totalPages);
  const pageStart = (page - 1) * PAGE_SIZE;
  const pageItems = filtered.slice(pageStart, pageStart + PAGE_SIZE);
  const rangeStart = totalCount === 0 ? 0 : pageStart + 1;
  const rangeEnd = Math.min(pageStart + PAGE_SIZE, totalCount);

  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      <p className="text-meta uppercase tracking-label text-accent">Observation archive</p>
      <h1 className="mt-2 font-display text-display-md text-foreground">
        Coastal observations across the AusCIN network
      </h1>
      <p className="mt-2 text-meta text-muted">
        Sample development record &mdash; not an operational AusCIN feed. Every station, camera
        and image below is a synthetic fixture for local development and testing.
      </p>

      <p className="mt-6 max-w-2xl text-body text-muted">
        AusCIN brings together fixed reference cameras, lidar scanners, existing camera
        infrastructure and CoastSnap observations from stations around the Australian coast. Each
        record keeps its station, camera and capture time, so a single search can follow coastal
        change across the network rather than one site at a time.
      </p>

      <details className="mt-10 border-t border-b border-border" open={activeFilters}>
        <summary className="cursor-pointer select-none py-4 text-small font-medium text-foreground">
          Filters{activeFilterCount > 0 ? ` (${activeFilterCount} active)` : ""}
        </summary>
        <form method="get" action="/observations" className="pb-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <label className={labelClassName}>
              Station
              <select name="station" defaultValue={filters.station?.id ?? ""} className={controlClassName}>
                <option value="">All stations</option>
                {stations.map((station) => (
                  <option key={station.id} value={station.id}>
                    {station.name}
                  </option>
                ))}
              </select>
            </label>

            <label className={labelClassName}>
              State or territory
              <select name="state" defaultValue={filters.state ?? ""} className={controlClassName}>
                <option value="">All states</option>
                {availableStates.map((state) => (
                  <option key={state} value={state}>
                    {state}
                  </option>
                ))}
              </select>
            </label>

            <label className={labelClassName}>
              Region
              <select name="region" defaultValue={filters.region ?? ""} className={controlClassName}>
                <option value="">All regions</option>
                {availableRegions.map((region) => (
                  <option key={region} value={region}>
                    {region}
                  </option>
                ))}
              </select>
            </label>

            <label className={labelClassName}>
              Camera
              <select name="camera" defaultValue={filters.camera?.id ?? ""} className={controlClassName}>
                <option value="">All cameras</option>
                {cameraOptions.map((camera) => (
                  <option key={camera.id} value={camera.id}>
                    {camera.name}
                    {!filters.station ? ` — ${stationById.get(camera.stationId)?.name ?? camera.stationId}` : ""}
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
              <Link href="/observations" className="text-small font-medium text-accent hover:text-accent-strong">
                Clear filters
              </Link>
            )}
          </div>
        </form>
      </details>

      <div className="mt-6 border-b border-border pb-6">
        <p className="text-small text-foreground">
          <span className="font-medium">{totalCount}</span> observation{totalCount === 1 ? "" : "s"}
          {" · "}
          {summaryParts.join(" · ")}
          {totalCount > 0 && (
            <>
              {" · "}showing {rangeStart}–{rangeEnd}
            </>
          )}
        </p>
        <p className="mt-2 max-w-2xl text-meta text-muted">
          Date filters match each observation&apos;s own station-local calendar day. A Perth
          morning and a Sydney morning can fall on different UTC dates but are matched by their
          local day, not a shared UTC window.
        </p>
      </div>

      {pageItems.length === 0 ? (
        <EmptyState
          className="mt-10"
          title="No observations match these filters"
          description="Try a different station, camera, date or status, or clear the filters to see the whole network record."
          action={activeFilters ? { label: "Clear filters", href: "/observations" } : undefined}
        />
      ) : (
        <>
          <div className="mt-10 grid grid-cols-2 gap-6 sm:grid-cols-3 lg:grid-cols-4">
            {pageItems.map((item) => {
              const station = stationById.get(item.stationId);
              const camera = cameraById.get(item.cameraId);
              return (
                <Link
                  key={item.id}
                  href={`/stations/${item.stationId}/archive/${item.id}`}
                  className="block border-t border-border pt-3"
                >
                  <ObservationThumbnail item={item} sizes="(min-width: 1024px) 25vw, 50vw" />
                  <p className="mt-2 text-small font-medium text-foreground">
                    {station?.name ?? item.stationId}
                  </p>
                  <p className="mt-1 text-meta uppercase tracking-label text-muted">
                    {station ? `${station.state} · ${station.region}` : ""}
                  </p>
                  <p className="mt-1 text-meta uppercase tracking-label text-muted">
                    {camera?.name ?? item.cameraId} · {formatMediaTypeLabel(item.mediaType)}
                  </p>
                  <p className="mt-1 text-meta uppercase tracking-label text-muted">
                    {formatLocalDateTime(item.capturedAtUtc, item.displayTimeZone)}
                  </p>
                  <p className="mt-1 text-small text-muted">{item.caption}</p>
                </Link>
              );
            })}
          </div>

          <div className="mt-10 flex items-center justify-between border-t border-border pt-6">
            {page > 1 ? (
              <Link
                href={buildObservationsHref({ ...paramState, page: String(page - 1) })}
                className="text-small font-medium text-accent hover:text-accent-strong"
              >
                &larr; Previous
              </Link>
            ) : (
              <span className="text-small text-muted" aria-disabled="true">
                &larr; Previous
              </span>
            )}
            <p className="text-meta uppercase tracking-label text-muted">
              Page {page} of {totalPages}
            </p>
            {page < totalPages ? (
              <Link
                href={buildObservationsHref({ ...paramState, page: String(page + 1) })}
                className="text-small font-medium text-accent hover:text-accent-strong"
              >
                Next &rarr;
              </Link>
            ) : (
              <span className="text-small text-muted" aria-disabled="true">
                Next &rarr;
              </span>
            )}
          </div>
        </>
      )}
    </div>
  );
}

import type { Metadata } from "next";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusLabel } from "@/components/ui/status-label";
import { getAllStations, getCamerasForStation, getMediaForStation, type Station } from "@/data";
import { getOperatingStatusTone } from "@/lib/status-tone";
import { applyMapFilters, countActiveFilters, hasActiveFilters, parseMapFilters, type SearchParams } from "./filters";
import { latitudeTicks, longitudeTicks, projectToPercent } from "./geo";

export const metadata: Metadata = {
  title: "Map",
};

const controlClassName =
  "w-full rounded-sm border border-border bg-surface px-3 py-2 text-small text-foreground";
const labelClassName = "flex flex-col gap-1 text-small text-foreground";

const OPERATING_STATUSES = ["active", "offline", "maintenance"] as const;

function markerToneClass(tone: ReturnType<typeof getOperatingStatusTone>): string {
  // Active stations get a solid fill; anything else a hollow ring — a shape
  // difference as well as a colour one, so status isn't colour-only.
  if (tone === "positive") return "border-accent bg-accent";
  return "border-secondary-accent bg-surface";
}

export default async function MapPage({ searchParams }: PageProps<"/map">) {
  const search: SearchParams = await searchParams;
  const stations = getAllStations();

  const availableStates = [...new Set(stations.map((station) => station.state))].sort();
  const availableRegions = [...new Set(stations.map((station) => station.region))].sort();

  const filters = parseMapFilters(search, stations);
  const filtered = applyMapFilters(stations, filters);
  const activeFilters = hasActiveFilters(filters);
  const activeFilterCount = countActiveFilters(filters);

  const summaryParts = [
    filters.state ?? "all states",
    ...(filters.region ? [filters.region] : []),
    ...(filters.status ? [filters.status] : []),
  ];

  const latTicks = latitudeTicks();
  const lonTicks = longitudeTicks();

  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      <p className="text-meta uppercase tracking-label text-accent">Observation network</p>
      <h1 className="mt-2 font-display text-display-md text-foreground">
        Coastal observation stations across Australia
      </h1>
      <p className="mt-2 text-meta text-muted">
        Sample development record &mdash; not an operational AusCIN feed. These six stations are
        fictional records used to build and test this map.
      </p>

      <p className="mt-6 max-w-2xl text-body text-muted">
        AusCIN&apos;s network combines fixed reference cameras, lidar scanners, existing camera
        infrastructure and CoastSnap observations. The sample stations plotted below use fixed
        cameras and, at Cape Mirrigan, a lidar reference scanner &mdash; positioned here by their
        recorded latitude and longitude.
      </p>

      <details className="mt-10 border-t border-b border-border" open={activeFilters}>
        <summary className="cursor-pointer select-none py-4 text-small font-medium text-foreground">
          Filters{activeFilterCount > 0 ? ` (${activeFilterCount} active)` : ""}
        </summary>
        <form method="get" action="/map" className="pb-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
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
              Operational status
              <select name="status" defaultValue={filters.status ?? ""} className={controlClassName}>
                <option value="">All statuses</option>
                {OPERATING_STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="mt-6 flex flex-wrap items-center gap-4">
            <Button type="submit">Apply filters</Button>
            {activeFilters && (
              <Link href="/map" className="text-small font-medium text-accent hover:text-accent-strong">
                Clear filters
              </Link>
            )}
          </div>
        </form>
      </details>

      <p className="mt-6 border-b border-border pb-6 text-small text-foreground">
        <span className="font-medium">{filtered.length}</span> of {stations.length} station
        {stations.length === 1 ? "" : "s"} &middot; {summaryParts.join(" · ")}
      </p>

      {filtered.length === 0 ? (
        <EmptyState
          className="mt-10"
          title="No stations match these filters"
          description="Try a different state, region or operational status, or clear the filters to see the whole network."
          action={activeFilters ? { label: "Clear filters", href: "/map" } : undefined}
        />
      ) : (
        <>
          <div className="mt-10 mx-auto max-w-2xl">
            <div
              className="relative aspect-[42/34] w-full border border-border bg-accent/5"
              role="group"
              aria-label="Map of Australia showing sample AusCIN station locations"
            >
              {/* Gridlines and edge labels: a plain latitude/longitude plot, not a decorative map. */}
              {latTicks.map((lat) => {
                const { yPercent } = projectToPercent(lat, 112);
                return (
                  <div key={lat} className="absolute inset-x-0" style={{ top: `${yPercent}%` }}>
                    <div className="border-t border-border/70" />
                    <span className="absolute left-1 top-1 text-meta text-muted">{Math.abs(lat)}&deg;S</span>
                  </div>
                );
              })}
              {lonTicks.map((lon) => {
                const { xPercent } = projectToPercent(-10, lon);
                return (
                  <div key={lon} className="absolute inset-y-0" style={{ left: `${xPercent}%` }}>
                    <div className="h-full border-l border-border/70" />
                    <span className="absolute bottom-1 left-1 text-meta text-muted">{lon}&deg;E</span>
                  </div>
                );
              })}

              <span className="absolute left-1 top-1/2 -translate-y-1/2 -rotate-90 text-meta uppercase tracking-label text-muted">
                Indian Ocean
              </span>
              <span className="absolute right-1 top-1/2 -translate-y-1/2 rotate-90 text-meta uppercase tracking-label text-muted">
                Pacific Ocean
              </span>
              <span className="absolute right-1 top-1 text-meta uppercase tracking-label text-muted">
                Arafura Sea
              </span>

              {filtered.map((station) => {
                const { xPercent, yPercent } = projectToPercent(station.latitude, station.longitude);
                const tone = getOperatingStatusTone(station.operationalStatus);
                const cameraCount = getCamerasForStation(station.id).length;
                const mediaCount = getMediaForStation(station.id).length;
                return (
                  <div
                    key={station.id}
                    className="group absolute z-10 -translate-x-1/2 -translate-y-1/2"
                    style={{ left: `${xPercent}%`, top: `${yPercent}%` }}
                  >
                    <Link
                      href={`/stations/${station.id}`}
                      aria-label={`${station.name}, ${station.state}, ${station.region}. Status: ${station.operationalStatus}. ${cameraCount} cameras, ${mediaCount} observations.`}
                      className={`block h-3.5 w-3.5 rounded-full border-2 ${markerToneClass(tone)}`}
                    />
                    <div
                      className="pointer-events-none absolute left-1/2 top-full z-20 mt-2 hidden w-52 -translate-x-1/2 border border-border bg-surface p-3 text-left group-hover:block group-focus-within:block"
                      aria-hidden="true"
                    >
                      <p className="text-small font-medium text-foreground">{station.name}</p>
                      <p className="mt-1 text-meta uppercase tracking-label text-muted">
                        {station.state} &middot; {station.region}
                      </p>
                      <p className="mt-1 text-meta uppercase tracking-label text-muted">
                        {station.operationalStatus} &middot; {cameraCount} cameras &middot; {mediaCount}{" "}
                        observations
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
            <p className="mt-3 flex flex-wrap items-center gap-4 text-meta uppercase tracking-label text-muted">
              <span className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full border-2 border-accent bg-accent" aria-hidden="true" />
                Active
              </span>
              <span className="flex items-center gap-2">
                <span
                  className="h-2.5 w-2.5 rounded-full border-2 border-secondary-accent bg-surface"
                  aria-hidden="true"
                />
                Offline / maintenance
              </span>
            </p>
            <p className="mt-2 text-meta text-muted">
              Bounded by the Indian Ocean to the west, the Pacific Ocean to the east, the Arafura
              Sea to the north and the Southern Ocean to the south.
            </p>
          </div>

          <section className="mt-16 border-t border-border pt-10">
            <h2 className="font-display text-heading-lg text-foreground">Station records</h2>
            <ul className="mt-6 divide-y divide-border">
              {filtered.map((station) => (
                <StationRow key={station.id} station={station} />
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}

function StationRow({ station }: { station: Station }) {
  const cameraCount = getCamerasForStation(station.id).length;
  const mediaCount = getMediaForStation(station.id).length;

  return (
    <li className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2 py-4">
      <div className="min-w-0">
        <Link
          href={`/stations/${station.id}`}
          className="text-small font-medium text-foreground hover:text-accent"
        >
          {station.name}
        </Link>
        <p className="mt-1 text-meta uppercase tracking-label text-muted">
          {station.state} &middot; {station.region} &middot; Station ID {station.id}
        </p>
        <div className="mt-1">
          <StatusLabel label={station.operationalStatus} tone={getOperatingStatusTone(station.operationalStatus)} />
        </div>
      </div>
      <div className="flex flex-col items-end gap-1 text-right">
        <p className="text-meta uppercase tracking-label text-muted">
          {cameraCount} camera{cameraCount === 1 ? "" : "s"} &middot; {mediaCount} observation
          {mediaCount === 1 ? "" : "s"}
        </p>
        <div className="flex flex-wrap justify-end gap-x-4 gap-y-1">
          <Link
            href={`/stations/${station.id}`}
            className="text-small font-medium text-accent hover:text-accent-strong"
          >
            Station record &rarr;
          </Link>
          <Link
            href={`/stations/${station.id}/archive`}
            className="text-small font-medium text-accent hover:text-accent-strong"
          >
            Archive &rarr;
          </Link>
        </div>
      </div>
    </li>
  );
}

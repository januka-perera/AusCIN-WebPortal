import type { Metadata } from "next";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusLabel } from "@/components/ui/status-label";
import { coastSnapRepository, getCoastSnapDataSource, repository } from "@/data";
import { applyMapFilters, countActiveFilters, hasActiveFilters, parseMapFilters, type SearchParams } from "./filters";
import { describeLocationCounts, MAP_LOCATION_KIND_LABELS } from "./labels";
import { loadMapLocations } from "./locations";
import { MapLoader } from "./map-loader";
import { resolveTileConfig } from "./tile-config";
import type { MapLocation } from "./types";

export const metadata: Metadata = {
  title: "Map",
};

const controlClassName =
  "w-full rounded-sm border border-border bg-surface px-3 py-2 text-small text-foreground";
const labelClassName = "flex flex-col gap-1 text-small text-foreground";

const OPERATING_STATUSES = ["active", "offline", "maintenance"] as const;

export default async function MapPage({ searchParams }: PageProps<"/map">) {
  const search: SearchParams = await searchParams;
  const coastSnapSource = getCoastSnapDataSource();
  const { locations, coastSnapUnavailable } = await loadMapLocations(repository, coastSnapRepository);
  const stationCount = locations.filter((location) => location.kind === "station").length;
  const coastSnapCount = locations.length - stationCount;

  const availableStates = [...new Set(locations.map((location) => location.state))].sort();
  const availableRegions = [...new Set(locations.map((location) => location.region))].sort();

  const filters = parseMapFilters(search, locations);
  const filtered = applyMapFilters(locations, filters);
  const activeFilters = hasActiveFilters(filters);
  const activeFilterCount = countActiveFilters(filters);

  const summaryParts = [
    filters.state ?? "all states",
    ...(filters.region ? [filters.region] : []),
    ...(filters.status ? [filters.status] : []),
  ];

  const tileConfig = resolveTileConfig(
    process.env.NEXT_PUBLIC_MAP_TILE_URL,
    process.env.NEXT_PUBLIC_MAP_TILE_ATTRIBUTION,
  );

  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      <p className="text-meta uppercase tracking-label text-accent">Observation network</p>
      <h1 className="mt-2 font-display text-display-md text-foreground">
        Coastal observation locations across Australia
      </h1>
      <p className="mt-2 text-meta text-muted">
        Sample development record &mdash; not an operational AusCIN feed. The {stationCount} fixed
        station{stationCount === 1 ? "" : "s"} are fictional records used to build and test this map.{" "}
        {coastSnapSource === "sample"
          ? "The CoastSnap sites are synthetic sample fixtures too."
          : "CoastSnap sites come from the CoastSnap catalogue; each site's own page says if it is a test record."}
      </p>

      <p className="mt-6 max-w-2xl text-body text-muted">
        AusCIN&apos;s network combines fixed reference cameras, lidar scanners, existing camera
        infrastructure and CoastSnap observations. The fixed stations plotted below use installed
        cameras and, at Cape Mirrigan, a lidar reference scanner. CoastSnap sites are community
        photo points, plotted only once they have at least one published photo; in the catalogue,
        their location must also be confirmed from the source records.
      </p>
      {coastSnapUnavailable && (
        <p role="status" className="mt-4 max-w-2xl border-l-2 border-secondary-accent pl-4 text-small text-foreground">
          CoastSnap sites couldn&apos;t be loaded from the catalogue just now, so only fixed stations
          are shown. Please try again shortly.
        </p>
      )}

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
        <span className="font-medium">{filtered.length}</span> of {locations.length} location
        {locations.length === 1 ? "" : "s"} ({stationCount} fixed station{stationCount === 1 ? "" : "s"},{" "}
        {coastSnapCount} CoastSnap site{coastSnapCount === 1 ? "" : "s"}) &middot; {summaryParts.join(" · ")}
      </p>

      {locations.length === 0 ? (
        <EmptyState
          className="mt-10"
          title="No locations to show yet"
          description="No fixed stations or published CoastSnap sites are available to plot."
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          className="mt-10"
          title="No locations match these filters"
          description="Try a different state, region or operational status, or clear the filters to see the whole network."
          action={activeFilters ? { label: "Clear filters", href: "/map" } : undefined}
        />
      ) : (
        <>
          <div className="mt-10">
            {tileConfig.available ? (
              <MapLoader
                key={filtered.map((location) => location.anchorId).join(",")}
                locations={filtered}
                tileConfig={tileConfig}
              />
            ) : (
              <EmptyState
                title="Map unavailable"
                description="No basemap tile source is configured for this preview. All matching locations are listed below."
              />
            )}
            {tileConfig.available && tileConfig.isDevDefault && (
              <p className="mt-2 text-meta text-muted">
                Uses OpenStreetMap&apos;s public tile server for local development only &mdash; set{" "}
                <code>NEXT_PUBLIC_MAP_TILE_URL</code> to an approved tile provider before any
                production deployment.
              </p>
            )}
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
          </div>

          <section className="mt-16 border-t border-border pt-10">
            <h2 className="font-display text-heading-lg text-foreground">Location records</h2>
            <ul className="mt-6 divide-y divide-border">
              {filtered.map((location) => (
                <LocationRow key={location.anchorId} location={location} />
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}

function LocationRow({ location }: { location: MapLocation }) {
  return (
    <li
      id={location.anchorId}
      className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2 py-4 [&:target]:bg-accent/5"
    >
      <div className="min-w-0">
        <Link href={location.href} className="text-small font-medium text-foreground hover:text-accent">
          {location.name}
        </Link>
        <p className="mt-1 text-meta uppercase tracking-label text-muted">
          {MAP_LOCATION_KIND_LABELS[location.kind]} &middot; {location.state} &middot; {location.region} &middot;{" "}
          {location.kind === "coastsnap" ? "Site" : "Station"} ID {location.id}
        </p>
        <div className="mt-1">
          <StatusLabel label={location.operationalStatus} tone={location.tone} />
        </div>
      </div>
      <div className="flex flex-col items-end gap-1 text-right">
        <p className="text-meta uppercase tracking-label text-muted">{describeLocationCounts(location)}</p>
        <div className="flex flex-wrap justify-end gap-x-4 gap-y-1">
          <Link href={location.href} className="text-small font-medium text-accent hover:text-accent-strong">
            {location.kind === "coastsnap" ? "Site record" : "Station record"} &rarr;
          </Link>
          <Link
            href={location.archiveHref}
            className="text-small font-medium text-accent hover:text-accent-strong"
          >
            Archive &rarr;
          </Link>
        </div>
      </div>
    </li>
  );
}

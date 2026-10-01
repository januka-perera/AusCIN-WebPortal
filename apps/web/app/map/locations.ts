import { CoastSnapApiError } from "@/data/coastsnap-http-repository";
import type { AusCinRepository, CoastSnapRepository, CoastSnapSite, Station } from "@/data";
import { getOperatingStatusTone } from "@/lib/status-tone";
import type { MapLocation } from "./types";

export function stationToMapLocation(station: Station, cameraCount: number, observationCount: number): MapLocation {
  return {
    id: station.id,
    kind: "station",
    name: station.name,
    state: station.state,
    region: station.region,
    latitude: station.latitude,
    longitude: station.longitude,
    operationalStatus: station.operationalStatus,
    tone: getOperatingStatusTone(station.operationalStatus),
    cameraCount,
    observationCount,
    href: `/stations/${station.id}`,
    archiveHref: `/stations/${station.id}/archive`,
    anchorId: `station-${station.id}`,
  };
}

export function coastSnapSiteToMapLocation(site: CoastSnapSite, observationCount: number): MapLocation {
  return {
    id: site.id,
    kind: "coastsnap",
    name: site.name,
    state: site.state,
    region: site.region,
    // Passed through unchanged: for API sites, the worker's confirmed coordinate.
    latitude: site.latitude,
    longitude: site.longitude,
    operationalStatus: site.status,
    tone: getOperatingStatusTone(site.status),
    cameraCount: null,
    observationCount,
    href: `/coastsnap/${site.id}`,
    archiveHref: `/coastsnap/${site.id}/archive`,
    anchorId: `coastsnap-${site.id}`,
  };
}

/** Defence in depth: the API and the HTTP repository already validate coordinates, but nothing unplottable reaches Leaflet. */
export function hasPlottableCoordinates(location: Pick<MapLocation, "latitude" | "longitude">): boolean {
  return (
    Number.isFinite(location.latitude) &&
    Number.isFinite(location.longitude) &&
    Math.abs(location.latitude) <= 90 &&
    Math.abs(location.longitude) <= 180
  );
}

export type MapLocationsResult = {
  /** Fixed stations first, then CoastSnap sites, each in repository order. */
  locations: MapLocation[];
  /** True when the CoastSnap catalogue failed; fixed stations are still returned. */
  coastSnapUnavailable: boolean;
};

/**
 * Every plottable location for the map.
 *
 * CoastSnap counts come from the `total` of a one-item page, so the archive
 * itself is never loaded. Sites with no observations are left out: the
 * catalogue API already omits them, and this applies the same rule to the
 * sample repository. A CoastSnap catalogue failure (`CoastSnapApiError`) is
 * reported rather than thrown, so the fixed stations still render.
 */
export async function loadMapLocations(
  stationRepository: AusCinRepository,
  coastSnap: CoastSnapRepository,
): Promise<MapLocationsResult> {
  const stations = await stationRepository.listStations();
  const stationLocations = await Promise.all(
    stations.map(async (station) =>
      stationToMapLocation(
        station,
        (await stationRepository.listCamerasForStation(station.id)).length,
        (await stationRepository.listStationObservations(station.id, {})).length,
      ),
    ),
  );

  let coastSnapLocations: MapLocation[] = [];
  let coastSnapUnavailable = false;
  try {
    const sites = await coastSnap.listSites();
    const counted = await Promise.all(
      sites.map(async (site) => {
        const { total } = await coastSnap.listObservationsForSitePaginated(site.id, {}, { page: 1, pageSize: 1 });
        return coastSnapSiteToMapLocation(site, total);
      }),
    );
    coastSnapLocations = counted.filter((location) => location.observationCount > 0);
  } catch (error) {
    if (!(error instanceof CoastSnapApiError)) throw error;
    coastSnapUnavailable = true;
  }

  return {
    locations: [...stationLocations, ...coastSnapLocations].filter(hasPlottableCoordinates),
    coastSnapUnavailable,
  };
}

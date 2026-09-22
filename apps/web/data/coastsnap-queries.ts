import { COASTSNAP_OBSERVATIONS, COASTSNAP_SITES } from "./sample";
import { sortMediaByCaptureTime } from "./queries";
import type { CoastSnapObservation, CoastSnapSite } from "./types/coastsnap";

/**
 * Typed, synchronous, dependency-free data-access helpers over the
 * CoastSnap sample fixtures — the same shape as `data/queries.ts`'s
 * station/camera/media helpers, kept in a separate file because
 * CoastSnap is a separate frontend area with its own data shape (see
 * `data/types/coastsnap.ts`). Every function accepts the data set it
 * should read as an optional final argument (defaulting to the sample
 * data), for the same reasons as the station helpers: easy to unit test
 * with small fixture arrays, easy to swap for a real API client later.
 */

export function getAllCoastSnapSites(sites: CoastSnapSite[] = COASTSNAP_SITES): CoastSnapSite[] {
  return sites;
}

export function getCoastSnapSiteById(
  id: string,
  sites: CoastSnapSite[] = COASTSNAP_SITES,
): CoastSnapSite | undefined {
  return sites.find((site) => site.id === id);
}

export function getAllCoastSnapObservations(
  observations: CoastSnapObservation[] = COASTSNAP_OBSERVATIONS,
): CoastSnapObservation[] {
  return observations;
}

export function getObservationsForCoastSnapSite(
  siteId: string,
  observations: CoastSnapObservation[] = COASTSNAP_OBSERVATIONS,
): CoastSnapObservation[] {
  return observations.filter((observation) => observation.siteId === siteId);
}

export function getCoastSnapObservationById(
  observationId: string,
  observations: CoastSnapObservation[] = COASTSNAP_OBSERVATIONS,
): CoastSnapObservation | undefined {
  return observations.find((observation) => observation.id === observationId);
}

export type CoastSnapObservationDateRange = {
  earliest: CoastSnapObservation;
  latest: CoastSnapObservation;
};

/**
 * The earliest and latest observation captured at a site, regardless of
 * processing or publication status. Returns undefined for a site with
 * no observations at all, rather than an invalid or empty-looking range.
 */
export function getObservationDateRangeForSite(
  siteId: string,
  observations: CoastSnapObservation[] = COASTSNAP_OBSERVATIONS,
): CoastSnapObservationDateRange | undefined {
  const siteObservations = getObservationsForCoastSnapSite(siteId, observations);
  if (siteObservations.length === 0) return undefined;
  const sorted = sortMediaByCaptureTime(siteObservations, "asc");
  return { earliest: sorted[0], latest: sorted[sorted.length - 1] };
}

/**
 * The single most recent presentable (processed and public) observation
 * from each site that has one. Sites with no presentable observations —
 * including a site with no observations at all — are skipped rather
 * than shown with a broken or embargoed item. Mirrors
 * `getLatestObservationPerStation` in `data/queries.ts`.
 */
export function getLatestObservationPerCoastSnapSite(
  sites: CoastSnapSite[] = COASTSNAP_SITES,
  observations: CoastSnapObservation[] = COASTSNAP_OBSERVATIONS,
): CoastSnapObservation[] {
  const latestPerSite: CoastSnapObservation[] = [];
  for (const site of sites) {
    const presentable = observations.filter(
      (observation) =>
        observation.siteId === site.id &&
        observation.processingStatus === "processed" &&
        observation.publicationStatus === "public",
    );
    if (presentable.length === 0) continue;
    latestPerSite.push(sortMediaByCaptureTime(presentable, "desc")[0]);
  }
  return sortMediaByCaptureTime(latestPerSite, "desc");
}

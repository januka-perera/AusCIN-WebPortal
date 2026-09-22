import { getLocalDateKey } from "@/lib/format";
import { COASTSNAP_OBSERVATIONS, COASTSNAP_SITES } from "./sample";
import { sortMediaByCaptureTime } from "./queries";
import type { CoastSnapObservation, CoastSnapSite } from "./types/coastsnap";
import type { MediaType } from "./types/media";

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

/**
 * Looks up an observation scoped to one site, exactly as
 * `getMediaById(mediaId, getMediaForStation(stationId))` scopes a
 * station's media in `data/queries.ts`. An observation ID that belongs
 * to a different site is never returned, even if it exists elsewhere in
 * the dataset — this is what prevents a media item from one CoastSnap
 * site being displayed under another site's URL.
 */
export function getCoastSnapObservationForSite(
  siteId: string,
  observationId: string,
  observations: CoastSnapObservation[] = COASTSNAP_OBSERVATIONS,
): CoastSnapObservation | undefined {
  return getCoastSnapObservationById(observationId, getObservationsForCoastSnapSite(siteId, observations));
}

export function filterCoastSnapByMediaType(
  observations: CoastSnapObservation[],
  mediaType: MediaType,
): CoastSnapObservation[] {
  return observations.filter((observation) => observation.mediaType === mediaType);
}

/**
 * Filters to observations whose local calendar date (in each
 * observation's own displayTimeZone) matches the given "YYYY-MM-DD"
 * key. Timezone-aware, mirroring `filterMediaByLocalDate` in
 * `data/queries.ts`, implemented independently for CoastSnapObservation
 * rather than shared, per this stage's data-separation requirement.
 */
export function filterCoastSnapByLocalDate(
  observations: CoastSnapObservation[],
  localDateKey: string,
): CoastSnapObservation[] {
  return observations.filter(
    (observation) => getLocalDateKey(observation.capturedAtUtc, observation.displayTimeZone) === localDateKey,
  );
}

/**
 * Filters to observations whose local calendar date falls within
 * [fromDateKey, toDateKey], inclusive. Either bound may be omitted for
 * an open-ended range; a plain string comparison on "YYYY-MM-DD" keys,
 * so a reversed or otherwise invalid range naturally yields no matches
 * rather than needing special handling. Mirrors
 * `filterMediaByLocalDateRange` in `data/queries.ts`.
 */
export function filterCoastSnapByLocalDateRange(
  observations: CoastSnapObservation[],
  fromDateKey: string | undefined,
  toDateKey: string | undefined,
): CoastSnapObservation[] {
  if (!fromDateKey && !toDateKey) return observations;
  return observations.filter((observation) => {
    const key = getLocalDateKey(observation.capturedAtUtc, observation.displayTimeZone);
    if (fromDateKey && key < fromDateKey) return false;
    if (toDateKey && key > toDateKey) return false;
    return true;
  });
}

export type CoastSnapObservationFilters = {
  mediaType?: MediaType;
  date?: string;
  from?: string;
  to?: string;
};

/** Applies the media-type and date/range filters additively (AND). */
export function applyCoastSnapObservationFilters(
  observations: CoastSnapObservation[],
  filters: CoastSnapObservationFilters,
): CoastSnapObservation[] {
  let result = observations;
  if (filters.mediaType) result = filterCoastSnapByMediaType(result, filters.mediaType);
  if (filters.date) {
    result = filterCoastSnapByLocalDate(result, filters.date);
  } else if (filters.from || filters.to) {
    result = filterCoastSnapByLocalDateRange(result, filters.from, filters.to);
  }
  return result;
}

/** A site's observations, scoped to the site and then filtered — the composition the site archive page needs. */
export function getFilteredObservationsForCoastSnapSite(
  siteId: string,
  filters: CoastSnapObservationFilters,
  observations: CoastSnapObservation[] = COASTSNAP_OBSERVATIONS,
): CoastSnapObservation[] {
  return applyCoastSnapObservationFilters(getObservationsForCoastSnapSite(siteId, observations), filters);
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

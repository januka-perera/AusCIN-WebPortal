import {
  countMediaFilterFields,
  firstParam,
  hasMediaFilterFields,
  MEDIA_TYPES,
  parseMediaFilterFields,
  PROCESSING_STATUSES,
  PUBLICATION_STATUSES,
  summariseMediaFilterFields,
  type MediaFilterFields,
  type SearchParams,
} from "@/lib/media-filters";

/**
 * The station archive's filter vocabulary is exactly the shared media
 * filter fields — a single station is already fixed by the route, so
 * there's no station/state/region scoping to add on top. This file is a
 * thin, route-named adapter over lib/media-filters.ts (parsing logic
 * lives there, once) plus this route's own URL and summary shape.
 * Applying the parsed filters is a repository concern — see
 * data/repository.ts's listStationObservations — not exported here. The
 * media detail page reuses these exports too, so a detail page can be
 * reached with the same filter context.
 */

export { firstParam, MEDIA_TYPES, PROCESSING_STATUSES, PUBLICATION_STATUSES };
export type { SearchParams };

export type ArchiveFilters = MediaFilterFields;

export const parseArchiveFilters = parseMediaFilterFields;
export const hasActiveFilters = hasMediaFilterFields;
export const countActiveFilters = countMediaFilterFields;

export type FilterParamState = {
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

export function filtersToParamState(filters: ArchiveFilters): FilterParamState {
  return {
    camera: filters.camera?.id,
    mediaType: filters.mediaType,
    date: filters.date,
    from: filters.from,
    to: filters.to,
    timeOfDay: filters.timeOfDay?.key,
    processingStatus: filters.processingStatus,
    publicationStatus: filters.publicationStatus,
  };
}

export function buildArchiveHref(stationId: string, state: FilterParamState): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(state)) {
    if (value) params.set(key, value);
  }
  const query = params.toString();
  return `/stations/${stationId}/archive${query ? `?${query}` : ""}`;
}

/** Same query-param context as buildArchiveHref, but pointed at a media item's detail page. */
export function buildMediaDetailHref(
  stationId: string,
  mediaId: string,
  state: FilterParamState,
): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(state)) {
    if (key === "selected" || !value) continue; // meaningless on the detail page itself
    params.set(key, value);
  }
  const query = params.toString();
  return `/stations/${stationId}/archive/${mediaId}${query ? `?${query}` : ""}`;
}

export function summariseFilters(filters: ArchiveFilters): string[] {
  return [filters.camera ? filters.camera.name : "all cameras", ...summariseMediaFilterFields(filters)];
}

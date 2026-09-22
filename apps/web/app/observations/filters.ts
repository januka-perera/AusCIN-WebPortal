import {
  countActiveObservationFilters,
  firstParam,
  hasActiveObservationFilters,
  MEDIA_TYPES,
  parseObservationFilters,
  PROCESSING_STATUSES,
  PUBLICATION_STATUSES,
  summariseMediaFilterFields,
  type ObservationFilters,
  type SearchParams,
} from "@/lib/media-filters";
import { DEFAULT_PAGE_SIZE } from "@/lib/pagination";
import { TIME_OF_DAY_OPTIONS } from "@/lib/time-of-day";

/**
 * This route's parsing logic lives in lib/media-filters.ts (shared with
 * the station archive's underlying media fields); applying it is a
 * repository concern — see data/repository.ts's listObservations — not
 * exported here. This file keeps only what's genuinely specific to
 * /observations: its page size, its URL shape, and its summary sentence.
 */

export { firstParam, MEDIA_TYPES, parseObservationFilters, PROCESSING_STATUSES, PUBLICATION_STATUSES, TIME_OF_DAY_OPTIONS };
export type { ObservationFilters, SearchParams };

export const PAGE_SIZE = DEFAULT_PAGE_SIZE;

export const hasActiveFilters = hasActiveObservationFilters;
export const countActiveFilters = countActiveObservationFilters;

export type ObservationParamState = {
  station?: string;
  state?: string;
  region?: string;
  camera?: string;
  mediaType?: string;
  date?: string;
  from?: string;
  to?: string;
  timeOfDay?: string;
  processingStatus?: string;
  publicationStatus?: string;
  page?: string;
};

/** The URL param state for the current filters, excluding page (callers set page explicitly per link). */
export function filtersToParamState(filters: ObservationFilters): ObservationParamState {
  return {
    station: filters.station?.id,
    state: filters.state,
    region: filters.region,
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

export function buildObservationsHref(state: ObservationParamState): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(state)) {
    if (value) params.set(key, value);
  }
  const query = params.toString();
  return `/observations${query ? `?${query}` : ""}`;
}

export function summariseFilters(filters: ObservationFilters): string[] {
  const parts: string[] = [];
  parts.push(
    filters.station
      ? filters.station.name
      : filters.state
        ? `${filters.state} stations`
        : filters.region
          ? filters.region
          : "all stations",
  );
  if (filters.camera) parts.push(filters.camera.name);
  return [...parts, ...summariseMediaFilterFields(filters)];
}

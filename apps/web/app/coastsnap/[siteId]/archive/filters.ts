import type { CoastSnapObservationFilters, MediaType } from "@/data";
import { formatDayHeading, formatShortDate } from "@/lib/format";
import { formatMediaTypeLabel } from "@/lib/observation-badge";

/**
 * The CoastSnap site archive's own filter vocabulary. Deliberately not
 * shared with `lib/media-filters.ts` (the station archive/observations
 * filter module) — this stage keeps CoastSnap's routes and data access
 * independent of the station model until the CoastSnap data shape is
 * proven, even where the two happen to look similar (media type, date,
 * date range, page).
 */

export type SearchParams = Record<string, string | string[] | undefined>;

export function firstParam(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

function isValidDateKey(value: string | undefined): value is string {
  return value !== undefined && DATE_PATTERN.test(value);
}

export const MEDIA_TYPES: MediaType[] = ["image", "composite", "timelapse"];

export const PAGE_SIZE = 4;

export type CoastSnapArchiveFilters = CoastSnapObservationFilters & { page: number };

/** Parses and validates the archive's query params. Invalid or unrecognised values are dropped, not rejected. */
export function parseCoastSnapArchiveFilters(search: SearchParams): CoastSnapArchiveFilters {
  const mediaTypeParam = firstParam(search.mediaType);
  const mediaType = MEDIA_TYPES.find((type) => type === mediaTypeParam);

  const dateParam = firstParam(search.date);
  const date = isValidDateKey(dateParam) ? dateParam : undefined;

  const fromParam = firstParam(search.from);
  const toParam = firstParam(search.to);
  const from = isValidDateKey(fromParam) ? fromParam : undefined;
  const to = isValidDateKey(toParam) ? toParam : undefined;

  const pageParam = firstParam(search.page);
  const parsedPage = pageParam ? Number.parseInt(pageParam, 10) : 1;
  const page = Number.isFinite(parsedPage) && parsedPage > 0 ? parsedPage : 1;

  return { mediaType, date, from, to, page };
}

export function hasActiveFilters(filters: CoastSnapArchiveFilters): boolean {
  return Boolean(filters.mediaType || filters.date || filters.from || filters.to);
}

/** Counts a date and a range together as a single active group, matching the station archive's convention. */
export function countActiveFilters(filters: CoastSnapArchiveFilters): number {
  let count = 0;
  if (filters.mediaType) count += 1;
  if (filters.date || filters.from || filters.to) count += 1;
  return count;
}

export type CoastSnapArchiveParamState = {
  mediaType?: string;
  date?: string;
  from?: string;
  to?: string;
  page?: string;
};

/** The URL param state for the current filters, excluding page (callers set page explicitly per link). */
export function filtersToParamState(filters: CoastSnapArchiveFilters): CoastSnapArchiveParamState {
  return { mediaType: filters.mediaType, date: filters.date, from: filters.from, to: filters.to };
}

export function buildArchiveHref(siteId: string, state: CoastSnapArchiveParamState): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(state)) {
    if (value) params.set(key, value);
  }
  const query = params.toString();
  return `/coastsnap/${siteId}/archive${query ? `?${query}` : ""}`;
}

export function summariseFilters(filters: CoastSnapArchiveFilters): string[] {
  const parts: string[] = [];
  if (filters.mediaType) parts.push(formatMediaTypeLabel(filters.mediaType).toLowerCase());
  if (filters.date) {
    parts.push(formatDayHeading(filters.date));
  } else if (filters.from || filters.to) {
    parts.push(
      `${filters.from ? formatShortDate(filters.from) : "start"} to ${filters.to ? formatShortDate(filters.to) : "now"}`,
    );
  }
  return parts;
}

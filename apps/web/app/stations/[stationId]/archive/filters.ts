import {
  filterMediaByLocalDate,
  filterMediaByLocalDateRange,
  filterMediaByProcessingStatus,
  filterMediaByPublicationStatus,
  filterMediaByTimeOfDay,
  filterMediaByType,
  getMediaForCamera,
  type Camera,
  type MediaItem,
  type MediaType,
  type ProcessingStatus,
  type PublicationStatus,
} from "@/data";
import { formatDayHeading, formatShortDate } from "@/lib/format";
import { formatMediaTypeLabel, formatPublicationLabel } from "@/lib/observation-badge";
import { getTimeOfDayOption, type TimeOfDayOption } from "./time-of-day";

/**
 * Shared archive filter vocabulary: parsing, validation, application and
 * URL building. Used by both the archive page and the media detail page
 * so a detail page can be reached with the same filter context (for
 * previous/next navigation and a correct "back to archive" link)
 * without duplicating the parsing/filtering logic twice.
 */

export const MEDIA_TYPES: MediaType[] = ["image", "composite", "timelapse"];
export const PROCESSING_STATUSES: ProcessingStatus[] = ["processed", "processing", "failed"];
export const PUBLICATION_STATUSES: PublicationStatus[] = [
  "public",
  "embargoed",
  "project-only",
  "restricted",
];

const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

export type SearchParams = Record<string, string | string[] | undefined>;

export function firstParam(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function isValidDate(value: string | undefined): value is string {
  return value !== undefined && DATE_PATTERN.test(value);
}

export type ArchiveFilters = {
  camera?: Camera;
  mediaType?: MediaType;
  date?: string;
  from?: string;
  to?: string;
  timeOfDay?: TimeOfDayOption;
  processingStatus?: ProcessingStatus;
  publicationStatus?: PublicationStatus;
};

/** Parses and validates filter query params. Invalid or foreign values are dropped, not rejected. */
export function parseArchiveFilters(search: SearchParams, cameras: Camera[]): ArchiveFilters {
  const cameraParam = firstParam(search.camera);
  const camera = cameraParam ? cameras.find((candidate) => candidate.id === cameraParam) : undefined;

  const mediaTypeParam = firstParam(search.mediaType);
  const mediaType = MEDIA_TYPES.find((type) => type === mediaTypeParam);

  const dateParam = firstParam(search.date);
  const date = isValidDate(dateParam) ? dateParam : undefined;

  const fromParam = firstParam(search.from);
  const toParam = firstParam(search.to);
  const from = isValidDate(fromParam) ? fromParam : undefined;
  const to = isValidDate(toParam) ? toParam : undefined;

  const timeOfDay = getTimeOfDayOption(firstParam(search.timeOfDay));

  const processingParam = firstParam(search.processingStatus);
  const processingStatus = PROCESSING_STATUSES.find((status) => status === processingParam);

  const publicationParam = firstParam(search.publicationStatus);
  const publicationStatus = PUBLICATION_STATUSES.find((status) => status === publicationParam);

  return { camera, mediaType, date, from, to, timeOfDay, processingStatus, publicationStatus };
}

export function applyArchiveFilters(media: MediaItem[], filters: ArchiveFilters): MediaItem[] {
  let result = filters.camera ? getMediaForCamera(filters.camera.id, media) : media;
  if (filters.mediaType) result = filterMediaByType(result, filters.mediaType);
  if (filters.date) {
    result = filterMediaByLocalDate(result, filters.date);
  } else if (filters.from || filters.to) {
    // Timezone-aware: compares each item's own local calendar date, not a
    // fixed UTC instant window, so it stays correct regardless of the
    // station's UTC offset. See data/queries.ts for details.
    result = filterMediaByLocalDateRange(result, filters.from, filters.to);
  }
  if (filters.timeOfDay) {
    result = filterMediaByTimeOfDay(result, filters.timeOfDay.startMinutes, filters.timeOfDay.endMinutes);
  }
  if (filters.processingStatus) result = filterMediaByProcessingStatus(result, filters.processingStatus);
  if (filters.publicationStatus) result = filterMediaByPublicationStatus(result, filters.publicationStatus);
  return result;
}

export function hasActiveFilters(filters: ArchiveFilters): boolean {
  return Boolean(
    filters.camera ||
      filters.mediaType ||
      filters.date ||
      filters.from ||
      filters.to ||
      filters.timeOfDay ||
      filters.processingStatus ||
      filters.publicationStatus,
  );
}

/** Counts active filters as logical groups (a date + a range together still count once), for a compact mobile summary. */
export function countActiveFilters(filters: ArchiveFilters): number {
  let count = 0;
  if (filters.camera) count += 1;
  if (filters.mediaType) count += 1;
  if (filters.date || filters.from || filters.to) count += 1;
  if (filters.timeOfDay) count += 1;
  if (filters.processingStatus) count += 1;
  if (filters.publicationStatus) count += 1;
  return count;
}

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
  const parts: string[] = [filters.camera ? filters.camera.name : "all cameras"];
  if (filters.mediaType) parts.push(formatMediaTypeLabel(filters.mediaType).toLowerCase());
  if (filters.date) {
    parts.push(formatDayHeading(filters.date));
  } else if (filters.from || filters.to) {
    parts.push(
      `${filters.from ? formatShortDate(filters.from) : "start"} to ${filters.to ? formatShortDate(filters.to) : "now"}`,
    );
  }
  if (filters.timeOfDay) parts.push(filters.timeOfDay.label);
  if (filters.processingStatus) parts.push(`processing: ${filters.processingStatus}`);
  if (filters.publicationStatus) {
    parts.push(`publication: ${formatPublicationLabel(filters.publicationStatus).toLowerCase()}`);
  }
  return parts;
}

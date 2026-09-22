import {
  filterMediaByLocalDate,
  filterMediaByLocalDateRange,
  filterMediaByProcessingStatus,
  filterMediaByPublicationStatus,
  filterMediaByTimeOfDay,
  filterMediaByType,
  getCamerasForStation,
  getMediaForCamera,
  type Camera,
  type MediaItem,
  type MediaType,
  type ProcessingStatus,
  type PublicationStatus,
  type StateOrTerritory,
  type Station,
} from "@/data";
import { formatDayHeading, formatShortDate } from "@/lib/format";
import { formatMediaTypeLabel, formatPublicationLabel } from "@/lib/observation-badge";
import { getTimeOfDayOption, type TimeOfDayOption } from "./time-of-day";

/**
 * The media filter vocabulary shared by every view that filters
 * observations — the station archive, the cross-station observations
 * page, and (indirectly, via those two) the media detail page. Kept in
 * one place so the same query-param name always means the same thing
 * and the parsing/application logic can't drift between routes.
 *
 * Route-specific concerns — station/state/region scoping, pagination,
 * and how filter state is turned into a URL or a summary sentence for a
 * particular page — stay in that route's own `filters.ts`.
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

/** Shape-only validation (matches "YYYY-MM-DD"); does not check calendar validity. Safe as a filter bound either way, since range filtering is a plain string comparison — see filterMediaByLocalDateRange. */
export function isValidDateKey(value: string | undefined): value is string {
  return value !== undefined && DATE_PATTERN.test(value);
}

export type MediaFilterFields = {
  camera?: Camera;
  mediaType?: MediaType;
  date?: string;
  from?: string;
  to?: string;
  timeOfDay?: TimeOfDayOption;
  processingStatus?: ProcessingStatus;
  publicationStatus?: PublicationStatus;
};

/** Parses and validates the shared media filter params against the given camera scope. Invalid or out-of-scope values are dropped, not rejected. */
export function parseMediaFilterFields(search: SearchParams, cameras: Camera[]): MediaFilterFields {
  const cameraParam = firstParam(search.camera);
  const camera = cameraParam ? cameras.find((candidate) => candidate.id === cameraParam) : undefined;

  const mediaTypeParam = firstParam(search.mediaType);
  const mediaType = MEDIA_TYPES.find((type) => type === mediaTypeParam);

  const dateParam = firstParam(search.date);
  const date = isValidDateKey(dateParam) ? dateParam : undefined;

  const fromParam = firstParam(search.from);
  const toParam = firstParam(search.to);
  const from = isValidDateKey(fromParam) ? fromParam : undefined;
  const to = isValidDateKey(toParam) ? toParam : undefined;

  const timeOfDay = getTimeOfDayOption(firstParam(search.timeOfDay));

  const processingParam = firstParam(search.processingStatus);
  const processingStatus = PROCESSING_STATUSES.find((status) => status === processingParam);

  const publicationParam = firstParam(search.publicationStatus);
  const publicationStatus = PUBLICATION_STATUSES.find((status) => status === publicationParam);

  return { camera, mediaType, date, from, to, timeOfDay, processingStatus, publicationStatus };
}

export function applyMediaFilterFields(media: MediaItem[], fields: MediaFilterFields): MediaItem[] {
  let result = fields.camera ? getMediaForCamera(fields.camera.id, media) : media;
  if (fields.mediaType) result = filterMediaByType(result, fields.mediaType);
  if (fields.date) {
    result = filterMediaByLocalDate(result, fields.date);
  } else if (fields.from || fields.to) {
    // Timezone-aware: compares each item's own local calendar date, not a
    // fixed UTC instant window. See data/queries.ts for details.
    result = filterMediaByLocalDateRange(result, fields.from, fields.to);
  }
  if (fields.timeOfDay) {
    result = filterMediaByTimeOfDay(result, fields.timeOfDay.startMinutes, fields.timeOfDay.endMinutes);
  }
  if (fields.processingStatus) result = filterMediaByProcessingStatus(result, fields.processingStatus);
  if (fields.publicationStatus) result = filterMediaByPublicationStatus(result, fields.publicationStatus);
  return result;
}

export function hasMediaFilterFields(fields: MediaFilterFields): boolean {
  return Boolean(
    fields.camera ||
      fields.mediaType ||
      fields.date ||
      fields.from ||
      fields.to ||
      fields.timeOfDay ||
      fields.processingStatus ||
      fields.publicationStatus,
  );
}

/** Counts active fields as logical groups (a date + a range together still count once). */
export function countMediaFilterFields(fields: MediaFilterFields): number {
  let count = 0;
  if (fields.camera) count += 1;
  if (fields.mediaType) count += 1;
  if (fields.date || fields.from || fields.to) count += 1;
  if (fields.timeOfDay) count += 1;
  if (fields.processingStatus) count += 1;
  if (fields.publicationStatus) count += 1;
  return count;
}

/** The shared tail of a filter summary sentence (media type, date/range, time of day, statuses). Callers prepend their own primary scope (a camera, a station, a state) first. */
export function summariseMediaFilterFields(fields: MediaFilterFields): string[] {
  const parts: string[] = [];
  if (fields.mediaType) parts.push(formatMediaTypeLabel(fields.mediaType).toLowerCase());
  if (fields.date) {
    parts.push(formatDayHeading(fields.date));
  } else if (fields.from || fields.to) {
    parts.push(
      `${fields.from ? formatShortDate(fields.from) : "start"} to ${fields.to ? formatShortDate(fields.to) : "now"}`,
    );
  }
  if (fields.timeOfDay) parts.push(fields.timeOfDay.label);
  if (fields.processingStatus) parts.push(`processing: ${fields.processingStatus}`);
  if (fields.publicationStatus) {
    parts.push(`publication: ${formatPublicationLabel(fields.publicationStatus).toLowerCase()}`);
  }
  return parts;
}

/**
 * The network-wide filter vocabulary used by the cross-station
 * observations page (and, in principle, any future view that filters
 * across stations rather than within one). Extends the shared media
 * fields with station/state/region scoping and pagination.
 */
export type ObservationFilters = MediaFilterFields & {
  station?: Station;
  state?: StateOrTerritory;
  region?: string;
  page: number;
};

/**
 * Parses every network-wide filter param, including page. A camera
 * filter is only valid within the cameras of the selected station, when
 * one is selected — a camera ID from another station is dropped rather
 * than silently displaying the wrong station's camera.
 */
export function parseObservationFilters(
  search: SearchParams,
  stations: Station[],
  allCameras: Camera[],
): ObservationFilters {
  const stationParam = firstParam(search.station);
  const station = stationParam ? stations.find((candidate) => candidate.id === stationParam) : undefined;

  const availableStates = new Set(stations.map((candidate) => candidate.state));
  const stateParam = firstParam(search.state) as StateOrTerritory | undefined;
  const state = stateParam && availableStates.has(stateParam) ? stateParam : undefined;

  const availableRegions = new Set(stations.map((candidate) => candidate.region));
  const regionParam = firstParam(search.region);
  const region = regionParam && availableRegions.has(regionParam) ? regionParam : undefined;

  const cameraScope = station ? getCamerasForStation(station.id, allCameras) : allCameras;
  const mediaFields = parseMediaFilterFields(search, cameraScope);

  const pageParam = firstParam(search.page);
  const parsedPage = pageParam ? Number.parseInt(pageParam, 10) : 1;
  const page = Number.isFinite(parsedPage) && parsedPage > 0 ? parsedPage : 1;

  return { station, state, region, ...mediaFields, page };
}

/**
 * Applies every filter additively (as an AND), including station/state/
 * region, which have no equivalent on the single-station archive page.
 * A contradictory combination (e.g. a station paired with a state it
 * isn't in) safely yields zero results rather than an error.
 */
export function applyObservationFilters(
  media: MediaItem[],
  filters: ObservationFilters,
  stations: Station[],
): MediaItem[] {
  let result = media;

  if (filters.station) {
    const stationId = filters.station.id;
    result = result.filter((item) => item.stationId === stationId);
  }
  if (filters.state) {
    const stateStationIds = new Set(
      stations.filter((candidate) => candidate.state === filters.state).map((candidate) => candidate.id),
    );
    result = result.filter((item) => stateStationIds.has(item.stationId));
  }
  if (filters.region) {
    const regionStationIds = new Set(
      stations.filter((candidate) => candidate.region === filters.region).map((candidate) => candidate.id),
    );
    result = result.filter((item) => regionStationIds.has(item.stationId));
  }

  return applyMediaFilterFields(result, filters);
}

export function hasActiveObservationFilters(filters: ObservationFilters): boolean {
  return Boolean(filters.station || filters.state || filters.region) || hasMediaFilterFields(filters);
}

export function countActiveObservationFilters(filters: ObservationFilters): number {
  let count = 0;
  if (filters.station) count += 1;
  if (filters.state) count += 1;
  if (filters.region) count += 1;
  return count + countMediaFilterFields(filters);
}

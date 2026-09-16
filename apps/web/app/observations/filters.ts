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
// Reuse the archive's filter vocabulary rather than redefining it, so the
// two pages always agree on valid values (e.g. adding a media type only
// requires updating one list).
import {
  firstParam,
  MEDIA_TYPES,
  PROCESSING_STATUSES,
  PUBLICATION_STATUSES,
  type SearchParams,
} from "../stations/[stationId]/archive/filters";
import {
  getTimeOfDayOption,
  TIME_OF_DAY_OPTIONS,
  type TimeOfDayOption,
} from "../stations/[stationId]/archive/time-of-day";

export { firstParam, MEDIA_TYPES, PROCESSING_STATUSES, PUBLICATION_STATUSES, TIME_OF_DAY_OPTIONS };
export type { SearchParams };

const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

function isValidDate(value: string | undefined): value is string {
  return value !== undefined && DATE_PATTERN.test(value);
}

export const PAGE_SIZE = 24;

export type ObservationFilters = {
  station?: Station;
  state?: StateOrTerritory;
  region?: string;
  camera?: Camera;
  mediaType?: MediaType;
  date?: string;
  from?: string;
  to?: string;
  timeOfDay?: TimeOfDayOption;
  processingStatus?: ProcessingStatus;
  publicationStatus?: PublicationStatus;
  page: number;
};

/**
 * Parses and validates every network-wide filter param, including page.
 * Invalid, missing or foreign values are dropped rather than rejected —
 * a camera that doesn't belong to the selected station is simply ignored,
 * matching the archive page's convention.
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

  // A camera filter is only valid within the cameras of the selected
  // station, when one is selected — a camera ID from another station is
  // dropped rather than silently displaying the wrong station's camera.
  const cameraScope = station ? getCamerasForStation(station.id, allCameras) : allCameras;
  const cameraParam = firstParam(search.camera);
  const camera = cameraParam ? cameraScope.find((candidate) => candidate.id === cameraParam) : undefined;

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

  const pageParam = firstParam(search.page);
  const parsedPage = pageParam ? Number.parseInt(pageParam, 10) : 1;
  const page = Number.isFinite(parsedPage) && parsedPage > 0 ? parsedPage : 1;

  return {
    station,
    state,
    region,
    camera,
    mediaType,
    date,
    from,
    to,
    timeOfDay,
    processingStatus,
    publicationStatus,
    page,
  };
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
  if (filters.camera) {
    result = getMediaForCamera(filters.camera.id, result);
  }
  if (filters.mediaType) result = filterMediaByType(result, filters.mediaType);
  if (filters.date) {
    result = filterMediaByLocalDate(result, filters.date);
  } else if (filters.from || filters.to) {
    result = filterMediaByLocalDateRange(result, filters.from, filters.to);
  }
  if (filters.timeOfDay) {
    result = filterMediaByTimeOfDay(result, filters.timeOfDay.startMinutes, filters.timeOfDay.endMinutes);
  }
  if (filters.processingStatus) result = filterMediaByProcessingStatus(result, filters.processingStatus);
  if (filters.publicationStatus) result = filterMediaByPublicationStatus(result, filters.publicationStatus);

  return result;
}

export function hasActiveFilters(filters: ObservationFilters): boolean {
  return Boolean(
    filters.station ||
      filters.state ||
      filters.region ||
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

export function countActiveFilters(filters: ObservationFilters): number {
  let count = 0;
  if (filters.station) count += 1;
  if (filters.state) count += 1;
  if (filters.region) count += 1;
  if (filters.camera) count += 1;
  if (filters.mediaType) count += 1;
  if (filters.date || filters.from || filters.to) count += 1;
  if (filters.timeOfDay) count += 1;
  if (filters.processingStatus) count += 1;
  if (filters.publicationStatus) count += 1;
  return count;
}

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
  parts.push(filters.station ? filters.station.name : filters.state ? `${filters.state} stations` : filters.region ? filters.region : "all stations");
  if (filters.camera) parts.push(filters.camera.name);
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

import { getLocalDateKey, getLocalMinutesOfDay } from "@/lib/format";
import type { Camera, MediaItem, MediaType, ProcessingStatus, PublicationStatus, Station } from "./types/media";
import { CAMERAS, MEDIA, STATIONS } from "./sample";

/**
 * Typed, synchronous, dependency-free data-access helpers over the
 * sample fixtures. Every function accepts the data set it should read
 * as an optional final argument (defaulting to the sample data), so
 * these are easy to unit test with small fixture arrays and easy to
 * swap for a real API client later without changing call sites' shape.
 */

export function getAllStations(stations: Station[] = STATIONS): Station[] {
  return stations;
}

export function getAllMedia(media: MediaItem[] = MEDIA): MediaItem[] {
  return media;
}

export function getStationById(id: string, stations: Station[] = STATIONS): Station | undefined {
  return stations.find((station) => station.id === id);
}

export function getAllCameras(cameras: Camera[] = CAMERAS): Camera[] {
  return cameras;
}

export function getCamerasForStation(stationId: string, cameras: Camera[] = CAMERAS): Camera[] {
  return cameras.filter((camera) => camera.stationId === stationId);
}

export function getCameraById(id: string, cameras: Camera[] = CAMERAS): Camera | undefined {
  return cameras.find((camera) => camera.id === id);
}

export function getMediaForStation(stationId: string, media: MediaItem[] = MEDIA): MediaItem[] {
  return media.filter((item) => item.stationId === stationId);
}

export function getMediaForCamera(cameraId: string, media: MediaItem[] = MEDIA): MediaItem[] {
  return media.filter((item) => item.cameraId === cameraId);
}

export function getMediaById(mediaId: string, media: MediaItem[] = MEDIA): MediaItem | undefined {
  return media.find((item) => item.id === mediaId);
}

/**
 * Given a chronologically sorted list, finds the items immediately
 * before and after the one matching mediaId. Returns an empty object
 * (no crash) if mediaId isn't present in the list.
 */
export function getAdjacentMedia(
  sortedMedia: MediaItem[],
  mediaId: string,
): { previous?: MediaItem; next?: MediaItem } {
  const index = sortedMedia.findIndex((item) => item.id === mediaId);
  if (index === -1) return {};
  return {
    previous: index > 0 ? sortedMedia[index - 1] : undefined,
    next: index < sortedMedia.length - 1 ? sortedMedia[index + 1] : undefined,
  };
}

/**
 * Filters media whose capturedAtUtc falls within [start, end], inclusive.
 * Accepts ISO date/time strings or Date objects.
 */
export function filterMediaByDateRange(
  media: MediaItem[],
  start: string | Date,
  end: string | Date,
): MediaItem[] {
  const startMs = new Date(start).getTime();
  const endMs = new Date(end).getTime();
  return media.filter((item) => {
    const capturedMs = new Date(item.capturedAtUtc).getTime();
    return capturedMs >= startMs && capturedMs <= endMs;
  });
}

export function filterMediaByType(media: MediaItem[], mediaType: MediaType): MediaItem[] {
  return media.filter((item) => item.mediaType === mediaType);
}

/** Generic over anything with a capturedAtUtc field, so non-station observation types (e.g. CoastSnap) can reuse this instead of duplicating the same sort. */
export function sortMediaByCaptureTime<T extends { capturedAtUtc: string }>(
  media: T[],
  direction: "asc" | "desc" = "asc",
): T[] {
  const sorted = [...media].sort(
    (a, b) => new Date(a.capturedAtUtc).getTime() - new Date(b.capturedAtUtc).getTime(),
  );
  return direction === "asc" ? sorted : sorted.reverse();
}

/** Resolves a media item's relatedMediaIds to the actual items, skipping any that are missing. */
export function getRelatedMedia(mediaId: string, media: MediaItem[] = MEDIA): MediaItem[] {
  const item = media.find((candidate) => candidate.id === mediaId);
  if (!item) return [];
  const byId = new Map(media.map((candidate) => [candidate.id, candidate]));
  return item.relatedMediaIds
    .map((relatedId) => byId.get(relatedId))
    .filter((related): related is MediaItem => related !== undefined);
}

export function filterMediaByProcessingStatus(
  media: MediaItem[],
  status: ProcessingStatus,
): MediaItem[] {
  return media.filter((item) => item.processingStatus === status);
}

export function filterMediaByPublicationStatus(
  media: MediaItem[],
  status: PublicationStatus,
): MediaItem[] {
  return media.filter((item) => item.publicationStatus === status);
}

/**
 * Filters to items whose local calendar date (in each item's own
 * displayTimeZone) matches the given "YYYY-MM-DD" key. Timezone-aware,
 * so it correctly handles a local day that spans two UTC calendar dates.
 */
export function filterMediaByLocalDate(media: MediaItem[], localDateKey: string): MediaItem[] {
  return media.filter(
    (item) => getLocalDateKey(item.capturedAtUtc, item.displayTimeZone) === localDateKey,
  );
}

/**
 * Filters to items whose local calendar date (each item's own
 * displayTimeZone) falls within [fromDateKey, toDateKey], inclusive.
 * Either bound may be omitted for an open-ended range. Because
 * "YYYY-MM-DD" keys sort lexicographically the same as chronologically,
 * this is a plain string comparison per item — no UTC boundary math,
 * so it is correct regardless of how far an item's local time zone is
 * offset from UTC, and correctly handles local dates that span two UTC
 * calendar dates (e.g. an early-morning Sydney or Perth capture whose
 * capturedAtUtc falls on the previous UTC day). A fromDateKey after
 * toDateKey naturally yields no matches rather than needing special
 * handling for an invalid range.
 */
export function filterMediaByLocalDateRange(
  media: MediaItem[],
  fromDateKey: string | undefined,
  toDateKey: string | undefined,
): MediaItem[] {
  if (!fromDateKey && !toDateKey) return media;
  return media.filter((item) => {
    const key = getLocalDateKey(item.capturedAtUtc, item.displayTimeZone);
    if (fromDateKey && key < fromDateKey) return false;
    if (toDateKey && key > toDateKey) return false;
    return true;
  });
}

/**
 * Filters to items whose local time-of-day (minutes since local
 * midnight) falls within [startMinutes, endMinutes]. When startMinutes
 * is greater than endMinutes, the range is treated as wrapping past
 * local midnight (e.g. a "night" window of 21:00-04:59).
 */
export function filterMediaByTimeOfDay(
  media: MediaItem[],
  startMinutes: number,
  endMinutes: number,
): MediaItem[] {
  return media.filter((item) => {
    const minutes = getLocalMinutesOfDay(item.capturedAtUtc, item.displayTimeZone);
    if (startMinutes <= endMinutes) {
      return minutes >= startMinutes && minutes <= endMinutes;
    }
    return minutes >= startMinutes || minutes <= endMinutes;
  });
}

/** Groups media by local calendar date (each item's own displayTimeZone), preserving input order within each group. */
export function groupMediaByLocalDate(media: MediaItem[]): Map<string, MediaItem[]> {
  const groups = new Map<string, MediaItem[]>();
  for (const item of media) {
    const key = getLocalDateKey(item.capturedAtUtc, item.displayTimeZone);
    const existing = groups.get(key);
    if (existing) {
      existing.push(item);
    } else {
      groups.set(key, [item]);
    }
  }
  return groups;
}

/** The IANA time zone a station's observations are displayed in, derived from its media records. */
export function getStationTimeZone(stationId: string, media: MediaItem[] = MEDIA): string | undefined {
  return media.find((item) => item.stationId === stationId)?.displayTimeZone;
}

/**
 * The single most recent presentable (processed and public) observation
 * from each station, most recent overall first. Stations with no
 * presentable media are skipped rather than shown with a broken or
 * restricted item. Intended for compact cross-station summaries such as
 * a homepage "latest observations" list.
 */
export function getLatestObservationPerStation(
  stations: Station[] = STATIONS,
  media: MediaItem[] = MEDIA,
): MediaItem[] {
  const latestPerStation: MediaItem[] = [];
  for (const station of stations) {
    const presentable = media.filter(
      (item) =>
        item.stationId === station.id &&
        item.processingStatus === "processed" &&
        item.publicationStatus === "public",
    );
    if (presentable.length === 0) continue;
    latestPerStation.push(sortMediaByCaptureTime(presentable, "desc")[0]);
  }
  return sortMediaByCaptureTime(latestPerStation, "desc");
}

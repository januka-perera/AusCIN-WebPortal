import type { Camera, MediaItem, MediaType, Station } from "./types/media";
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

export function getStationById(id: string, stations: Station[] = STATIONS): Station | undefined {
  return stations.find((station) => station.id === id);
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

export function sortMediaByCaptureTime(
  media: MediaItem[],
  direction: "asc" | "desc" = "asc",
): MediaItem[] {
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

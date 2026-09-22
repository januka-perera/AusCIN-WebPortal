/**
 * Shared data model for the AusCIN sample data layer.
 *
 * This is the single source of truth for station, camera and media
 * shapes so the sample fixtures, the query helpers and (eventually) a
 * real API client all agree on one schema. Keep this frontend-only
 * layer free of any backend or transport concerns.
 */

export type StateOrTerritory = "NSW" | "VIC" | "QLD" | "WA" | "SA" | "TAS" | "NT" | "ACT";

export type ViewDirection = "N" | "NE" | "E" | "SE" | "S" | "SW" | "W" | "NW";

/** Shared by stations and cameras: whether the hardware is currently operating. */
export type OperatingStatus = "active" | "offline" | "maintenance";

export type CameraType = "fixed" | "ptz" | "lidar";

export type MediaType = "image" | "composite" | "timelapse";

/** Where a media item is up to in the ingestion/processing pipeline. */
export type ProcessingStatus = "processed" | "processing" | "failed";

/** Who is allowed to see a media item, independent of processing status. */
export type PublicationStatus = "public" | "embargoed" | "project-only" | "restricted";

export interface Station {
  /** Stable, human-legible station identifier, e.g. "STN-SEAGLASS". */
  id: string;
  name: string;
  state: StateOrTerritory;
  latitude: number;
  longitude: number;
  /** Region or local government area, e.g. "Illawarra, NSW". */
  region: string;
  description: string;
  viewDirection: ViewDirection;
  elevationMetres: number;
  operationalStatus: OperatingStatus;
  /** ISO date the station went live, e.g. "2018-03-01". */
  operationalSince: string;
  /** Path to a representative image, served from public/sample-media. */
  representativeImageUrl: string;
}

export interface Camera {
  /** Stable identifier, e.g. "STN-SEAGLASS-CAM1". */
  id: string;
  stationId: string;
  name: string;
  type: CameraType;
  resolution: { width: number; height: number };
  viewDirection: ViewDirection;
  captureIntervalMinutes: number;
  status: OperatingStatus;
}

export interface MediaItem {
  /** Stable, opaque-style identifier. Never a filesystem path. */
  id: string;
  stationId: string;
  cameraId: string;
  mediaType: MediaType;
  /** ISO 8601 timestamp in UTC, e.g. "2025-02-09T19:00:00.000Z". */
  capturedAtUtc: string;
  /** IANA time zone used to display capturedAtUtc to visitors. */
  displayTimeZone: string;
  /** Present only for mediaType "timelapse". */
  durationSeconds?: number;
  width: number;
  height: number;
  fileSizeBytes: number;
  processingStatus: ProcessingStatus;
  publicationStatus: PublicationStatus;
  /** Null when no thumbnail is available yet (processing/failed). */
  thumbnailUrl: string | null;
  /** Null when a preview could not be generated. */
  previewUrl: string | null;
  /** Null at this prototype stage: no original files are served yet. */
  originalUrl: string | null;
  relatedMediaIds: string[];
  caption: string;
  altText: string;
}

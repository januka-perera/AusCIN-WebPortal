import {
  applyMediaFilterFields,
  applyObservationFilters,
  type MediaFilterFields,
  type ObservationFilters,
} from "@/lib/media-filters";
import { paginate } from "@/lib/pagination";
import {
  getAllCameras,
  getAllMedia,
  getAllStations,
  getCameraById,
  getCamerasForStation,
  getLatestObservationPerStation,
  getMediaById,
  getMediaForStation,
  getRelatedMedia,
  getStationById,
} from "./queries";
import type { Camera, MediaItem, Station } from "./types/media";
import type { PaginatedResult, PaginationParams } from "./types/api";

/**
 * The frontend's data-access boundary: every page reads station, camera
 * and observation data through this interface rather than importing
 * `data/queries` or `data/sample` directly. The current implementation
 * (SampleRepository, below) wraps the synchronous sample dataset, but
 * every method is async — matching what a real fetch-based client would
 * look like — so a future FastAPI-backed implementation can be dropped
 * in behind the same interface without changing a single page component.
 *
 * No network requests are made here yet. Filtering, pagination and
 * lookups are still deterministic, synchronous sample-data operations
 * under the hood; only the call shape is already API-ready.
 */
export interface AusCinRepository {
  listStations(): Promise<Station[]>;
  getStation(stationId: string): Promise<Station | undefined>;
  listCameras(): Promise<Camera[]>;
  listCamerasForStation(stationId: string): Promise<Camera[]>;
  getCamera(cameraId: string): Promise<Camera | undefined>;
  /** One station's observations matching the given filters. Pass {} for the station's full, unfiltered record. */
  listStationObservations(stationId: string, filters: MediaFilterFields): Promise<MediaItem[]>;
  /** Network-wide observations matching the given filters, one page at a time, newest first. */
  listObservations(
    filters: ObservationFilters,
    pagination: PaginationParams,
  ): Promise<PaginatedResult<MediaItem>>;
  /** The single most recent presentable (processed and public) observation from each station that has one. */
  listLatestObservationPerStation(): Promise<MediaItem[]>;
  getMediaItem(stationId: string, mediaId: string): Promise<MediaItem | undefined>;
  /** Other media explicitly linked to this one (e.g. a time-lapse's source stills), scoped to the same station. */
  getRelatedMediaItems(stationId: string, mediaId: string): Promise<MediaItem[]>;
}

class SampleRepository implements AusCinRepository {
  async listStations(): Promise<Station[]> {
    return getAllStations();
  }

  async getStation(stationId: string): Promise<Station | undefined> {
    return getStationById(stationId);
  }

  async listCameras(): Promise<Camera[]> {
    return getAllCameras();
  }

  async listCamerasForStation(stationId: string): Promise<Camera[]> {
    return getCamerasForStation(stationId);
  }

  async getCamera(cameraId: string): Promise<Camera | undefined> {
    return getCameraById(cameraId);
  }

  async listStationObservations(stationId: string, filters: MediaFilterFields): Promise<MediaItem[]> {
    return applyMediaFilterFields(getMediaForStation(stationId), filters);
  }

  async listObservations(
    filters: ObservationFilters,
    pagination: PaginationParams,
  ): Promise<PaginatedResult<MediaItem>> {
    const filtered = applyObservationFilters(getAllMedia(), filters, getAllStations()).sort(
      (a, b) => new Date(b.capturedAtUtc).getTime() - new Date(a.capturedAtUtc).getTime(),
    );
    return paginate(filtered, pagination.page, pagination.pageSize);
  }

  async listLatestObservationPerStation(): Promise<MediaItem[]> {
    return getLatestObservationPerStation();
  }

  async getMediaItem(stationId: string, mediaId: string): Promise<MediaItem | undefined> {
    return getMediaById(mediaId, getMediaForStation(stationId));
  }

  async getRelatedMediaItems(stationId: string, mediaId: string): Promise<MediaItem[]> {
    return getRelatedMedia(mediaId, getMediaForStation(stationId));
  }
}

/**
 * The single repository instance every page should import. Swapping the
 * sample implementation for a real API client is intended to happen by
 * changing this one assignment (and adding the new implementation
 * class), not by touching call sites.
 */
export const repository: AusCinRepository = new SampleRepository();

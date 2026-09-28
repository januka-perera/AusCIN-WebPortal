import { paginate } from "@/lib/pagination";
import {
  getAllCoastSnapSites,
  getCoastSnapObservationById,
  getCoastSnapObservationForSite,
  getCoastSnapSiteById,
  getFilteredObservationsForCoastSnapSite,
  getLatestObservationPerCoastSnapSite,
  getObservationDateRangeForSite,
  type CoastSnapObservationDateRange,
  type CoastSnapObservationFilters,
} from "./coastsnap-queries";
import { HttpCoastSnapRepository } from "./coastsnap-http-repository";
import { sortMediaByCaptureTime } from "./queries";
import type { CoastSnapObservation, CoastSnapSite } from "./types/coastsnap";
import type { PaginatedResult, PaginationParams } from "./types/api";

/**
 * The CoastSnap frontend area's data-access boundary — the same pattern
 * as `AusCinRepository` in `data/repository.ts`, kept as a separate
 * interface because CoastSnap's domain shape (sites and observations)
 * differs from the station/camera/media model. Every method is async,
 * matching what a real fetch-based client (eventually reading ingested
 * Spotteron data) would look like, so pages built against this
 * interface won't need to change when the sample implementation is
 * replaced. The sample implementation makes no network requests. The
 * HTTP implementation lives in `coastsnap-http-repository.ts`, and
 * `coastSnapRepository` below selects between them.
 */
export interface CoastSnapRepository {
  listSites(): Promise<CoastSnapSite[]>;
  getSite(siteId: string): Promise<CoastSnapSite | undefined>;
  /** One site's observations matching the given filters. Pass {} (or omit) for the site's full, unfiltered record. */
  listObservationsForSite(
    siteId: string,
    filters?: CoastSnapObservationFilters,
  ): Promise<CoastSnapObservation[]>;
  /** A site's filtered observations, one page at a time, newest first. */
  listObservationsForSitePaginated(
    siteId: string,
    filters: CoastSnapObservationFilters,
    pagination: PaginationParams,
  ): Promise<PaginatedResult<CoastSnapObservation>>;
  getObservation(observationId: string): Promise<CoastSnapObservation | undefined>;
  /** Looks up an observation scoped to one site — never resolves an observation that belongs to a different site. */
  getObservationForSite(siteId: string, observationId: string): Promise<CoastSnapObservation | undefined>;
  /** The single most recent presentable observation from each site that has one. */
  listLatestObservationPerSite(): Promise<CoastSnapObservation[]>;
  /** The earliest and latest observation at a site, or undefined if it has none. */
  getObservationDateRange(siteId: string): Promise<CoastSnapObservationDateRange | undefined>;
}

class SampleCoastSnapRepository implements CoastSnapRepository {
  async listSites(): Promise<CoastSnapSite[]> {
    return getAllCoastSnapSites();
  }

  async getSite(siteId: string): Promise<CoastSnapSite | undefined> {
    return getCoastSnapSiteById(siteId);
  }

  async listObservationsForSite(
    siteId: string,
    filters: CoastSnapObservationFilters = {},
  ): Promise<CoastSnapObservation[]> {
    return getFilteredObservationsForCoastSnapSite(siteId, filters);
  }

  async listObservationsForSitePaginated(
    siteId: string,
    filters: CoastSnapObservationFilters,
    pagination: PaginationParams,
  ): Promise<PaginatedResult<CoastSnapObservation>> {
    const filtered = sortMediaByCaptureTime(
      getFilteredObservationsForCoastSnapSite(siteId, filters),
      "desc",
    );
    return paginate(filtered, pagination.page, pagination.pageSize);
  }

  async getObservation(observationId: string): Promise<CoastSnapObservation | undefined> {
    return getCoastSnapObservationById(observationId);
  }

  async getObservationForSite(
    siteId: string,
    observationId: string,
  ): Promise<CoastSnapObservation | undefined> {
    return getCoastSnapObservationForSite(siteId, observationId);
  }

  async listLatestObservationPerSite(): Promise<CoastSnapObservation[]> {
    return getLatestObservationPerCoastSnapSite();
  }

  async getObservationDateRange(siteId: string): Promise<CoastSnapObservationDateRange | undefined> {
    return getObservationDateRangeForSite(siteId);
  }
}

/** Where CoastSnap data comes from for the current server environment. */
export type CoastSnapDataSource = "sample" | "api";

type CoastSnapEnv = Record<string, string | undefined>;

function readApiBaseUrl(env: CoastSnapEnv): string | undefined {
  const value = env.COASTSNAP_API_BASE_URL?.trim();
  return value ? value : undefined;
}

/**
 * `"api"` when the server-side `COASTSNAP_API_BASE_URL` is set, otherwise
 * `"sample"`. Pages use this to choose between sample-data disclaimers and
 * wording for real records.
 */
export function getCoastSnapDataSource(env: CoastSnapEnv = process.env): CoastSnapDataSource {
  return readApiBaseUrl(env) ? "api" : "sample";
}

const sampleRepository = new SampleCoastSnapRepository();
let cachedHttp: { key: string; repository: HttpCoastSnapRepository } | undefined;

/**
 * Chooses the repository for the given environment:
 * - `COASTSNAP_API_BASE_URL` unset or blank → the synthetic sample repository.
 *   This is the default for local development and every unit test.
 * - `COASTSNAP_API_BASE_URL` set → the HTTP repository for the FastAPI catalogue,
 *   with media URLs pinned to `COASTSNAP_MEDIA_ORIGIN` (default: the API origin).
 *
 * An invalid URL throws a config `CoastSnapApiError`. It does not silently fall
 * back to sample data, which would pass fixtures off as a live catalogue.
 */
export function createCoastSnapRepository(env: CoastSnapEnv = process.env): CoastSnapRepository {
  const apiBaseUrl = readApiBaseUrl(env);
  if (!apiBaseUrl) return sampleRepository;
  const mediaOrigin = env.COASTSNAP_MEDIA_ORIGIN?.trim() || undefined;
  const key = `${apiBaseUrl}\u0000${mediaOrigin ?? ""}`;
  if (cachedHttp?.key !== key) {
    cachedHttp = { key, repository: new HttpCoastSnapRepository({ apiBaseUrl, mediaOrigin }) };
  }
  return cachedHttp.repository;
}

/**
 * The single CoastSnap repository instance pages should import.
 *
 * It picks its implementation on every call (see `createCoastSnapRepository`)
 * rather than once at module load. A route rendered at request time therefore
 * always honours the server's current environment, and pages don't need to
 * know which implementation is behind the interface.
 */
export const coastSnapRepository: CoastSnapRepository = {
  listSites: () => createCoastSnapRepository().listSites(),
  getSite: (siteId) => createCoastSnapRepository().getSite(siteId),
  listObservationsForSite: (siteId, filters) => createCoastSnapRepository().listObservationsForSite(siteId, filters),
  listObservationsForSitePaginated: (siteId, filters, pagination) =>
    createCoastSnapRepository().listObservationsForSitePaginated(siteId, filters, pagination),
  getObservation: (observationId) => createCoastSnapRepository().getObservation(observationId),
  getObservationForSite: (siteId, observationId) =>
    createCoastSnapRepository().getObservationForSite(siteId, observationId),
  listLatestObservationPerSite: () => createCoastSnapRepository().listLatestObservationPerSite(),
  getObservationDateRange: (siteId) => createCoastSnapRepository().getObservationDateRange(siteId),
};

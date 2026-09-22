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
 * replaced. No network requests are made here yet.
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

/** The single CoastSnap repository instance pages should import. */
export const coastSnapRepository: CoastSnapRepository = new SampleCoastSnapRepository();

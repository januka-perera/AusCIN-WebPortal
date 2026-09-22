import {
  getAllCoastSnapSites,
  getCoastSnapObservationById,
  getCoastSnapSiteById,
  getLatestObservationPerCoastSnapSite,
  getObservationsForCoastSnapSite,
} from "./coastsnap-queries";
import type { CoastSnapObservation, CoastSnapSite } from "./types/coastsnap";

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
  listObservationsForSite(siteId: string): Promise<CoastSnapObservation[]>;
  getObservation(observationId: string): Promise<CoastSnapObservation | undefined>;
  /** The single most recent presentable observation from each site that has one. */
  listLatestObservationPerSite(): Promise<CoastSnapObservation[]>;
}

class SampleCoastSnapRepository implements CoastSnapRepository {
  async listSites(): Promise<CoastSnapSite[]> {
    return getAllCoastSnapSites();
  }

  async getSite(siteId: string): Promise<CoastSnapSite | undefined> {
    return getCoastSnapSiteById(siteId);
  }

  async listObservationsForSite(siteId: string): Promise<CoastSnapObservation[]> {
    return getObservationsForCoastSnapSite(siteId);
  }

  async getObservation(observationId: string): Promise<CoastSnapObservation | undefined> {
    return getCoastSnapObservationById(observationId);
  }

  async listLatestObservationPerSite(): Promise<CoastSnapObservation[]> {
    return getLatestObservationPerCoastSnapSite();
  }
}

/** The single CoastSnap repository instance pages should import. */
export const coastSnapRepository: CoastSnapRepository = new SampleCoastSnapRepository();

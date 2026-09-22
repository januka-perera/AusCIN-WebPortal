/**
 * Data model for the CoastSnap frontend area.
 *
 * CoastSnap sites are community photo-monitoring points, not powered
 * camera stations — a member of the public lines up a phone photo
 * against a fixed alignment mark. That's a different shape to the
 * station/camera/media model in `./media.ts`, so CoastSnap gets its own
 * types rather than being force-fitted into the station model. Where a
 * concept is genuinely the same (media type, processing status,
 * publication status, state/territory, operating status), those types
 * are reused from `./media.ts` rather than redefined here.
 *
 * Nothing in this file should ever hold a filesystem path — media
 * fields are opaque URLs served from `public/sample-media`, exactly
 * like `MediaItem` in `./media.ts`.
 */

import type {
  MediaType,
  OperatingStatus,
  ProcessingStatus,
  PublicationStatus,
  StateOrTerritory,
} from "./media";

/**
 * Where a CoastSnap record originated. Every real CoastSnap observation
 * is expected to come from the Spotteron platform; this is a union
 * (rather than a boolean) so a future second source doesn't need a
 * breaking change.
 */
export type CoastSnapSourcePlatform = "spotteron";

/** How to credit the person who submitted an observation. Never a real person's private contact details — a display name/handle only. */
export type CoastSnapContributor = {
  /** Display name or handle to credit, e.g. "Priya K." or an anonymised contributor handle. */
  displayName: string;
  /** The credit line shown alongside the observation, e.g. "CoastSnap community photo". */
  attributionText: string;
};

export interface CoastSnapSite {
  /** Stable, human-legible site identifier, e.g. "CS-DRIFTWOOD". */
  id: string;
  name: string;
  /**
   * The Spotteron platform's own identifier for this site ("spot"),
   * once the site corresponds to a real Spotteron spot. Left undefined
   * for every site in this prototype — none of these sites have been
   * ingested from Spotteron yet, so there is no real ID to record.
   */
  spotteronSiteId?: string;
  state: StateOrTerritory;
  latitude: number;
  longitude: number;
  /** Region or local government area, e.g. "Central Coast, NSW". */
  region: string;
  description: string;
  /** Whether the physical alignment mark/cradle is currently in service. */
  status: OperatingStatus;
  /** ISO date the site was set up for public contributions, e.g. "2024-11-01". */
  establishedSince: string;
  /** Path to a representative image, served from public/sample-media. Never a filesystem path. */
  representativeImageUrl: string;
  /** True while a site exists only as a local development fixture, with no corresponding real Spotteron spot. */
  isSynthetic: boolean;
}

export interface CoastSnapObservation {
  /** Stable, opaque-style identifier for this observation (one public contribution). Never a filesystem path. */
  id: string;
  siteId: string;
  sourcePlatform: CoastSnapSourcePlatform;
  /** The Spotteron platform's own identifier for this observation, when sourcePlatform is "spotteron" and the record has really been ingested. Undefined for every observation in this prototype. */
  spotteronObservationId?: string;
  /**
   * Identifier for the associated media asset. Kept distinct from `id`
   * because an observation and its media are different concepts (an
   * observation could in principle carry more than one media asset in
   * future) — always derived from `id` in this prototype's 1:1 sample
   * data.
   */
  mediaId: string;
  /** The Spotteron platform's own identifier for the media asset itself (distinct from the observation ID it belongs to). Undefined until a real ingestion populates it. */
  spotteronMediaId?: string;
  /** The asset's URL on Spotteron's own hosting, once ingested. Undefined for every observation in this prototype — never a locally-guessed or fabricated URL. */
  sourceUrl?: string;
  mediaType: MediaType;
  /** ISO 8601 timestamp in UTC, e.g. "2026-08-01T02:15:00.000Z". */
  capturedAtUtc: string;
  /** IANA time zone used to display capturedAtUtc to visitors. */
  displayTimeZone: string;
  /** Pixel dimensions, where known. Contributed phone photos can arrive with inconsistent or unknown dimensions, unlike a fixed station camera's fixed resolution, so both are optional. */
  width?: number;
  height?: number;
  contributor: CoastSnapContributor;
  processingStatus: ProcessingStatus;
  publicationStatus: PublicationStatus;
  /** Null when no thumbnail is available yet (processing/failed). */
  thumbnailUrl: string | null;
  /** Null when a preview could not be generated. */
  previewUrl: string | null;
  /**
   * Whether an original file is available to download. Kept as its own
   * explicit flag (rather than only inferring availability from
   * `originalUrl` being non-null) because a future ingested record could
   * know availability before a real download URL is populated. In this
   * prototype, true only for a single clearly-labelled mock record used
   * to exercise the "download available" UI state — see
   * data/sample/coastsnap-observations.ts.
   */
  isOriginalAvailable: boolean;
  /** The original file's URL when isOriginalAvailable is true. Null otherwise. Never a filesystem or /g/data path. */
  originalUrl: string | null;
  /** SHA-256 checksum of the original file, once one exists to check. Undefined for every observation in this prototype. */
  checksumSha256?: string;
  caption: string;
  altText: string;
  /** True for every observation in this prototype: none of this data has come from a real Spotteron ingestion. */
  isSynthetic: boolean;
}

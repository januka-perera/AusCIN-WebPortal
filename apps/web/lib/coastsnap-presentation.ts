import type { CoastSnapDataSource, CoastSnapObservation } from "@/data";

/**
 * Wording for CoastSnap records that depends on where they came from. Sample
 * fixtures keep their "development record" disclaimers and prototype download
 * wording. API-backed records are only labelled synthetic when the catalogue
 * says so (`isSynthetic`), and they get real download wording.
 */

/** Fixed document title for the /coastsnap error boundary. It never includes an API host, path or error detail. */
export const COASTSNAP_ERROR_TITLE = "CoastSnap catalogue unavailable | AusCIN";

export const SAMPLE_RECORD_NOTICE = "Sample development record — not an operational AusCIN feed.";
export const SYNTHETIC_API_RECORD_NOTICE =
  "Synthetic test record served by the development catalogue — not an operational AusCIN feed.";

/** The disclaimer for a site or observation, or null when none applies (a real, API-backed record). */
export function getRecordNotice(source: CoastSnapDataSource, isSynthetic: boolean): string | null {
  if (source === "sample") return SAMPLE_RECORD_NOTICE;
  return isSynthetic ? SYNTHETIC_API_RECORD_NOTICE : null;
}

/**
 * Why an original can or can't be downloaded. Each state stays distinct so the
 * UI never collapses processing, failed, restricted and unavailable into one
 * message.
 */
export type CoastSnapDownloadState =
  | "available"
  | "sample-demo"
  | "processing"
  | "failed"
  | "restricted"
  | "unavailable";

type DownloadFields = Pick<
  CoastSnapObservation,
  | "isOriginalAvailable"
  | "originalUrl"
  | "processingStatus"
  | "publicationStatus"
  | "level0DownloadAvailable"
  | "level0DownloadUrl"
  | "level0ChecksumSha256"
  | "level1DownloadAvailable"
  | "level1DownloadUrl"
  | "level1ChecksumSha256"
>;

/**
 * API records offer downloads per product level (Level 0 and/or Level 1).
 * Sample records only ever offer the one labelled prototype demo, through the
 * deprecated single-original fields.
 */
export function getCoastSnapDownloadState(
  source: CoastSnapDataSource,
  observation: DownloadFields,
): CoastSnapDownloadState {
  if (source === "sample") {
    if (observation.isOriginalAvailable && observation.originalUrl) return "sample-demo";
  } else if (
    (observation.level0DownloadAvailable && observation.level0DownloadUrl) ||
    (observation.level1DownloadAvailable && observation.level1DownloadUrl)
  ) {
    return "available";
  }
  if (observation.processingStatus === "processing") return "processing";
  if (observation.processingStatus === "failed") return "failed";
  if (observation.publicationStatus !== "public") return "restricted";
  return "unavailable";
}

export function describeUnavailableDownload(
  source: CoastSnapDataSource,
  state: Exclude<CoastSnapDownloadState, "available" | "sample-demo">,
): { label: string; description: string } {
  switch (state) {
    case "processing":
      return {
        label: "Original processing",
        description: "This observation is still being processed. The original will be available once processing finishes.",
      };
    case "failed":
      return {
        label: "Processing failed",
        description: "Processing failed for this observation, so no original file is available.",
      };
    case "restricted":
      return {
        label: "Original restricted",
        description: "This observation's publication status does not permit downloading the original file.",
      };
    case "unavailable":
      return source === "sample"
        ? {
            label: "Original unavailable",
            description:
              "This development prototype does not mark this observation’s original as available. Once real observations are ingested from Spotteron, availability here will follow the record’s actual publication status.",
          }
        : {
            label: "Original unavailable",
            description: "The original file is not offered for download for this observation.",
          };
  }
}

// --- Product-level downloads ----------------------------------------------------------------

export type CoastSnapProductLevel = "level0" | "level1";

/** Fixed, user-facing copy for each product level. */
export const PRODUCT_LEVEL_COPY: Record<
  CoastSnapProductLevel,
  { action: string; name: string; description: string }
> = {
  level0: {
    action: "Download original (Level 0)",
    name: "Level 0 (untouched source image)",
    description: "Level 0 is the untouched source image, exactly as it was contributed through Spotteron.",
  },
  level1: {
    action: "Download provenance copy (Level 1)",
    name: "Level 1 (provenance copy)",
    description:
      "Level 1 is the same image with AusCIN provenance metadata embedded (source platform, site and processing details).",
  },
};

export type OfferedLevelDownload = {
  level: CoastSnapProductLevel;
  url: string;
  action: string;
  description: string;
  checksumSha256?: string;
};

export type WithheldLevelDownload = { level: CoastSnapProductLevel; reason: string };

/** Everything the detail page needs to render its data-access actions. */
export type CoastSnapDownloadView =
  | { kind: "sample-demo"; url: string }
  | { kind: "levels"; offered: OfferedLevelDownload[]; withheld: WithheldLevelDownload[] }
  | { kind: "none"; label: string; description: string };

export function getCoastSnapDownloadView(
  source: CoastSnapDataSource,
  observation: DownloadFields,
): CoastSnapDownloadView {
  const state = getCoastSnapDownloadState(source, observation);
  if (state === "sample-demo" && observation.originalUrl) {
    return { kind: "sample-demo", url: observation.originalUrl };
  }
  if (state !== "available") {
    return { kind: "none", ...describeUnavailableDownload(source, state === "sample-demo" ? "unavailable" : state) };
  }

  const offered: OfferedLevelDownload[] = [];
  const withheld: WithheldLevelDownload[] = [];
  for (const level of ["level0", "level1"] as const) {
    const available = level === "level0" ? observation.level0DownloadAvailable : observation.level1DownloadAvailable;
    const url = level === "level0" ? observation.level0DownloadUrl : observation.level1DownloadUrl;
    const checksum = level === "level0" ? observation.level0ChecksumSha256 : observation.level1ChecksumSha256;
    if (available && url) {
      offered.push({
        level,
        url,
        action: PRODUCT_LEVEL_COPY[level].action,
        description: PRODUCT_LEVEL_COPY[level].description,
        checksumSha256: checksum,
      });
    } else {
      withheld.push({
        level,
        reason: `${PRODUCT_LEVEL_COPY[level].name} is not offered for download for this observation.`,
      });
    }
  }
  return { kind: "levels", offered, withheld };
}

import type { CoastSnapDataSource, CoastSnapObservation } from "@/data";

/**
 * Wording for CoastSnap records that depends on where they came from. Sample
 * fixtures keep their "development record" disclaimers and prototype download
 * wording. API-backed records are only labelled synthetic when the catalogue
 * says so (`isSynthetic`), and they get real download wording.
 */

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
  "isOriginalAvailable" | "originalUrl" | "processingStatus" | "publicationStatus"
>;

export function getCoastSnapDownloadState(
  source: CoastSnapDataSource,
  observation: DownloadFields,
): CoastSnapDownloadState {
  if (observation.isOriginalAvailable && observation.originalUrl) {
    return source === "sample" ? "sample-demo" : "available";
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

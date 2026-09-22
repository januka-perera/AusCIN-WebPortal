import type { MediaItem } from "@/data";

/**
 * The explicit set of "can a visitor get the original file" outcomes for
 * an observation, independent of whether a preview/thumbnail exists.
 *
 * - "original-available": an original file exists and downloading it is
 *   permitted. Not currently reachable from the sample dataset — this
 *   prototype never sets `originalUrl` — but the branch is real and
 *   tested so a future API returning an actual original needs no UI
 *   change here.
 * - "restricted": no original is offered because the record's
 *   publication status does not permit it (independent of whether
 *   processing has finished).
 * - "unavailable-prototype": no original exists yet for a reason that
 *   isn't a publication restriction — in this prototype, that always
 *   means originals simply aren't served yet.
 */
export type MediaAccessState = "original-available" | "restricted" | "unavailable-prototype";

export function getMediaAccessState(
  item: Pick<MediaItem, "originalUrl" | "publicationStatus">,
): MediaAccessState {
  if (item.originalUrl) return "original-available";
  if (item.publicationStatus === "restricted") return "restricted";
  return "unavailable-prototype";
}

/**
 * Whether a rendered preview can be shown at all, as distinct from
 * whether the *original* is downloadable (see getMediaAccessState).
 * Processing state gates the preview; publication status does not — an
 * embargoed or restricted item can still have a processed preview, it
 * simply isn't offered as a download.
 */
export type PreviewAvailability = "available" | "processing" | "failed" | "unavailable";

export function getPreviewAvailability(
  item: Pick<MediaItem, "previewUrl" | "thumbnailUrl" | "processingStatus">,
): PreviewAvailability {
  if (item.previewUrl || item.thumbnailUrl) return "available";
  if (item.processingStatus === "processing") return "processing";
  if (item.processingStatus === "failed") return "failed";
  return "unavailable";
}

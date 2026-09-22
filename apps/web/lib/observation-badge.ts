import type { StatusTone } from "@/components/ui/status-label";
import type { MediaType, ProcessingStatus, PublicationStatus } from "@/data";
import { getProcessingStatusTone, getPublicationStatusTone } from "@/lib/status-tone";

export function formatMediaTypeLabel(type: MediaType): string {
  return type === "timelapse" ? "Time-lapse" : type.charAt(0).toUpperCase() + type.slice(1);
}

export function formatPublicationLabel(status: PublicationStatus): string {
  return status.charAt(0).toUpperCase() + status.slice(1).replace("-", " ");
}

/** Any observation-shaped record with these two status fields — deliberately not tied to `MediaItem`, so CoastSnapObservation satisfies this too without either type depending on the other. */
type ObservationStatusFields = {
  processingStatus: ProcessingStatus;
  publicationStatus: PublicationStatus;
};

/**
 * Only surfaces a badge when there's something worth flagging on a
 * thumbnail; ordinary public, processed items stay unbadged so the
 * gallery doesn't turn into a wall of labels.
 */
export function getObservationBadge(item: ObservationStatusFields): { label: string; tone: StatusTone } | null {
  if (item.processingStatus === "processing") {
    return { label: "Processing", tone: getProcessingStatusTone(item.processingStatus) };
  }
  if (item.processingStatus === "failed") {
    return { label: "Failed", tone: getProcessingStatusTone(item.processingStatus) };
  }
  if (item.publicationStatus !== "public") {
    return {
      label: formatPublicationLabel(item.publicationStatus),
      tone: getPublicationStatusTone(item.publicationStatus),
    };
  }
  return null;
}

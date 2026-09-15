import type { StatusTone } from "@/components/ui/status-label";
import type { OperatingStatus, ProcessingStatus, PublicationStatus } from "@/data";

/**
 * Maps domain status values to the restrained StatusLabel tones, so the
 * mapping lives in one place instead of being re-decided at each call site.
 */

export function getOperatingStatusTone(status: OperatingStatus): StatusTone {
  return status === "active" ? "positive" : "caution";
}

export function getProcessingStatusTone(status: ProcessingStatus): StatusTone {
  if (status === "failed") return "restricted";
  if (status === "processing") return "neutral";
  return "positive";
}

export function getPublicationStatusTone(status: PublicationStatus): StatusTone {
  if (status === "restricted") return "restricted";
  if (status === "public") return "positive";
  return "caution"; // embargoed, project-only
}

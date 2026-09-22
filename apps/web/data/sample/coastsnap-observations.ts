import type { CoastSnapObservation } from "../types/coastsnap";

/**
 * Synthetic CoastSnap observations for Driftwood Bay only — Saltmarsh
 * Point deliberately has none yet (see coastsnap-sites.ts), to exercise
 * a site with no observations. Covers, across four records: multiple
 * observation dates, multiple contributors, a normal public image, a
 * missing preview, and an item still processing. No original file is
 * ever set (see CoastSnapObservation.originalUrl) — this prototype does
 * not serve production downloads.
 */
export const COASTSNAP_OBSERVATIONS: CoastSnapObservation[] = [
  {
    id: "CS-DRIFTWOOD-OBS-001",
    siteId: "CS-DRIFTWOOD",
    sourcePlatform: "spotteron",
    mediaId: "CS-DRIFTWOOD-OBS-001-MEDIA",
    mediaType: "image",
    capturedAtUtc: "2026-08-01T02:15:00.000Z",
    displayTimeZone: "Australia/Sydney",
    contributor: { displayName: "Priya K.", attributionText: "CoastSnap community photo" },
    processingStatus: "processed",
    publicationStatus: "public",
    thumbnailUrl: "/sample-media/thumbnails/beach-wide.svg",
    previewUrl: "/sample-media/previews/beach-wide.svg",
    originalUrl: null,
    caption: "Driftwood Bay — morning shoreline, contributed 1 August 2026",
    altText: "Wide view of Driftwood Bay's shoreline, photographed from the CoastSnap alignment mark.",
    isSynthetic: true,
  },
  {
    id: "CS-DRIFTWOOD-OBS-002",
    siteId: "CS-DRIFTWOOD",
    sourcePlatform: "spotteron",
    mediaId: "CS-DRIFTWOOD-OBS-002-MEDIA",
    mediaType: "image",
    capturedAtUtc: "2026-08-01T05:40:00.000Z",
    displayTimeZone: "Australia/Sydney",
    contributor: { displayName: "CoastSnap Contributor #217", attributionText: "CoastSnap community photo" },
    processingStatus: "processed",
    // Edge case: processed, but the preview render is unavailable (thumbnail still exists).
    thumbnailUrl: "/sample-media/thumbnails/beach-wide.svg",
    previewUrl: null,
    publicationStatus: "public",
    originalUrl: null,
    caption: "Driftwood Bay — midday shoreline, contributed 1 August 2026 (preview unavailable)",
    altText: "Shoreline view of Driftwood Bay; a full preview could not be generated for this capture.",
    isSynthetic: true,
  },
  {
    id: "CS-DRIFTWOOD-OBS-003",
    siteId: "CS-DRIFTWOOD",
    sourcePlatform: "spotteron",
    mediaId: "CS-DRIFTWOOD-OBS-003-MEDIA",
    mediaType: "image",
    capturedAtUtc: "2026-08-05T03:05:00.000Z",
    displayTimeZone: "Australia/Sydney",
    contributor: { displayName: "Priya K.", attributionText: "CoastSnap community photo" },
    processingStatus: "processed",
    publicationStatus: "public",
    thumbnailUrl: "/sample-media/thumbnails/beach-wide.svg",
    previewUrl: "/sample-media/previews/beach-wide.svg",
    originalUrl: null,
    caption: "Driftwood Bay — shoreline, contributed 5 August 2026",
    altText: "Wide view of Driftwood Bay's shoreline, photographed from the CoastSnap alignment mark.",
    isSynthetic: true,
  },
  {
    id: "CS-DRIFTWOOD-OBS-004",
    siteId: "CS-DRIFTWOOD",
    sourcePlatform: "spotteron",
    mediaId: "CS-DRIFTWOOD-OBS-004-MEDIA",
    mediaType: "image",
    capturedAtUtc: "2026-08-10T04:20:00.000Z",
    displayTimeZone: "Australia/Sydney",
    contributor: { displayName: "Tom R.", attributionText: "CoastSnap community photo" },
    // Edge case: still processing — nothing to render yet.
    processingStatus: "processing",
    publicationStatus: "embargoed",
    thumbnailUrl: null,
    previewUrl: null,
    originalUrl: null,
    caption: "Driftwood Bay — capture from 10 August 2026 is still processing",
    altText: "This CoastSnap contribution is still processing; no preview is available yet.",
    isSynthetic: true,
  },
];

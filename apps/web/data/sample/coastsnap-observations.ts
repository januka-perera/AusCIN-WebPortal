import type { CoastSnapObservation } from "../types/coastsnap";

/**
 * Synthetic CoastSnap observations for Driftwood Bay only — Saltmarsh
 * Point deliberately has none yet (see coastsnap-sites.ts), to exercise
 * a site with no observations. Covers, across six records: multiple
 * observation dates, multiple contributors, a normal public image, a
 * missing preview, an item still processing, a composite media type,
 * and one clearly-labelled mock "original available" download used
 * only to exercise that UI state — every other record leaves
 * isOriginalAvailable false and originalUrl null, since this prototype
 * does not serve real production downloads.
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
    width: 4032,
    height: 3024,
    contributor: { displayName: "Priya K.", attributionText: "CoastSnap community photo" },
    processingStatus: "processed",
    publicationStatus: "public",
    thumbnailUrl: "/sample-media/thumbnails/beach-wide.svg",
    previewUrl: "/sample-media/previews/beach-wide.svg",
    isOriginalAvailable: false,
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
    width: 4032,
    height: 3024,
    contributor: { displayName: "CoastSnap Contributor #217", attributionText: "CoastSnap community photo" },
    processingStatus: "processed",
    // Edge case: processed, but the preview render is unavailable (thumbnail still exists).
    thumbnailUrl: "/sample-media/thumbnails/beach-wide.svg",
    previewUrl: null,
    publicationStatus: "public",
    isOriginalAvailable: false,
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
    width: 4032,
    height: 3024,
    contributor: { displayName: "Priya K.", attributionText: "CoastSnap community photo" },
    processingStatus: "processed",
    publicationStatus: "public",
    thumbnailUrl: "/sample-media/thumbnails/beach-wide.svg",
    previewUrl: "/sample-media/previews/beach-wide.svg",
    isOriginalAvailable: false,
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
    isOriginalAvailable: false,
    originalUrl: null,
    caption: "Driftwood Bay — capture from 10 August 2026 is still processing",
    altText: "This CoastSnap contribution is still processing; no preview is available yet.",
    isSynthetic: true,
  },
  {
    id: "CS-DRIFTWOOD-OBS-005",
    siteId: "CS-DRIFTWOOD",
    sourcePlatform: "spotteron",
    mediaId: "CS-DRIFTWOOD-OBS-005-MEDIA",
    // Edge case: a media type other than "image", to exercise media-type filtering.
    mediaType: "composite",
    capturedAtUtc: "2026-08-15T02:30:00.000Z",
    displayTimeZone: "Australia/Sydney",
    width: 4032,
    height: 3024,
    contributor: { displayName: "Priya K.", attributionText: "CoastSnap community photo" },
    processingStatus: "processed",
    publicationStatus: "public",
    thumbnailUrl: "/sample-media/thumbnails/beach-wide.svg",
    previewUrl: "/sample-media/previews/beach-wide.svg",
    isOriginalAvailable: false,
    originalUrl: null,
    caption: "Driftwood Bay — stacked high-tide composite, contributed 15 August 2026",
    altText: "A stacked composite of Driftwood Bay's shoreline at high tide.",
    isSynthetic: true,
  },
  {
    id: "CS-DRIFTWOOD-OBS-006",
    siteId: "CS-DRIFTWOOD",
    sourcePlatform: "spotteron",
    mediaId: "CS-DRIFTWOOD-OBS-006-MEDIA",
    mediaType: "image",
    capturedAtUtc: "2026-08-18T03:00:00.000Z",
    displayTimeZone: "Australia/Sydney",
    width: 4032,
    height: 3024,
    contributor: { displayName: "Tom R.", attributionText: "CoastSnap community photo" },
    processingStatus: "processed",
    publicationStatus: "public",
    thumbnailUrl: "/sample-media/thumbnails/beach-wide.svg",
    previewUrl: "/sample-media/previews/beach-wide.svg",
    // Edge case: the one record in this prototype marked as having an
    // available original — originalUrl points at an existing local
    // placeholder asset (not a real photo, not a filesystem or /g/data
    // path) purely to exercise the "download available" UI state. The
    // detail page must label this a prototype/mock download, never a
    // real production file.
    isOriginalAvailable: true,
    originalUrl: "/sample-media/previews/beach-wide.svg",
    caption: "Driftwood Bay — shoreline, contributed 18 August 2026 (prototype download demo)",
    altText: "Wide view of Driftwood Bay's shoreline, used to demonstrate the download-available UI state.",
    isSynthetic: true,
  },
];

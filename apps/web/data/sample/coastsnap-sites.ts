import type { CoastSnapSite } from "../types/coastsnap";

/**
 * Two fictional CoastSnap sites used for local development and testing
 * only. Names, locations and descriptions are invented — they do not
 * correspond to any real CoastSnap installation, real Spotteron spot,
 * or real coastal monitoring program. None of these sites has been
 * ingested from Spotteron; see `isSynthetic`.
 */
export const COASTSNAP_SITES: CoastSnapSite[] = [
  {
    id: "CS-DRIFTWOOD",
    name: "Driftwood Bay CoastSnap",
    state: "NSW",
    latitude: -33.45,
    longitude: 151.4,
    region: "Central Coast, NSW",
    description:
      "A community photo-monitoring point on a sheltered bay, where visitors line up a phone photo against a fixed alignment mark to track the beach over time.",
    status: "active",
    establishedSince: "2024-11-01",
    representativeImageUrl: "/sample-media/thumbnails/beach-wide.svg",
    isSynthetic: true,
  },
  {
    id: "CS-SALTMARSH",
    name: "Saltmarsh Point CoastSnap",
    state: "VIC",
    latitude: -38.28,
    longitude: 144.62,
    region: "Bellarine Peninsula, VIC",
    description:
      "A newly installed alignment mark on a low-energy point. Set up for public contributions, but no submissions have come in yet.",
    status: "active",
    establishedSince: "2026-07-01",
    representativeImageUrl: "/sample-media/thumbnails/water-calm.svg",
    isSynthetic: true,
  },
];

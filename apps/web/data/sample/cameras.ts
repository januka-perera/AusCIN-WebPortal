import type { Camera } from "../types/media";

/**
 * Two cameras per station (see stations.ts). Kestrel Head's second
 * camera is deliberately "offline" to exercise that edge case in the
 * interface; every other camera is active.
 */
export const CAMERAS: Camera[] = [
  // Seaglass Point (NSW)
  {
    id: "STN-SEAGLASS-CAM1",
    stationId: "STN-SEAGLASS",
    name: "Seaglass Point — North",
    type: "fixed",
    resolution: { width: 1920, height: 1080 },
    viewDirection: "S",
    captureIntervalMinutes: 30,
    status: "active",
  },
  {
    id: "STN-SEAGLASS-CAM2",
    stationId: "STN-SEAGLASS",
    name: "Seaglass Point — South",
    type: "fixed",
    resolution: { width: 1920, height: 1080 },
    viewDirection: "SW",
    captureIntervalMinutes: 30,
    status: "active",
  },

  // Kestrel Head (VIC)
  {
    id: "STN-KESTREL-CAM1",
    stationId: "STN-KESTREL",
    name: "Kestrel Head — Point",
    type: "fixed",
    resolution: { width: 1920, height: 1080 },
    viewDirection: "SW",
    captureIntervalMinutes: 30,
    status: "active",
  },
  {
    id: "STN-KESTREL-CAM2",
    stationId: "STN-KESTREL",
    name: "Kestrel Head — PTZ",
    type: "ptz",
    resolution: { width: 2560, height: 1440 },
    viewDirection: "W",
    captureIntervalMinutes: 15,
    status: "offline",
  },

  // Windara Bluff (SA)
  {
    id: "STN-WINDARA-CAM1",
    stationId: "STN-WINDARA",
    name: "Windara Bluff — East",
    type: "fixed",
    resolution: { width: 1920, height: 1080 },
    viewDirection: "E",
    captureIntervalMinutes: 30,
    status: "active",
  },
  {
    id: "STN-WINDARA-CAM2",
    stationId: "STN-WINDARA",
    name: "Windara Bluff — Jetty",
    type: "fixed",
    resolution: { width: 1920, height: 1080 },
    viewDirection: "NE",
    captureIntervalMinutes: 30,
    status: "active",
  },

  // Cape Mirrigan (WA)
  {
    id: "STN-MIRRIGAN-CAM1",
    stationId: "STN-MIRRIGAN",
    name: "Cape Mirrigan — Dune",
    type: "fixed",
    resolution: { width: 1920, height: 1080 },
    viewDirection: "SW",
    captureIntervalMinutes: 30,
    status: "active",
  },
  {
    id: "STN-MIRRIGAN-CAM2",
    stationId: "STN-MIRRIGAN",
    name: "Cape Mirrigan — Lidar",
    type: "lidar",
    resolution: { width: 1024, height: 1024 },
    viewDirection: "SW",
    captureIntervalMinutes: 60,
    status: "active",
  },

  // Talwarra Beach (QLD)
  {
    id: "STN-TALWARRA-CAM1",
    stationId: "STN-TALWARRA",
    name: "Talwarra Beach — Pier",
    type: "fixed",
    resolution: { width: 1920, height: 1080 },
    viewDirection: "E",
    captureIntervalMinutes: 30,
    status: "active",
  },
  {
    id: "STN-TALWARRA-CAM2",
    stationId: "STN-TALWARRA",
    name: "Talwarra Beach — Dune",
    type: "fixed",
    resolution: { width: 1920, height: 1080 },
    viewDirection: "NE",
    captureIntervalMinutes: 30,
    status: "active",
  },

  // Bluewater Spit (TAS)
  {
    id: "STN-BLUEWATER-CAM1",
    stationId: "STN-BLUEWATER",
    name: "Bluewater Spit — North",
    type: "fixed",
    resolution: { width: 1920, height: 1080 },
    viewDirection: "NE",
    captureIntervalMinutes: 30,
    status: "active",
  },
  {
    id: "STN-BLUEWATER-CAM2",
    stationId: "STN-BLUEWATER",
    name: "Bluewater Spit — PTZ",
    type: "ptz",
    resolution: { width: 2560, height: 1440 },
    viewDirection: "N",
    captureIntervalMinutes: 15,
    status: "active",
  },
];

import type { Station } from "../types/media";

/**
 * Six fictional coastal observation stations used for local development
 * and testing only. Locations are loosely inspired by Australian coastal
 * environments but do not correspond to real AusCIN stations, real
 * precise coordinates, or real monitoring infrastructure.
 */
export const STATIONS: Station[] = [
  {
    id: "STN-SEAGLASS",
    name: "Seaglass Point",
    state: "NSW",
    latitude: -34.42,
    longitude: 150.89,
    region: "Illawarra, NSW",
    description:
      "A south-facing sandy beach station monitoring swell and shoreline position along the Illawarra coast.",
    viewDirection: "S",
    elevationMetres: 14,
    operationalStatus: "active",
    operationalSince: "2018-03-01",
    representativeImageUrl: "/sample-media/thumbnails/beach-wide.svg",
    cameraCount: 2,
  },
  {
    id: "STN-KESTREL",
    name: "Kestrel Head",
    state: "VIC",
    latitude: -38.35,
    longitude: 144.28,
    region: "Surf Coast, VIC",
    description:
      "An exposed headland station overlooking a rocky point, used to track wave energy on the open Surf Coast.",
    viewDirection: "SW",
    elevationMetres: 32,
    operationalStatus: "active",
    operationalSince: "2019-07-15",
    representativeImageUrl: "/sample-media/thumbnails/headland-rocky.svg",
    cameraCount: 2,
  },
  {
    id: "STN-WINDARA",
    name: "Windara Bluff",
    state: "SA",
    latitude: -35.5,
    longitude: 138.45,
    region: "Fleurieu Peninsula, SA",
    description:
      "A sheltered gulf-facing station recording calmer water conditions on the Fleurieu Peninsula.",
    viewDirection: "E",
    elevationMetres: 9,
    operationalStatus: "active",
    operationalSince: "2020-01-20",
    representativeImageUrl: "/sample-media/thumbnails/water-calm.svg",
    cameraCount: 2,
  },
  {
    id: "STN-MIRRIGAN",
    name: "Cape Mirrigan",
    state: "WA",
    latitude: -34.0,
    longitude: 115.15,
    region: "South West, WA",
    description:
      "A South West station pairing a fixed camera with a lidar scanner to track dune and shoreline change.",
    viewDirection: "SW",
    elevationMetres: 21,
    operationalStatus: "active",
    operationalSince: "2021-05-10",
    representativeImageUrl: "/sample-media/thumbnails/lidar-composite.svg",
    cameraCount: 2,
  },
  {
    id: "STN-TALWARRA",
    name: "Talwarra Beach",
    state: "QLD",
    latitude: -26.65,
    longitude: 153.09,
    region: "Sunshine Coast, QLD",
    description:
      "A subtropical beach station capturing conditions on a popular stretch of the Sunshine Coast.",
    viewDirection: "E",
    elevationMetres: 11,
    operationalStatus: "active",
    operationalSince: "2017-11-02",
    representativeImageUrl: "/sample-media/thumbnails/sunset.svg",
    cameraCount: 2,
  },
  {
    id: "STN-BLUEWATER",
    name: "Bluewater Spit",
    state: "TAS",
    latitude: -41.75,
    longitude: 148.27,
    region: "East Coast, TAS",
    description:
      "A remote east-coast station with limited connectivity, monitoring a low-energy sandy spit.",
    viewDirection: "NE",
    elevationMetres: 6,
    operationalStatus: "active",
    operationalSince: "2022-02-18",
    representativeImageUrl: "/sample-media/thumbnails/night-low-light.svg",
    cameraCount: 2,
  },
];

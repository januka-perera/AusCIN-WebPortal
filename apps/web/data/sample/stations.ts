import type { Station } from "../types/media";

/**
 * Seven fictional coastal observation stations used for local development
 * and testing only. Locations are loosely inspired by Australian coastal
 * environments but do not correspond to real AusCIN stations, real
 * precise coordinates, or real monitoring infrastructure.
 *
 * Station operating status is deliberately varied (active, offline and
 * maintenance) so the interface exercises all three states rather than
 * only ever showing a fully active network.
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
  },
  {
    id: "STN-BLUEWATER",
    name: "Bluewater Spit",
    state: "TAS",
    latitude: -41.75,
    longitude: 148.27,
    region: "East Coast, TAS",
    description:
      "A remote east-coast station with limited connectivity, monitoring a low-energy sandy spit. Currently offline pending a site visit to restore its uplink.",
    viewDirection: "NE",
    elevationMetres: 6,
    // Edge case: an offline station. Its archive still holds the media
    // captured before it went offline, so the historical record remains
    // browsable even though the station is not currently reporting.
    operationalStatus: "offline",
    operationalSince: "2022-02-18",
    representativeImageUrl: "/sample-media/thumbnails/night-low-light.svg",
  },
  {
    id: "STN-PELICAN",
    name: "Pelican Reach",
    state: "NT",
    latitude: -12.47,
    longitude: 130.98,
    region: "Top End, NT",
    description:
      "A newly commissioned Top End station, installed to extend coverage into the Northern Territory. Its camera is being calibrated and has not yet recorded a capture.",
    viewDirection: "N",
    elevationMetres: 4,
    // Edge case: a maintenance station with no observations at all, and
    // a camera that has never captured anything — exercises both the
    // "station with no observations" and "camera with no observations"
    // states without contradicting the "offline" state used above.
    operationalStatus: "maintenance",
    operationalSince: "2025-02-01",
    representativeImageUrl: "/sample-media/thumbnails/beach-wide.svg",
  },
];

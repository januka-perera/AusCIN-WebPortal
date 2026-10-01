import type { MapLocation, MapLocationKind } from "./types";

/**
 * Text shared by the server-rendered location list and the client map.
 * No data-layer imports, so the client map bundle stays free of them.
 */

export const MAP_LOCATION_KIND_LABELS: Record<MapLocationKind, string> = {
  station: "Fixed station",
  coastsnap: "CoastSnap site",
};

function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

/** e.g. "2 cameras · 14 observations" for a station, "6 observations" for a CoastSnap site. */
export function describeLocationCounts(location: Pick<MapLocation, "cameraCount" | "observationCount">): string {
  const observations = plural(location.observationCount, "observation");
  return location.cameraCount === null ? observations : `${plural(location.cameraCount, "camera")} · ${observations}`;
}

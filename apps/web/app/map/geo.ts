/**
 * A plain latitude/longitude bounding box covering mainland Australia
 * and Tasmania, used to project station coordinates onto a simple 2D
 * plotting area. This is a fixed linear projection (equirectangular,
 * not geographically precise at this scale) chosen for simplicity and
 * to avoid any external map tiles or a mapping dependency.
 */
export const MAP_BOUNDS = {
  minLat: -44,
  maxLat: -10,
  minLon: 112,
  maxLon: 154,
};

export type ProjectedPoint = {
  xPercent: number;
  yPercent: number;
};

/** Projects a latitude/longitude pair to a percentage position within MAP_BOUNDS (0,0 = top-left / north-west). */
export function projectToPercent(latitude: number, longitude: number): ProjectedPoint {
  const { minLat, maxLat, minLon, maxLon } = MAP_BOUNDS;
  const xPercent = ((longitude - minLon) / (maxLon - minLon)) * 100;
  const yPercent = ((maxLat - latitude) / (maxLat - minLat)) * 100;
  return { xPercent, yPercent };
}

/** Latitude gridlines (whole 10-degree steps) that fall within MAP_BOUNDS. */
export function latitudeTicks(): number[] {
  const ticks: number[] = [];
  for (let lat = -10; lat >= MAP_BOUNDS.minLat; lat -= 10) {
    if (lat <= MAP_BOUNDS.maxLat && lat >= MAP_BOUNDS.minLat) ticks.push(lat);
  }
  return ticks;
}

/** Longitude gridlines (whole 10-degree steps) that fall within MAP_BOUNDS. */
export function longitudeTicks(): number[] {
  const ticks: number[] = [];
  for (let lon = 110; lon <= 160; lon += 10) {
    if (lon >= MAP_BOUNDS.minLon && lon <= MAP_BOUNDS.maxLon) ticks.push(lon);
  }
  return ticks;
}

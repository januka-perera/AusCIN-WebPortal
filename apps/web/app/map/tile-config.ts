/**
 * Resolves which raster tile source the network map uses. Kept as a pure
 * function of explicit env values (rather than reading process.env
 * directly) so it is easy to unit test every configuration state.
 *
 * NEXT_PUBLIC_MAP_TILE_URL should point at a licensed, production-approved
 * tile provider (e.g. MapTiler, Stadia Maps, Mapbox raster tiles) before
 * this prototype is ever deployed. When it is unset, this falls back to
 * OpenStreetMap's public tile server, which OSM's own usage policy
 * permits for light development and testing but not for production
 * traffic — that fallback is clearly flagged so it is never mistaken for
 * a production-ready configuration. Setting the env var to the literal
 * value "disabled" simulates "no tile source available" so the
 * fallback-to-station-list behaviour can be exercised deliberately.
 */

export const OSM_DEV_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const OSM_DEV_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

export type TileConfig =
  | { available: true; url: string; attribution: string; isDevDefault: boolean }
  | { available: false };

export function resolveTileConfig(
  tileUrl: string | undefined,
  attribution: string | undefined,
): TileConfig {
  if (tileUrl === "disabled") {
    return { available: false };
  }

  if (tileUrl && tileUrl.trim().length > 0) {
    return {
      available: true,
      url: tileUrl,
      attribution: attribution && attribution.trim().length > 0 ? attribution : OSM_DEV_ATTRIBUTION,
      isDevDefault: false,
    };
  }

  return {
    available: true,
    url: OSM_DEV_TILE_URL,
    attribution: OSM_DEV_ATTRIBUTION,
    isDevDefault: true,
  };
}

"use client";

import dynamic from "next/dynamic";
import type { TileConfig } from "./tile-config";
import type { MapStationSummary } from "./types";

// Leaflet reads `window` at module load time, so the map must never be
// part of the server-rendered bundle. next/dynamic with ssr:false can
// only be used from a Client Component, hence this thin wrapper around
// the server page's usage of the actual map.
const StationMap = dynamic(() => import("./station-map"), {
  ssr: false,
  loading: () => (
    <div
      className="flex h-[320px] w-full items-center justify-center border border-border bg-accent/5 text-small text-muted sm:h-[420px] lg:h-[520px]"
      aria-hidden="true"
    >
      Loading map&hellip;
    </div>
  ),
});

type MapLoaderProps = {
  stations: MapStationSummary[];
  tileConfig: Extract<TileConfig, { available: true }>;
};

export function MapLoader({ stations, tileConfig }: MapLoaderProps) {
  return <StationMap stations={stations} tileConfig={tileConfig} />;
}

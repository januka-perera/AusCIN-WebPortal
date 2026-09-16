"use client";

import "leaflet/dist/leaflet.css";
import "./station-map.css";
import L from "leaflet";
import Link from "next/link";
import { useMemo } from "react";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import type { TileConfig } from "./tile-config";
import type { MapStationSummary } from "./types";

type StationMapProps = {
  stations: MapStationSummary[];
  tileConfig: Extract<TileConfig, { available: true }>;
};

// A fixed fallback view centred on the Australian mainland, used only
// when there is one (or zero) filtered stations to derive bounds from.
const AUSTRALIA_CENTER: [number, number] = [-27, 134];
const AUSTRALIA_DEFAULT_ZOOM = 4;

function markerIcon(tone: MapStationSummary["tone"]): L.DivIcon {
  // Active stations get a solid fill, everything else a hollow ring —
  // a shape difference as well as a colour one, matching the station
  // list's status treatment so status is never colour-only.
  const style =
    tone === "positive"
      ? "background:var(--color-accent);border-color:var(--color-accent);"
      : "background:var(--color-surface);border-color:var(--color-secondary-accent);";
  return L.divIcon({
    className: "auscin-marker-icon",
    html: `<span class="auscin-marker-dot" style="${style}"></span>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
    popupAnchor: [0, -10],
  });
}

export default function StationMap({ stations, tileConfig }: StationMapProps) {
  const bounds = useMemo(() => {
    if (stations.length < 2) return undefined;
    return L.latLngBounds(stations.map((station): [number, number] => [station.latitude, station.longitude]));
  }, [stations]);

  const center: [number, number] =
    stations.length === 1 ? [stations[0].latitude, stations[0].longitude] : AUSTRALIA_CENTER;
  const zoom = stations.length === 1 ? 9 : AUSTRALIA_DEFAULT_ZOOM;

  return (
    <div
      className="h-[320px] w-full border border-border sm:h-[420px] lg:h-[520px]"
      role="group"
      aria-label="Interactive map of AusCIN station locations across Australia"
    >
      <MapContainer
        center={center}
        zoom={zoom}
        bounds={bounds}
        boundsOptions={{ padding: [32, 32] }}
        minZoom={3}
        maxZoom={14}
        scrollWheelZoom={false}
        className="h-full w-full"
      >
        <TileLayer url={tileConfig.url} attribution={tileConfig.attribution} />
        {stations.map((station) => (
          <Marker
            key={station.id}
            position={[station.latitude, station.longitude]}
            icon={markerIcon(station.tone)}
            title={`${station.name}, ${station.state}, ${station.region}. Status: ${station.operationalStatus}. ${station.cameraCount} cameras, ${station.mediaCount} observations.`}
          >
            <Popup>
              <p className="text-small font-medium text-foreground">{station.name}</p>
              <p className="mt-1 text-meta uppercase tracking-label text-muted">
                {station.state} &middot; {station.region}
              </p>
              <p className="mt-1 text-meta uppercase tracking-label text-muted">
                {station.operationalStatus} &middot; {station.cameraCount} camera
                {station.cameraCount === 1 ? "" : "s"} &middot; {station.mediaCount} observation
                {station.mediaCount === 1 ? "" : "s"}
              </p>
              <span className="mt-2 flex flex-col items-start gap-1">
                <Link
                  href={`/stations/${station.id}`}
                  className="text-small font-medium text-accent hover:text-accent-strong"
                >
                  Station record &rarr;
                </Link>
                <a
                  href={`#station-${station.id}`}
                  className="text-small font-medium text-accent hover:text-accent-strong"
                >
                  Find in station list &darr;
                </a>
              </span>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}

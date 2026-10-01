"use client";

import "leaflet/dist/leaflet.css";
import "./station-map.css";
import L from "leaflet";
import Link from "next/link";
import { useMemo } from "react";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import { describeLocationCounts, MAP_LOCATION_KIND_LABELS } from "./labels";
import type { TileConfig } from "./tile-config";
import type { MapLocation } from "./types";

type StationMapProps = {
  locations: MapLocation[];
  tileConfig: Extract<TileConfig, { available: true }>;
};

// A fixed fallback view centred on the Australian mainland, used only
// when there is one (or zero) filtered locations to derive bounds from.
const AUSTRALIA_CENTER: [number, number] = [-27, 134];
const AUSTRALIA_DEFAULT_ZOOM = 4;

function markerIcon(tone: MapLocation["tone"]): L.DivIcon {
  // Active locations get a solid fill, everything else a hollow ring —
  // a shape difference as well as a colour one, matching the location
  // list's status treatment so status is never colour-only. Fixed
  // stations and CoastSnap sites share this marker; each one's kind is
  // stated in its marker title and popup.
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

export default function StationMap({ locations, tileConfig }: StationMapProps) {
  const bounds = useMemo(() => {
    if (locations.length < 2) return undefined;
    return L.latLngBounds(locations.map((location): [number, number] => [location.latitude, location.longitude]));
  }, [locations]);

  const center: [number, number] =
    locations.length === 1 ? [locations[0].latitude, locations[0].longitude] : AUSTRALIA_CENTER;
  const zoom = locations.length === 1 ? 9 : AUSTRALIA_DEFAULT_ZOOM;

  return (
    <div
      className="h-[320px] w-full border border-border sm:h-[420px] lg:h-[520px]"
      role="group"
      aria-label="Interactive map of AusCIN stations and CoastSnap sites across Australia"
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
        {locations.map((location) => (
          <Marker
            key={location.anchorId}
            position={[location.latitude, location.longitude]}
            icon={markerIcon(location.tone)}
            title={`${MAP_LOCATION_KIND_LABELS[location.kind]}: ${location.name}, ${location.state}, ${location.region}. Status: ${location.operationalStatus}. ${describeLocationCounts(location)}.`}
          >
            <Popup>
              <p className="text-small font-medium text-foreground">{location.name}</p>
              <p className="mt-1 text-meta uppercase tracking-label text-muted">
                {MAP_LOCATION_KIND_LABELS[location.kind]} &middot; {location.state} &middot; {location.region}
              </p>
              <p className="mt-1 text-meta uppercase tracking-label text-muted">
                {location.operationalStatus} &middot; {describeLocationCounts(location)}
              </p>
              <span className="mt-2 flex flex-col items-start gap-1">
                <Link href={location.href} className="text-small font-medium text-accent hover:text-accent-strong">
                  {location.kind === "coastsnap" ? "Site record" : "Station record"} &rarr;
                </Link>
                <a
                  href={`#${location.anchorId}`}
                  className="text-small font-medium text-accent hover:text-accent-strong"
                >
                  Find in location list &darr;
                </a>
              </span>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}

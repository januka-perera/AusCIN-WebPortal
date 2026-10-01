import type { OperatingStatus, StateOrTerritory } from "@/data";
import type { StatusTone } from "@/components/ui/status-label";

/** What a plotted location is: a fixed AusCIN station, or a CoastSnap community photo site. */
export type MapLocationKind = "station" | "coastsnap";

/**
 * One plotted location, either a fixed station or a CoastSnap site, with
 * only what the map and its list need. Kept separate from the data-layer
 * types so the client map component never imports the data layer — the
 * server page resolves these (see locations.ts) and passes them down as
 * plain props. Links are explicit, so nothing hard-codes `/stations/{id}`.
 */
export type MapLocation = {
  id: string;
  kind: MapLocationKind;
  name: string;
  state: StateOrTerritory;
  region: string;
  latitude: number;
  longitude: number;
  operationalStatus: OperatingStatus;
  tone: StatusTone;
  /** Installed cameras at a fixed station. Null for a CoastSnap site, which has none. */
  cameraCount: number | null;
  observationCount: number;
  /** The location's record page: /stations/{id} or /coastsnap/{id}. */
  href: string;
  /** The location's observation archive. */
  archiveHref: string;
  /** Unique DOM id of the location's list row, unique across both kinds. */
  anchorId: string;
};

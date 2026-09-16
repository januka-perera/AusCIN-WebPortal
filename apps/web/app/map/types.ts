import type { OperatingStatus, StateOrTerritory } from "@/data";
import type { StatusTone } from "@/components/ui/status-label";

/**
 * The subset of a station record (plus derived counts and status tone)
 * the interactive map needs. Kept separate from the full Station type so
 * the client map component never has to import the data layer directly —
 * the server page resolves this from getAllStations/getCamerasForStation/
 * getMediaForStation and passes it down as plain props.
 */
export type MapStationSummary = {
  id: string;
  name: string;
  state: StateOrTerritory;
  region: string;
  latitude: number;
  longitude: number;
  operationalStatus: OperatingStatus;
  tone: StatusTone;
  cameraCount: number;
  mediaCount: number;
};

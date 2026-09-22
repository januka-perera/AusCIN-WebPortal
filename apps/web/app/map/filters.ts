import type { OperatingStatus, StateOrTerritory, Station } from "@/data";
import { firstParam, type SearchParams } from "@/lib/media-filters";

export { firstParam };
export type { SearchParams };

const OPERATING_STATUSES: OperatingStatus[] = ["active", "offline", "maintenance"];

export type MapFilters = {
  state?: StateOrTerritory;
  region?: string;
  status?: OperatingStatus;
};

/** Parses and validates state/region/status query params against the actual station data. Invalid values are dropped, not rejected. */
export function parseMapFilters(search: SearchParams, stations: Station[]): MapFilters {
  const availableStates = new Set(stations.map((station) => station.state));
  const stateParam = firstParam(search.state) as StateOrTerritory | undefined;
  const state = stateParam && availableStates.has(stateParam) ? stateParam : undefined;

  const availableRegions = new Set(stations.map((station) => station.region));
  const regionParam = firstParam(search.region);
  const region = regionParam && availableRegions.has(regionParam) ? regionParam : undefined;

  const statusParam = firstParam(search.status);
  const status = OPERATING_STATUSES.find((candidate) => candidate === statusParam);

  return { state, region, status };
}

/** Applies each filter additively (AND); a contradictory combination safely yields zero results. */
export function applyMapFilters(stations: Station[], filters: MapFilters): Station[] {
  return stations.filter((station) => {
    if (filters.state && station.state !== filters.state) return false;
    if (filters.region && station.region !== filters.region) return false;
    if (filters.status && station.operationalStatus !== filters.status) return false;
    return true;
  });
}

export function hasActiveFilters(filters: MapFilters): boolean {
  return Boolean(filters.state || filters.region || filters.status);
}

export function countActiveFilters(filters: MapFilters): number {
  let count = 0;
  if (filters.state) count += 1;
  if (filters.region) count += 1;
  if (filters.status) count += 1;
  return count;
}

export type MapParamState = {
  state?: string;
  region?: string;
  status?: string;
};

export function filtersToParamState(filters: MapFilters): MapParamState {
  return { state: filters.state, region: filters.region, status: filters.status };
}

export function buildMapHref(state: MapParamState): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(state)) {
    if (value) params.set(key, value);
  }
  const query = params.toString();
  return `/map${query ? `?${query}` : ""}`;
}

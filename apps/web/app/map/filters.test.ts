import { describe, expect, it } from "vitest";
import { STATIONS } from "@/data";
import {
  applyMapFilters,
  buildMapHref,
  countActiveFilters,
  hasActiveFilters,
  parseMapFilters,
  type SearchParams,
} from "./filters";

describe("parseMapFilters", () => {
  it("resolves a state present in the station list", () => {
    const filters = parseMapFilters({ state: "NSW" }, STATIONS);
    expect(filters.state).toBe("NSW");
  });

  it("drops a state not present in the station list", () => {
    const filters = parseMapFilters({ state: "ZZ" } as SearchParams, STATIONS);
    expect(filters.state).toBeUndefined();
  });

  it("drops a region not present in the station list", () => {
    const filters = parseMapFilters({ region: "Nowhereville" }, STATIONS);
    expect(filters.region).toBeUndefined();
  });

  it("drops an unrecognised operating status", () => {
    const filters = parseMapFilters({ status: "on-fire" }, STATIONS);
    expect(filters.status).toBeUndefined();
  });

  it("accepts a valid operating status", () => {
    const filters = parseMapFilters({ status: "offline" }, STATIONS);
    expect(filters.status).toBe("offline");
  });

  it("never throws for a fully invalid search and yields no active filters", () => {
    const search: SearchParams = { state: "ZZ", region: "nowhere", status: "unknown" };
    expect(() => parseMapFilters(search, STATIONS)).not.toThrow();
    const filters = parseMapFilters(search, STATIONS);
    expect(hasActiveFilters(filters)).toBe(false);
    expect(countActiveFilters(filters)).toBe(0);
  });
});

describe("applyMapFilters", () => {
  it("filters stations by operating status", () => {
    const filters = parseMapFilters({ status: "offline" }, STATIONS);
    const filtered = applyMapFilters(STATIONS, filters);
    expect(filtered.every((station) => station.operationalStatus === "offline")).toBe(true);
  });

  it("a contradictory state/region combination yields zero results, not an error", () => {
    const station = STATIONS[0];
    const otherRegion = STATIONS.find((candidate) => candidate.region !== station.region)?.region;
    const filtered = applyMapFilters(STATIONS, { state: station.state, region: otherRegion });
    expect(filtered).toEqual([]);
  });

  it("returns every station when no filters are set", () => {
    expect(applyMapFilters(STATIONS, {})).toEqual(STATIONS);
  });
});

describe("countActiveFilters", () => {
  it("counts each of state, region and status independently", () => {
    expect(countActiveFilters({ state: "NSW", region: "Illawarra, NSW", status: "active" })).toBe(3);
  });
});

describe("buildMapHref", () => {
  it("builds a bare /map href with no params set", () => {
    expect(buildMapHref({})).toBe("/map");
  });

  it("omits empty values from the query string", () => {
    expect(buildMapHref({ state: "NSW", region: "" })).toBe("/map?state=NSW");
  });

  it("includes every set param", () => {
    const href = buildMapHref({ state: "NSW", status: "active" });
    expect(href).toBe("/map?state=NSW&status=active");
  });
});

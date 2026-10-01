import { describe, expect, it, vi } from "vitest";
import {
  createCoastSnapRepository,
  repository,
  type CoastSnapRepository,
  type CoastSnapSite,
} from "@/data";
import { HttpCoastSnapRepository } from "@/data/coastsnap-http-repository";
import { applyMapFilters, parseMapFilters } from "./filters";
import { describeLocationCounts } from "./labels";
import { hasPlottableCoordinates, loadMapLocations } from "./locations";

/** No test here makes a network request: the HTTP repository gets an in-memory fake fetch. */

const API = "http://localhost:8000";
const sampleCoastSnap = createCoastSnapRepository({});

/** An API-shaped site, as /api/v1/coastsnap/sites returns it (worker-confirmed coordinates). */
function apiSite(id: string, overrides: Record<string, unknown> = {}) {
  return {
    id,
    name: `${id} CoastSnap`,
    state: "NSW",
    latitude: -33.000417,
    longitude: 151.000263,
    region: "Synthetic test region",
    description: "Synthetic CoastSnap site used only by the frontend test suite.",
    status: "active",
    establishedSince: "2026-07-01",
    displayTimeZone: "Australia/Sydney",
    representativeImageUrl: null,
    isSynthetic: true,
    ...overrides,
  };
}

function apiPage(total: number, pageSize: number) {
  return { items: [], total, page: 1, pageSize, totalPages: Math.max(1, Math.ceil(total / pageSize)) };
}

function httpCoastSnap(sites: unknown[], totals: Record<string, number>, status = 200) {
  const requests: string[] = [];
  const fetchImpl = (async (input: RequestInfo | URL) => {
    const url = new URL(String(input));
    requests.push(`${url.pathname}${url.search}`);
    if (status !== 200) return new Response("{}", { status });
    const match = url.pathname.match(/^\/api\/v1\/coastsnap\/sites\/([^/]+)\/observations$/);
    const body = match
      ? apiPage(totals[match[1]] ?? 0, Number(url.searchParams.get("pageSize")))
      : sites;
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  }) as typeof fetch;
  return { repository: new HttpCoastSnapRepository({ apiBaseUrl: API, fetchImpl }), requests };
}

describe("loadMapLocations with the sample repositories", () => {
  it("combines fixed stations and CoastSnap sites", async () => {
    const { locations, coastSnapUnavailable } = await loadMapLocations(repository, sampleCoastSnap);
    const stations = await repository.listStations();

    expect(coastSnapUnavailable).toBe(false);
    expect(locations.filter((l) => l.kind === "station").map((l) => l.id)).toEqual(stations.map((s) => s.id));
    expect(locations.filter((l) => l.kind === "coastsnap").map((l) => l.id)).toEqual(["CS-DRIFTWOOD"]);
  });

  it("excludes a CoastSnap site with no observations, matching the catalogue API", async () => {
    const sites = (await sampleCoastSnap.listSites()).map((site) => site.id);
    expect(sites).toContain("CS-SALTMARSH"); // in the sample data, but has no observations
    const { locations } = await loadMapLocations(repository, sampleCoastSnap);
    expect(locations.map((l) => l.id)).not.toContain("CS-SALTMARSH");
  });

  it("links each kind to its own record and archive pages", async () => {
    const { locations } = await loadMapLocations(repository, sampleCoastSnap);
    const station = locations.find((l) => l.id === "STN-SEAGLASS");
    const site = locations.find((l) => l.id === "CS-DRIFTWOOD");

    expect(station).toMatchObject({
      href: "/stations/STN-SEAGLASS",
      archiveHref: "/stations/STN-SEAGLASS/archive",
      anchorId: "station-STN-SEAGLASS",
    });
    expect(site).toMatchObject({
      href: "/coastsnap/CS-DRIFTWOOD",
      archiveHref: "/coastsnap/CS-DRIFTWOOD/archive",
      anchorId: "coastsnap-CS-DRIFTWOOD",
      cameraCount: null,
      observationCount: 6,
    });
  });

  it("gives every location a unique list anchor", async () => {
    const { locations } = await loadMapLocations(repository, sampleCoastSnap);
    expect(new Set(locations.map((l) => l.anchorId)).size).toBe(locations.length);
  });

  it("counts CoastSnap observations from a one-item page, never the full archive", async () => {
    const paginated = vi.fn(sampleCoastSnap.listObservationsForSitePaginated);
    const full = vi.fn(sampleCoastSnap.listObservationsForSite);
    await loadMapLocations(repository, {
      ...sampleCoastSnap,
      listSites: () => sampleCoastSnap.listSites(),
      listObservationsForSitePaginated: paginated,
      listObservationsForSite: full,
    });

    expect(full).not.toHaveBeenCalled();
    expect(paginated).toHaveBeenCalledTimes(2);
    for (const call of paginated.mock.calls) expect(call[2]).toEqual({ page: 1, pageSize: 1 });
  });
});

describe("loadMapLocations with the catalogue API", () => {
  it("passes API site coordinates to the map unchanged and uses the page total as the count", async () => {
    const { repository: coastSnap, requests } = httpCoastSnap([apiSite("CS-TEST-SITE")], { "CS-TEST-SITE": 5 });
    const { locations } = await loadMapLocations(repository, coastSnap);
    const site = locations.find((l) => l.kind === "coastsnap");

    expect(site).toMatchObject({ id: "CS-TEST-SITE", latitude: -33.000417, longitude: 151.000263, observationCount: 5 });
    expect(requests).toEqual([
      "/api/v1/coastsnap/sites",
      "/api/v1/coastsnap/sites/CS-TEST-SITE/observations?page=1&pageSize=1",
    ]);
  });

  it("still plots fixed stations when no CoastSnap site is eligible", async () => {
    const { repository: coastSnap } = httpCoastSnap([], {});
    const { locations, coastSnapUnavailable } = await loadMapLocations(repository, coastSnap);
    expect(coastSnapUnavailable).toBe(false);
    expect(locations.length).toBeGreaterThan(0);
    expect(locations.every((l) => l.kind === "station")).toBe(true);
  });

  it("defensively excludes an API site that reports zero observations", async () => {
    const { repository: coastSnap } = httpCoastSnap([apiSite("CS-A"), apiSite("CS-B")], { "CS-A": 2, "CS-B": 0 });
    const { locations } = await loadMapLocations(repository, coastSnap);
    expect(locations.filter((l) => l.kind === "coastsnap").map((l) => l.id)).toEqual(["CS-A"]);
  });

  it("reports an unavailable catalogue but keeps the fixed stations", async () => {
    const { repository: coastSnap } = httpCoastSnap([], {}, 503);
    const { locations, coastSnapUnavailable } = await loadMapLocations(repository, coastSnap);
    expect(coastSnapUnavailable).toBe(true);
    expect(locations.length).toBe((await repository.listStations()).length);
  });

  it("does not swallow unexpected errors", async () => {
    const broken = { ...sampleCoastSnap, listSites: async () => { throw new TypeError("bug"); } };
    await expect(loadMapLocations(repository, broken)).rejects.toThrow("bug");
  });
});

describe("coordinates reaching the map", () => {
  function fakeCoastSnap(sites: CoastSnapSite[]): CoastSnapRepository {
    return {
      ...sampleCoastSnap,
      listSites: async () => sites,
      listObservationsForSitePaginated: async () => ({ items: [], total: 3, page: 1, pageSize: 1, totalPages: 3 }),
    };
  }

  it("never passes an invalid or missing coordinate to the map", async () => {
    const [template] = await sampleCoastSnap.listSites();
    const bad = [
      { ...template, id: "CS-NAN", latitude: Number.NaN },
      { ...template, id: "CS-INF", longitude: Number.POSITIVE_INFINITY },
      { ...template, id: "CS-RANGE", latitude: -91 },
      { ...template, id: "CS-NULL", latitude: null as unknown as number },
    ];
    const { locations } = await loadMapLocations(repository, fakeCoastSnap([...bad, template]));
    expect(locations.filter((l) => l.kind === "coastsnap").map((l) => l.id)).toEqual([template.id]);
    expect(locations.every(hasPlottableCoordinates)).toBe(true);
  });
});

describe("map filters across both kinds", () => {
  it("applies the state filter to fixed stations and CoastSnap sites alike", async () => {
    const { locations } = await loadMapLocations(repository, sampleCoastSnap);
    const nsw = applyMapFilters(locations, parseMapFilters({ state: "NSW" }, locations));
    expect(nsw.map((l) => [l.kind, l.id])).toEqual([
      ["station", "STN-SEAGLASS"],
      ["coastsnap", "CS-DRIFTWOOD"],
    ]);
  });

  it("offers and applies a region that only a CoastSnap site has", async () => {
    const { locations } = await loadMapLocations(repository, sampleCoastSnap);
    const filters = parseMapFilters({ region: "Central Coast, NSW" }, locations);
    expect(filters.region).toBe("Central Coast, NSW");
    expect(applyMapFilters(locations, filters).map((l) => l.id)).toEqual(["CS-DRIFTWOOD"]);
  });

  it("applies the operational status filter to both kinds", async () => {
    const { locations } = await loadMapLocations(repository, sampleCoastSnap);
    const active = applyMapFilters(locations, parseMapFilters({ status: "active" }, locations));
    expect(active.some((l) => l.kind === "coastsnap")).toBe(true);
    expect(active.every((l) => l.operationalStatus === "active")).toBe(true);
  });
});

describe("describeLocationCounts", () => {
  it("describes cameras only for fixed stations", () => {
    expect(describeLocationCounts({ cameraCount: 2, observationCount: 1 })).toBe("2 cameras · 1 observation");
    expect(describeLocationCounts({ cameraCount: null, observationCount: 6 })).toBe("6 observations");
  });
});

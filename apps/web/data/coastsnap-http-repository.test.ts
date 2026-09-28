import { describe, expect, it } from "vitest";
import {
  CoastSnapApiError,
  HttpCoastSnapRepository,
  MAX_FULL_LIST_OBSERVATIONS,
  normalizeMediaUrl,
} from "./coastsnap-http-repository";

/**
 * Payloads below are copied from the real fixture-backed API (apps/api, run
 * against tests/fixtures/coastsnap). No test makes a network request: every
 * request goes to an in-memory fake `fetch`.
 */

const API = "http://localhost:8000";
const SITE_ID = "CS-TEST-SITE";
const MEDIA_ID = "csm_5cea933ee069d94a0cd93aaa";
const MEDIA_ID_2 = "csm_0a1b2c3d4e5f60718293a4b5";

const apiSite = {
  id: SITE_ID,
  name: "Test Beach CoastSnap",
  state: "NSW",
  latitude: -33.0,
  longitude: 151.0,
  region: "Synthetic test region",
  description: "Synthetic CoastSnap site used only by the API test suite and local development. Not a real location.",
  status: "active",
  establishedSince: "2026-07-01",
  displayTimeZone: "Australia/Sydney",
  representativeImageUrl: null,
  isSynthetic: true,
};

type ApiObservation = Record<string, unknown>;

function apiObservation(overrides: ApiObservation = {}): ApiObservation {
  const mediaId = (overrides.mediaId as string | undefined) ?? MEDIA_ID;
  return {
    id: mediaId,
    siteId: SITE_ID,
    sourcePlatform: "spotteron",
    mediaId,
    mediaType: "image",
    capturedAtUtc: "2026-09-01T00:10:00Z",
    capturedAtSourceRaw: "2026-09-01 00:10:00",
    ingestedAtUtc: "2026-09-02T01:00:00Z",
    displayTimeZone: "Australia/Sydney",
    contributor: {
      displayName: "CoastSnap contributor",
      attributionText: "CoastSnap community photo (synthetic test data)",
    },
    processingStatus: "processed",
    publicationStatus: "public",
    thumbnailUrl: `${API}/media/coastsnap/${mediaId}/thumbnail`,
    previewUrl: `${API}/media/coastsnap/${mediaId}/preview`,
    isOriginalAvailable: true,
    originalUrl: `${API}/media/coastsnap/${mediaId}/original`,
    caption: "Test Beach CoastSnap — CoastSnap observation, 1 September 2026",
    altText: "Community photo of Test Beach CoastSnap taken from the CoastSnap alignment mark on 1 September 2026.",
    isSynthetic: true,
    ...overrides,
  };
}

function page(items: ApiObservation[], extra: Record<string, number> = {}) {
  return { items, total: items.length, page: 1, pageSize: 24, totalPages: 1, ...extra };
}

type Route = (url: URL) => { status: number; body?: unknown } | undefined;

/** A fake fetch that records every request URL and answers from `route`. Unrouted requests get the API's 404 shape. */
function fakeFetch(route: Route) {
  const requests: URL[] = [];
  const fetchImpl = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(input instanceof Request ? input.url : input.toString());
    requests.push(url);
    expect(init?.cache).toBe("no-store");
    const answer = route(url) ?? { status: 404, body: { error: { code: "not_found", message: "x" } } };
    return new Response(answer.body === undefined ? null : JSON.stringify(answer.body), {
      status: answer.status,
      headers: { "content-type": "application/json" },
    });
  }) as typeof fetch;
  return { fetchImpl, requests };
}

function repo(route: Route, options: { apiBaseUrl?: string; mediaOrigin?: string } = {}) {
  const { fetchImpl, requests } = fakeFetch(route);
  const repository = new HttpCoastSnapRepository({ apiBaseUrl: options.apiBaseUrl ?? API, mediaOrigin: options.mediaOrigin, fetchImpl });
  return { repository, requests };
}

const standardRoutes: Route = (url) => {
  switch (url.pathname) {
    case "/api/v1/coastsnap/sites":
      return { status: 200, body: [apiSite] };
    case `/api/v1/coastsnap/sites/${SITE_ID}`:
      return { status: 200, body: apiSite };
    case `/api/v1/coastsnap/sites/${SITE_ID}/observations`:
      return { status: 200, body: page([apiObservation(), apiObservation({ mediaId: MEDIA_ID_2 })]) };
    case `/api/v1/coastsnap/sites/${SITE_ID}/observations/${MEDIA_ID}`:
      return { status: 200, body: apiObservation() };
    case `/api/v1/coastsnap/sites/${SITE_ID}/date-range`:
      return {
        status: 200,
        body: { earliest: apiObservation({ mediaId: MEDIA_ID_2, capturedAtUtc: "2026-08-01T22:30:00Z" }), latest: apiObservation() },
      };
    default:
      return undefined;
  }
};

// --- Sites -----------------------------------------------------------------------

describe("HttpCoastSnapRepository sites", () => {
  it("lists the API site mapped onto CoastSnapSite", async () => {
    const { repository, requests } = repo(standardRoutes);
    const sites = await repository.listSites();
    expect(sites).toEqual([
      {
        id: SITE_ID,
        name: "Test Beach CoastSnap",
        state: "NSW",
        latitude: -33,
        longitude: 151,
        region: "Synthetic test region",
        description: apiSite.description,
        status: "active",
        establishedSince: "2026-07-01",
        representativeImageUrl: null,
        isSynthetic: true,
      },
    ]);
    expect(requests[0].toString()).toBe(`${API}/api/v1/coastsnap/sites`);
  });

  it("maps an API 404 to an absent site", async () => {
    const { repository } = repo(standardRoutes);
    await expect(repository.getSite("CS-UNKNOWN")).resolves.toBeUndefined();
  });

  it("answers malformed site IDs without making a request", async () => {
    const { repository, requests } = repo(standardRoutes);
    await expect(repository.getSite("../../etc/passwd")).resolves.toBeUndefined();
    await expect(repository.getSite("a/b")).resolves.toBeUndefined();
    expect(requests).toHaveLength(0);
  });

  it("honours a path prefix on the API base URL", async () => {
    const { repository, requests } = repo(
      (url) => (url.pathname === "/catalogue/api/v1/coastsnap/sites" ? { status: 200, body: [apiSite] } : undefined),
      { apiBaseUrl: "http://localhost:8000/catalogue/" },
    );
    await expect(repository.listSites()).resolves.toHaveLength(1);
    expect(requests[0].pathname).toBe("/catalogue/api/v1/coastsnap/sites");
  });
});

// --- Observations and pagination --------------------------------------------------------

describe("HttpCoastSnapRepository observations", () => {
  it("fetches a site's observations with filters and pagination mapped to query parameters", async () => {
    const { repository, requests } = repo((url) =>
      url.pathname.endsWith("/observations")
        ? { status: 200, body: page([apiObservation()], { total: 9, page: 2, pageSize: 4, totalPages: 3 }) }
        : undefined,
    );
    const result = await repository.listObservationsForSitePaginated(
      SITE_ID,
      { mediaType: "image", from: "2026-08-01", to: "2026-08-31" },
      { page: 2, pageSize: 4 },
    );
    expect(result.total).toBe(9);
    expect(result.page).toBe(2);
    expect(result.pageSize).toBe(4);
    expect(result.totalPages).toBe(3);
    expect(result.items.map((item) => item.id)).toEqual([MEDIA_ID]);
    const query = requests[0].searchParams;
    expect(Object.fromEntries(query)).toEqual({
      mediaType: "image",
      from: "2026-08-01",
      to: "2026-08-31",
      page: "2",
      pageSize: "4",
    });
  });

  it("clamps the page size to the API maximum", async () => {
    const { repository, requests } = repo((url) =>
      url.pathname.endsWith("/observations") ? { status: 200, body: page([]) } : undefined,
    );
    await repository.listObservationsForSitePaginated(SITE_ID, {}, { page: 0, pageSize: 5000 });
    expect(requests[0].searchParams.get("pageSize")).toBe("100");
    expect(requests[0].searchParams.get("page")).toBe("1");
  });

  it("maps an observation onto CoastSnapObservation, dropping API-only fields", async () => {
    const { repository } = repo(standardRoutes);
    const observation = await repository.getObservationForSite(SITE_ID, MEDIA_ID);
    expect(observation).toEqual({
      id: MEDIA_ID,
      siteId: SITE_ID,
      sourcePlatform: "spotteron",
      mediaId: MEDIA_ID,
      mediaType: "image",
      capturedAtUtc: "2026-09-01T00:10:00Z",
      displayTimeZone: "Australia/Sydney",
      contributor: { displayName: "CoastSnap contributor", attributionText: "CoastSnap community photo (synthetic test data)" },
      processingStatus: "processed",
      publicationStatus: "public",
      thumbnailUrl: `${API}/media/coastsnap/${MEDIA_ID}/thumbnail`,
      previewUrl: `${API}/media/coastsnap/${MEDIA_ID}/preview`,
      isOriginalAvailable: true,
      originalUrl: `${API}/media/coastsnap/${MEDIA_ID}/original`,
      caption: "Test Beach CoastSnap — CoastSnap observation, 1 September 2026",
      altText: "Community photo of Test Beach CoastSnap taken from the CoastSnap alignment mark on 1 September 2026.",
      isSynthetic: true,
    });
    expect(observation).not.toHaveProperty("capturedAtSourceRaw");
    expect(observation).not.toHaveProperty("ingestedAtUtc");
    expect(observation).not.toHaveProperty("width");
  });

  it("keeps width and height when the API supplies both", async () => {
    const { repository } = repo((url) =>
      url.pathname.endsWith(MEDIA_ID) ? { status: 200, body: apiObservation({ width: 4032, height: 3024 }) } : undefined,
    );
    const observation = await repository.getObservationForSite(SITE_ID, MEDIA_ID);
    expect([observation?.width, observation?.height]).toEqual([4032, 3024]);
  });

  it("maps an API 404 to an absent media record", async () => {
    const { repository } = repo(standardRoutes);
    await expect(repository.getObservationForSite(SITE_ID, "csm_000000000000000000000000")).resolves.toBeUndefined();
  });

  it("never returns another site's observation under this site", async () => {
    const { repository } = repo((url) =>
      url.pathname.endsWith(MEDIA_ID) ? { status: 200, body: apiObservation({ siteId: "CS-OTHER" }) } : undefined,
    );
    await expect(repository.getObservationForSite(SITE_ID, MEDIA_ID)).resolves.toBeUndefined();
  });

  it("maps an unknown site to an empty page and an empty list", async () => {
    const { repository } = repo(standardRoutes);
    await expect(repository.listObservationsForSitePaginated("CS-UNKNOWN", {}, { page: 1, pageSize: 4 })).resolves.toEqual({
      items: [],
      total: 0,
      page: 1,
      pageSize: 4,
      totalPages: 1,
    });
    await expect(repository.listObservationsForSite("CS-UNKNOWN")).resolves.toEqual([]);
  });

  it("pages through the API for a full listing", async () => {
    const { repository, requests } = repo((url) => {
      if (!url.pathname.endsWith("/observations")) return undefined;
      const current = Number(url.searchParams.get("page"));
      const mediaId = `csm_page${current}xxxxxxxxxxxxxxxxxx`;
      return { status: 200, body: page([apiObservation({ mediaId })], { total: 3, page: current, pageSize: 100, totalPages: 3 }) };
    });
    const all = await repository.listObservationsForSite(SITE_ID);
    expect(all).toHaveLength(3);
    expect(requests.map((request) => request.searchParams.get("page"))).toEqual(["1", "2", "3"]);
  });

  it("refuses to load an unbounded archive through the full listing", async () => {
    const pageSize = 100;
    const { repository } = repo((url) => {
      const current = Number(url.searchParams.get("page"));
      const items = Array.from({ length: pageSize }, (_, i) => apiObservation({ mediaId: `csm_${current}_${i}` }));
      return { status: 200, body: page(items, { total: 999_999, page: current, pageSize, totalPages: 9_999 }) };
    });
    await expect(repository.listObservationsForSite(SITE_ID)).rejects.toMatchObject({ kind: "invalid-response" });
    expect(MAX_FULL_LIST_OBSERVATIONS).toBeGreaterThan(0);
  });

  it("returns the date range, and undefined for a site with no observations", async () => {
    const { repository } = repo(standardRoutes);
    const range = await repository.getObservationDateRange(SITE_ID);
    expect(range?.earliest.id).toBe(MEDIA_ID_2);
    expect(range?.latest.id).toBe(MEDIA_ID);

    const empty = repo((url) =>
      url.pathname.endsWith("/date-range") ? { status: 200, body: { earliest: null, latest: null } } : undefined,
    );
    await expect(empty.repository.getObservationDateRange(SITE_ID)).resolves.toBeUndefined();
    await expect(repo(standardRoutes).repository.getObservationDateRange("CS-UNKNOWN")).resolves.toBeUndefined();
  });

  it("returns only processed, public newest observations per site", async () => {
    const { repository } = repo((url) => {
      if (url.pathname === "/api/v1/coastsnap/sites") return { status: 200, body: [apiSite] };
      if (url.pathname.endsWith("/observations")) return { status: 200, body: page([apiObservation({ processingStatus: "processing" })]) };
      return undefined;
    });
    await expect(repository.listLatestObservationPerSite()).resolves.toEqual([]);
  });
});

// --- Media URLs, downloads and unavailable states -------------------------------------------

describe("HttpCoastSnapRepository media URLs and download states", () => {
  async function observationWith(overrides: ApiObservation, options: { mediaOrigin?: string } = {}) {
    const { repository } = repo(
      (url) => (url.pathname.endsWith(MEDIA_ID) ? { status: 200, body: apiObservation(overrides) } : undefined),
      options,
    );
    const observation = await repository.getObservationForSite(SITE_ID, MEDIA_ID);
    if (!observation) throw new Error("expected an observation");
    return observation;
  }

  it("keeps null thumbnail and preview URLs as null", async () => {
    const observation = await observationWith({ thumbnailUrl: null, previewUrl: null });
    expect(observation.thumbnailUrl).toBeNull();
    expect(observation.previewUrl).toBeNull();
  });

  it("offers a permitted original download", async () => {
    const observation = await observationWith({});
    expect(observation.isOriginalAvailable).toBe(true);
    expect(observation.originalUrl).toBe(`${API}/media/coastsnap/${MEDIA_ID}/original`);
  });

  it("does not offer a restricted or unavailable original", async () => {
    const restricted = await observationWith({ isOriginalAvailable: false, originalUrl: null });
    expect(restricted.isOriginalAvailable).toBe(false);
    expect(restricted.originalUrl).toBeNull();
  });

  it("never offers a download whose URL fails validation, even if the API says it's available", async () => {
    const observation = await observationWith({ originalUrl: "https://elsewhere.example/media/coastsnap/x/original" });
    expect(observation.isOriginalAvailable).toBe(false);
    expect(observation.originalUrl).toBeNull();
  });

  it("resolves root-relative media URLs against the API origin, never the Next.js origin", async () => {
    const observation = await observationWith({
      thumbnailUrl: `/media/coastsnap/${MEDIA_ID}/thumbnail`,
      previewUrl: `/media/coastsnap/${MEDIA_ID}/preview`,
      originalUrl: `/media/coastsnap/${MEDIA_ID}/original`,
    });
    expect(observation.thumbnailUrl).toBe(`${API}/media/coastsnap/${MEDIA_ID}/thumbnail`);
    expect(observation.previewUrl).toBe(`${API}/media/coastsnap/${MEDIA_ID}/preview`);
    expect(observation.originalUrl).toBe(`${API}/media/coastsnap/${MEDIA_ID}/original`);
    for (const url of [observation.thumbnailUrl, observation.previewUrl, observation.originalUrl]) {
      expect(url).not.toContain("localhost:3000");
    }
  });

  it("uses COASTSNAP_MEDIA_ORIGIN for media when the API is reached on an internal address", async () => {
    const { repository } = repo(
      (url) =>
        url.pathname.endsWith(MEDIA_ID)
          ? {
              status: 200,
              body: apiObservation({
                thumbnailUrl: `/media/coastsnap/${MEDIA_ID}/thumbnail`,
                previewUrl: `https://media.example.test/media/coastsnap/${MEDIA_ID}/preview`,
                originalUrl: `http://127.0.0.1:8000/media/coastsnap/${MEDIA_ID}/original`,
              }),
            }
          : undefined,
      { apiBaseUrl: "http://127.0.0.1:8000", mediaOrigin: "https://media.example.test" },
    );
    const observation = await repository.getObservationForSite(SITE_ID, MEDIA_ID);
    expect(observation?.thumbnailUrl).toBe(`https://media.example.test/media/coastsnap/${MEDIA_ID}/thumbnail`);
    expect(observation?.previewUrl).toBe(`https://media.example.test/media/coastsnap/${MEDIA_ID}/preview`);
    // An absolute URL on the internal API origin isn't browser-reachable, so it's dropped.
    expect(observation?.originalUrl).toBeNull();
    expect(observation?.isOriginalAvailable).toBe(false);
  });

  it.each([
    ["another host", `https://evil.example/media/coastsnap/${MEDIA_ID}/thumbnail`],
    ["protocol-relative host", `//evil.example/media/coastsnap/${MEDIA_ID}/thumbnail`],
    ["file URL", "file:///g/data/qu34/AusCIN/coastsnap/level-1/x.jpg"],
    ["javascript URL", "javascript:alert(1)"],
    ["/g/data path", "/g/data/qu34/AusCIN/coastsnap-test/level-1/root-1/2026/08/01/images/1.jpg"],
    ["staging path", "/level-1/root-TEST_ROOT_ID/2026/08/01/images/TEST_OBS_0001.jpg"],
    ["other API path", "/api/v1/coastsnap/sites"],
    ["another observation's media", `/media/coastsnap/${MEDIA_ID_2}/thumbnail`],
    ["wrong kind", `/media/coastsnap/${MEDIA_ID}/original`],
    ["traversal", `/media/coastsnap/${MEDIA_ID}/../../../etc/passwd`],
    ["query string", `/media/coastsnap/${MEDIA_ID}/thumbnail?path=/g/data`],
    ["credentials", `http://user:pass@localhost:8000/media/coastsnap/${MEDIA_ID}/thumbnail`],
    ["Windows path", "C:\\Users\\someone\\staging\\level-1\\x.jpg"],
    ["non-string", 42],
  ])("drops an unsafe thumbnail URL (%s)", (_label, raw) => {
    expect(normalizeMediaUrl(raw, API, MEDIA_ID, "thumbnail")).toBeNull();
  });

  it("drops an unsafe site representative image URL", async () => {
    const { repository } = repo((url) =>
      url.pathname === "/api/v1/coastsnap/sites"
        ? { status: 200, body: [{ ...apiSite, representativeImageUrl: "/g/data/qu34/site.jpg" }] }
        : undefined,
    );
    const [site] = await repository.listSites();
    expect(site.representativeImageUrl).toBeNull();
  });

  it("never lets filesystem or internal paths into mapped data", async () => {
    const { repository } = repo((url) => {
      if (url.pathname === "/api/v1/coastsnap/sites") return { status: 200, body: [apiSite] };
      if (url.pathname.endsWith("/observations")) {
        return {
          status: 200,
          body: page([
            apiObservation({
              thumbnailUrl: "/g/data/qu34/AusCIN/derivatives/thumbnails/x.jpg",
              previewUrl: "file:///srv/staging/level-1/x.jpg",
              originalUrl: "/level-1/root-TEST_ROOT_ID/x.jpg",
            }),
          ]),
        };
      }
      return undefined;
    });
    const sites = await repository.listSites();
    const observations = await repository.listObservationsForSite(SITE_ID);
    const rendered = JSON.stringify({ sites, observations });
    for (const forbidden of ["/g/data", "qu34", "level-1", "level-0", "derivatives/", "file:", "staging", "TEST_ROOT_ID", "TEST_OBS"]) {
      expect(rendered).not.toContain(forbidden);
    }
  });
});

// --- Controlled failures --------------------------------------------------------------------

describe("HttpCoastSnapRepository failures", () => {
  it("turns a network failure into a controlled error", async () => {
    const fetchImpl = (async () => {
      throw new TypeError("fetch failed: connect ECONNREFUSED 127.0.0.1:8000");
    }) as typeof fetch;
    const repository = new HttpCoastSnapRepository({ apiBaseUrl: API, fetchImpl });
    const error = await repository.listSites().catch((caught) => caught);
    expect(error).toBeInstanceOf(CoastSnapApiError);
    expect(error).toMatchObject({ kind: "network" });
    expect(error.message).not.toContain("127.0.0.1");
    expect(error.message).not.toContain("ECONNREFUSED");
  });

  it("turns a timeout into a controlled error", async () => {
    const fetchImpl = (async () => {
      throw new DOMException("The operation timed out.", "TimeoutError");
    }) as typeof fetch;
    const repository = new HttpCoastSnapRepository({ apiBaseUrl: API, fetchImpl });
    await expect(repository.getSite(SITE_ID)).rejects.toMatchObject({ kind: "timeout" });
  });

  it.each([500, 502, 503, 422, 403])("turns HTTP %i into a controlled error", async (status) => {
    const { repository } = repo(() => ({ status, body: { error: { code: "x", message: "y" } } }));
    await expect(repository.listSites()).rejects.toMatchObject({ kind: "http", status });
  });

  it("rejects a response that isn't JSON", async () => {
    const fetchImpl = (async () => new Response("<html>proxy error</html>", { status: 200 })) as typeof fetch;
    const repository = new HttpCoastSnapRepository({ apiBaseUrl: API, fetchImpl });
    await expect(repository.listSites()).rejects.toMatchObject({ kind: "invalid-response" });
  });

  it.each([
    ["missing field", { ...apiSite, name: undefined }],
    ["wrong type", { ...apiSite, latitude: "-33" }],
    ["unknown enum value", { ...apiSite, status: "decommissioned" }],
    ["unsafe id", { ...apiSite, id: "../x" }],
  ])("rejects a malformed site (%s)", async (_label, body) => {
    const { repository } = repo(() => ({ status: 200, body: [body] }));
    await expect(repository.listSites()).rejects.toMatchObject({ kind: "invalid-response" });
  });

  it("rejects a malformed observation page", async () => {
    const { repository } = repo(() => ({ status: 200, body: { items: "nope", total: 1, page: 1, pageSize: 1, totalPages: 1 } }));
    await expect(repository.listObservationsForSitePaginated(SITE_ID, {}, { page: 1, pageSize: 1 })).rejects.toMatchObject({
      kind: "invalid-response",
    });
  });

  it.each(["localhost:8000", "ftp://localhost", "http://user:pw@localhost:8000", "http://localhost:8000/?x=1", "not a url"])(
    "rejects an invalid COASTSNAP_API_BASE_URL (%s)",
    (apiBaseUrl) => {
      expect(() => new HttpCoastSnapRepository({ apiBaseUrl })).toThrow(CoastSnapApiError);
    },
  );
});

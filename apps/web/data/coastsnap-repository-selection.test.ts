import { afterEach, describe, expect, it, vi } from "vitest";
import { HttpCoastSnapRepository } from "./coastsnap-http-repository";
import { coastSnapRepository, createCoastSnapRepository, getCoastSnapDataSource } from "./coastsnap-repository";
import { COASTSNAP_SITES } from "./sample";

describe("CoastSnap repository selection", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("uses the sample repository when COASTSNAP_API_BASE_URL is absent", async () => {
    expect(getCoastSnapDataSource({})).toBe("sample");
    const repository = createCoastSnapRepository({});
    expect(repository).not.toBeInstanceOf(HttpCoastSnapRepository);
    await expect(repository.listSites()).resolves.toEqual(COASTSNAP_SITES);
  });

  it("treats a blank COASTSNAP_API_BASE_URL as absent", () => {
    expect(getCoastSnapDataSource({ COASTSNAP_API_BASE_URL: "   " })).toBe("sample");
    expect(createCoastSnapRepository({ COASTSNAP_API_BASE_URL: "" })).not.toBeInstanceOf(HttpCoastSnapRepository);
  });

  it("uses the HTTP repository when COASTSNAP_API_BASE_URL is set", () => {
    const env = { COASTSNAP_API_BASE_URL: "http://localhost:8000" };
    expect(getCoastSnapDataSource(env)).toBe("api");
    expect(createCoastSnapRepository(env)).toBeInstanceOf(HttpCoastSnapRepository);
  });

  it("fails loudly, rather than silently showing sample data, for an invalid API URL", () => {
    expect(() => createCoastSnapRepository({ COASTSNAP_API_BASE_URL: "localhost:8000" })).toThrow(/COASTSNAP_API_BASE_URL/);
  });

  it("makes no network request when the environment variable is absent (the default for unit tests)", async () => {
    vi.stubEnv("COASTSNAP_API_BASE_URL", "");
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    await coastSnapRepository.listSites();
    await coastSnapRepository.listObservationsForSite("CS-DRIFTWOOD");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("selects the implementation per call, following the current environment", async () => {
    const fetchSpy = vi.fn(async () => new Response("[]", { status: 200 }));
    vi.stubGlobal("fetch", fetchSpy);

    vi.stubEnv("COASTSNAP_API_BASE_URL", "http://localhost:8000");
    await expect(coastSnapRepository.listSites()).resolves.toEqual([]);
    expect(fetchSpy).toHaveBeenCalledTimes(1);

    vi.stubEnv("COASTSNAP_API_BASE_URL", "");
    await expect(coastSnapRepository.listSites()).resolves.toEqual(COASTSNAP_SITES);
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });
});

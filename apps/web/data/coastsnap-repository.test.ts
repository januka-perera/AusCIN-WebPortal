import { describe, expect, it } from "vitest";
import { coastSnapRepository } from "./coastsnap-repository";
import { COASTSNAP_SITES } from "./sample";

describe("coastSnapRepository.listSites / getSite", () => {
  it("lists every sample site", async () => {
    await expect(coastSnapRepository.listSites()).resolves.toHaveLength(COASTSNAP_SITES.length);
  });

  it("retrieves a site by ID", async () => {
    const site = await coastSnapRepository.getSite("CS-DRIFTWOOD");
    expect(site?.name).toBe("Driftwood Bay CoastSnap");
  });

  it("resolves to undefined for an unknown site ID", async () => {
    await expect(coastSnapRepository.getSite("does-not-exist")).resolves.toBeUndefined();
  });
});

describe("coastSnapRepository.listObservationsForSite", () => {
  it("scopes observations to one site", async () => {
    const observations = await coastSnapRepository.listObservationsForSite("CS-DRIFTWOOD");
    expect(observations.length).toBeGreaterThan(0);
    expect(observations.every((item) => item.siteId === "CS-DRIFTWOOD")).toBe(true);
  });

  it("returns an empty array for a site with no observations", async () => {
    await expect(coastSnapRepository.listObservationsForSite("CS-SALTMARSH")).resolves.toEqual([]);
  });

  it("returns an empty array for an unknown site ID", async () => {
    await expect(coastSnapRepository.listObservationsForSite("does-not-exist")).resolves.toEqual([]);
  });

  it("applies filters within the site scope when given", async () => {
    const observations = await coastSnapRepository.listObservationsForSite("CS-DRIFTWOOD", {
      mediaType: "composite",
    });
    expect(observations).toHaveLength(1);
    expect(observations[0].mediaType).toBe("composite");
  });
});

describe("coastSnapRepository.listObservationsForSitePaginated", () => {
  it("paginates a site's filtered observations, newest first", async () => {
    const page1 = await coastSnapRepository.listObservationsForSitePaginated(
      "CS-DRIFTWOOD",
      {},
      { page: 1, pageSize: 4 },
    );
    expect(page1.items).toHaveLength(4);
    expect(page1.total).toBe(6);
    expect(page1.totalPages).toBe(2);
    for (let i = 1; i < page1.items.length; i += 1) {
      expect(new Date(page1.items[i].capturedAtUtc).getTime()).toBeLessThanOrEqual(
        new Date(page1.items[i - 1].capturedAtUtc).getTime(),
      );
    }
  });

  it("returns the remaining items on the second page", async () => {
    const page2 = await coastSnapRepository.listObservationsForSitePaginated(
      "CS-DRIFTWOOD",
      {},
      { page: 2, pageSize: 4 },
    );
    expect(page2.items).toHaveLength(2);
  });

  it("clamps an out-of-range page to the last valid page", async () => {
    const result = await coastSnapRepository.listObservationsForSitePaginated(
      "CS-DRIFTWOOD",
      {},
      { page: 999, pageSize: 4 },
    );
    expect(result.page).toBe(result.totalPages);
  });

  it("returns an empty page, not an error, for a site with no observations", async () => {
    const result = await coastSnapRepository.listObservationsForSitePaginated(
      "CS-SALTMARSH",
      {},
      { page: 1, pageSize: 4 },
    );
    expect(result.items).toEqual([]);
    expect(result.total).toBe(0);
    expect(result.totalPages).toBe(1);
  });

  it("never leaks another site's matching observations into a filtered, paginated result", async () => {
    const result = await coastSnapRepository.listObservationsForSitePaginated(
      "CS-SALTMARSH",
      { mediaType: "image" },
      { page: 1, pageSize: 10 },
    );
    expect(result.items).toEqual([]);
  });
});

describe("coastSnapRepository.getObservation / getObservationForSite", () => {
  it("retrieves an observation by ID", async () => {
    const observation = await coastSnapRepository.getObservation("CS-DRIFTWOOD-OBS-001");
    expect(observation?.siteId).toBe("CS-DRIFTWOOD");
  });

  it("resolves to undefined for an unknown observation ID", async () => {
    await expect(coastSnapRepository.getObservation("does-not-exist")).resolves.toBeUndefined();
  });

  it("resolves an observation scoped to its real site", async () => {
    const observation = await coastSnapRepository.getObservationForSite("CS-DRIFTWOOD", "CS-DRIFTWOOD-OBS-001");
    expect(observation?.id).toBe("CS-DRIFTWOOD-OBS-001");
  });

  it("never resolves a real observation ID under the wrong site", async () => {
    await expect(
      coastSnapRepository.getObservationForSite("CS-SALTMARSH", "CS-DRIFTWOOD-OBS-001"),
    ).resolves.toBeUndefined();
  });
});

describe("coastSnapRepository.listLatestObservationPerSite", () => {
  it("skips a site with no presentable observations", async () => {
    const latest = await coastSnapRepository.listLatestObservationPerSite();
    expect(latest.some((item) => item.siteId === "CS-SALTMARSH")).toBe(false);
  });
});

describe("coastSnapRepository.getObservationDateRange", () => {
  it("finds the earliest and latest observation for a site with several", async () => {
    const range = await coastSnapRepository.getObservationDateRange("CS-DRIFTWOOD");
    expect(range).toBeDefined();
    expect(new Date(range!.earliest.capturedAtUtc).getTime()).toBeLessThanOrEqual(
      new Date(range!.latest.capturedAtUtc).getTime(),
    );
  });

  it("resolves to undefined for a site with no observations", async () => {
    await expect(coastSnapRepository.getObservationDateRange("CS-SALTMARSH")).resolves.toBeUndefined();
  });

  it("resolves to undefined for an unknown site ID", async () => {
    await expect(coastSnapRepository.getObservationDateRange("does-not-exist")).resolves.toBeUndefined();
  });
});

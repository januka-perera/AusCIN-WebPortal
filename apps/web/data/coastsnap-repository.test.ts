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
});

describe("coastSnapRepository.getObservation", () => {
  it("retrieves an observation by ID", async () => {
    const observation = await coastSnapRepository.getObservation("CS-DRIFTWOOD-OBS-001");
    expect(observation?.siteId).toBe("CS-DRIFTWOOD");
  });

  it("resolves to undefined for an unknown observation ID", async () => {
    await expect(coastSnapRepository.getObservation("does-not-exist")).resolves.toBeUndefined();
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

import { describe, expect, it } from "vitest";
import {
  getAllCoastSnapObservations,
  getAllCoastSnapSites,
  getCoastSnapObservationById,
  getCoastSnapSiteById,
  getLatestObservationPerCoastSnapSite,
  getObservationDateRangeForSite,
  getObservationsForCoastSnapSite,
} from "./coastsnap-queries";
import { COASTSNAP_OBSERVATIONS, COASTSNAP_SITES } from "./sample";
import type { CoastSnapObservation } from "./types/coastsnap";

describe("CoastSnap site lookup", () => {
  it("returns all sample sites", () => {
    expect(getAllCoastSnapSites()).toHaveLength(COASTSNAP_SITES.length);
  });

  it("finds a site by ID", () => {
    const site = getCoastSnapSiteById("CS-DRIFTWOOD");
    expect(site?.name).toBe("Driftwood Bay CoastSnap");
  });

  it("returns undefined for an invalid site ID", () => {
    expect(getCoastSnapSiteById("CS-DOES-NOT-EXIST")).toBeUndefined();
  });

  it("has at least one active site and one site with no observations", () => {
    const siteIdsWithObservations = new Set(COASTSNAP_OBSERVATIONS.map((o) => o.siteId));
    const sitesWithNoObservations = COASTSNAP_SITES.filter(
      (site) => !siteIdsWithObservations.has(site.id),
    );
    expect(sitesWithNoObservations.length).toBeGreaterThanOrEqual(1);
    expect(COASTSNAP_SITES.some((site) => site.status === "active")).toBe(true);
  });

  it("produces the exact site-card data the catalogue page renders: name, region, location, status, observation count", () => {
    const cards = getAllCoastSnapSites().map((site) => ({
      name: site.name,
      region: site.region,
      state: site.state,
      latitude: site.latitude,
      longitude: site.longitude,
      status: site.status,
      observationCount: getObservationsForCoastSnapSite(site.id).length,
    }));
    expect(cards).toEqual([
      {
        name: "Driftwood Bay CoastSnap",
        region: "Central Coast, NSW",
        state: "NSW",
        latitude: -33.45,
        longitude: 151.4,
        status: "active",
        observationCount: 4,
      },
      {
        name: "Saltmarsh Point CoastSnap",
        region: "Bellarine Peninsula, VIC",
        state: "VIC",
        latitude: -38.28,
        longitude: 144.62,
        status: "active",
        observationCount: 0,
      },
    ]);
  });

  it("never sets a real Spotteron site ID in this prototype's sample data", () => {
    expect(COASTSNAP_SITES.every((site) => site.spotteronSiteId === undefined)).toBe(true);
  });

  it("flags every sample site as synthetic", () => {
    expect(COASTSNAP_SITES.every((site) => site.isSynthetic)).toBe(true);
  });
});

describe("CoastSnap observation lookup", () => {
  it("returns all sample observations", () => {
    expect(getAllCoastSnapObservations()).toHaveLength(COASTSNAP_OBSERVATIONS.length);
  });

  it("returns only observations belonging to the requested site", () => {
    const observations = getObservationsForCoastSnapSite("CS-DRIFTWOOD");
    expect(observations.length).toBeGreaterThan(0);
    expect(observations.every((item) => item.siteId === "CS-DRIFTWOOD")).toBe(true);
  });

  it("returns an empty array for the site with no observations", () => {
    expect(getObservationsForCoastSnapSite("CS-SALTMARSH")).toEqual([]);
  });

  it("returns an empty array for an invalid site ID", () => {
    expect(getObservationsForCoastSnapSite("CS-DOES-NOT-EXIST")).toEqual([]);
  });

  it("finds an observation by ID", () => {
    const observation = getCoastSnapObservationById("CS-DRIFTWOOD-OBS-001");
    expect(observation?.siteId).toBe("CS-DRIFTWOOD");
  });

  it("returns undefined for an invalid observation ID", () => {
    expect(getCoastSnapObservationById("CS-DOES-NOT-EXIST")).toBeUndefined();
  });

  it("exercises multiple observation dates and multiple contributors at Driftwood Bay", () => {
    const observations = getObservationsForCoastSnapSite("CS-DRIFTWOOD");
    const dates = new Set(observations.map((item) => item.capturedAtUtc.slice(0, 10)));
    const contributors = new Set(observations.map((item) => item.contributor.displayName));
    expect(dates.size).toBeGreaterThanOrEqual(2);
    expect(contributors.size).toBeGreaterThanOrEqual(2);
  });

  it("has a normal public image, a missing preview, and a still-processing observation", () => {
    const publicImage = COASTSNAP_OBSERVATIONS.find(
      (item) =>
        item.mediaType === "image" &&
        item.publicationStatus === "public" &&
        item.processingStatus === "processed" &&
        item.thumbnailUrl &&
        item.previewUrl,
    );
    const missingPreview = COASTSNAP_OBSERVATIONS.find(
      (item) => item.processingStatus === "processed" && item.previewUrl === null && item.thumbnailUrl,
    );
    const processing = COASTSNAP_OBSERVATIONS.find((item) => item.processingStatus === "processing");
    expect(publicImage).toBeDefined();
    expect(missingPreview).toBeDefined();
    expect(processing).toBeDefined();
    expect(processing?.thumbnailUrl).toBeNull();
  });

  it("never sets an original URL in this prototype's sample data", () => {
    expect(COASTSNAP_OBSERVATIONS.every((item) => item.originalUrl === null)).toBe(true);
  });

  it("flags every sample observation as synthetic and sourced from Spotteron", () => {
    expect(COASTSNAP_OBSERVATIONS.every((item) => item.isSynthetic)).toBe(true);
    expect(COASTSNAP_OBSERVATIONS.every((item) => item.sourcePlatform === "spotteron")).toBe(true);
  });

  it("derives each mediaId from its observation id, but keeps them distinct strings", () => {
    for (const item of COASTSNAP_OBSERVATIONS) {
      expect(item.mediaId).not.toBe(item.id);
      expect(item.mediaId.startsWith(item.id)).toBe(true);
    }
  });
});

describe("getLatestObservationPerCoastSnapSite", () => {
  it("returns one presentable observation per site with any, most recent first", () => {
    const latest = getLatestObservationPerCoastSnapSite();
    expect(latest.every((item) => item.processingStatus === "processed")).toBe(true);
    expect(latest.every((item) => item.publicationStatus === "public")).toBe(true);
    for (let i = 1; i < latest.length; i += 1) {
      expect(new Date(latest[i].capturedAtUtc).getTime()).toBeLessThanOrEqual(
        new Date(latest[i - 1].capturedAtUtc).getTime(),
      );
    }
  });

  it("skips the site with no observations", () => {
    const latest = getLatestObservationPerCoastSnapSite();
    expect(latest.some((item) => item.siteId === "CS-SALTMARSH")).toBe(false);
  });

  it("never returns the same site twice", () => {
    const latest = getLatestObservationPerCoastSnapSite();
    const siteIds = latest.map((item) => item.siteId);
    expect(new Set(siteIds).size).toBe(siteIds.length);
  });
});

describe("getObservationDateRangeForSite", () => {
  it("finds the earliest and latest observation at a site with several", () => {
    const range = getObservationDateRangeForSite("CS-DRIFTWOOD");
    expect(range).toBeDefined();
    expect(range!.earliest.id).toBe("CS-DRIFTWOOD-OBS-001");
    expect(range!.latest.id).toBe("CS-DRIFTWOOD-OBS-004");
  });

  it("returns undefined for a site with no observations", () => {
    expect(getObservationDateRangeForSite("CS-SALTMARSH")).toBeUndefined();
  });

  it("returns undefined for an unknown site ID", () => {
    expect(getObservationDateRangeForSite("CS-DOES-NOT-EXIST")).toBeUndefined();
  });

  it("returns the same single observation as both bounds for a site with exactly one", () => {
    const singleObservationSite = [
      { siteId: "CS-SOLO", capturedAtUtc: "2026-01-01T00:00:00.000Z" } as CoastSnapObservation,
    ];
    const range = getObservationDateRangeForSite("CS-SOLO", singleObservationSite);
    expect(range!.earliest).toBe(range!.latest);
  });
});

import { describe, expect, it } from "vitest";
import { repository } from "./repository";
import { CAMERAS, MEDIA, STATIONS } from "./sample";

describe("repository.listStations / getStation", () => {
  it("lists every sample station", async () => {
    await expect(repository.listStations()).resolves.toHaveLength(STATIONS.length);
  });

  it("retrieves a station by ID", async () => {
    const station = await repository.getStation("STN-SEAGLASS");
    expect(station?.name).toBe("Seaglass Point");
  });

  it("resolves to undefined for an unknown station ID", async () => {
    await expect(repository.getStation("does-not-exist")).resolves.toBeUndefined();
  });
});

describe("repository.listCameras / listCamerasForStation / getCamera", () => {
  it("lists every sample camera", async () => {
    await expect(repository.listCameras()).resolves.toHaveLength(CAMERAS.length);
  });

  it("scopes cameras to one station", async () => {
    const cameras = await repository.listCamerasForStation("STN-KESTREL");
    expect(cameras.every((camera) => camera.stationId === "STN-KESTREL")).toBe(true);
  });

  it("returns an empty array for a station with no cameras", async () => {
    await expect(repository.listCamerasForStation("does-not-exist")).resolves.toEqual([]);
  });

  it("retrieves a camera by ID", async () => {
    const camera = await repository.getCamera("STN-KESTREL-CAM2");
    expect(camera?.status).toBe("offline");
  });
});

describe("repository.listStationObservations", () => {
  it("returns a station's full record for an empty filter set", async () => {
    const observations = await repository.listStationObservations("STN-SEAGLASS", {});
    expect(observations.length).toBeGreaterThan(0);
    expect(observations.every((item) => item.stationId === "STN-SEAGLASS")).toBe(true);
  });

  it("applies media filters within the station scope", async () => {
    const observations = await repository.listStationObservations("STN-SEAGLASS", {
      mediaType: "timelapse",
    });
    expect(observations.length).toBeGreaterThan(0);
    expect(observations.every((item) => item.mediaType === "timelapse")).toBe(true);
  });

  it("returns an empty array for a station with no observations", async () => {
    await expect(repository.listStationObservations("STN-PELICAN", {})).resolves.toEqual([]);
  });

  it("never returns another station's media even when filters resolve to nothing for this one", async () => {
    const observations = await repository.listStationObservations("STN-PELICAN", {
      mediaType: "image",
    });
    expect(observations).toEqual([]);
  });
});

describe("repository.listObservations", () => {
  it("paginates network-wide observations, newest first", async () => {
    const page1 = await repository.listObservations({ page: 1 }, { page: 1, pageSize: 10 });
    expect(page1.items).toHaveLength(10);
    expect(page1.page).toBe(1);
    expect(page1.total).toBe(MEDIA.length);
    for (let i = 1; i < page1.items.length; i += 1) {
      expect(new Date(page1.items[i].capturedAtUtc).getTime()).toBeLessThanOrEqual(
        new Date(page1.items[i - 1].capturedAtUtc).getTime(),
      );
    }
  });

  it("clamps an out-of-range page to the last valid page", async () => {
    const result = await repository.listObservations({ page: 1 }, { page: 9999, pageSize: 10 });
    expect(result.page).toBe(result.totalPages);
  });

  it("applies station/state/region/media filters before paginating", async () => {
    const result = await repository.listObservations(
      { page: 1, mediaType: "timelapse" },
      { page: 1, pageSize: 100 },
    );
    expect(result.items.length).toBeGreaterThan(0);
    expect(result.items.every((item) => item.mediaType === "timelapse")).toBe(true);
  });

  it("returns an empty page (not an error) for filters that match nothing", async () => {
    const result = await repository.listObservations(
      { page: 1, processingStatus: "failed", publicationStatus: "public" },
      { page: 1, pageSize: 10 },
    );
    expect(result.items).toEqual([]);
    expect(result.total).toBe(0);
    expect(result.totalPages).toBe(1);
    expect(result.page).toBe(1);
  });
});

describe("repository.listLatestObservationPerStation", () => {
  it("skips a station with no presentable media", async () => {
    const latest = await repository.listLatestObservationPerStation();
    expect(latest.some((item) => item.stationId === "STN-PELICAN")).toBe(false);
  });
});

describe("repository.getMediaItem / getRelatedMediaItems", () => {
  it("retrieves a media item scoped to its station", async () => {
    const item = await repository.getMediaItem("STN-SEAGLASS", "STN-SEAGLASS-CAM1-20250210-0600");
    expect(item?.stationId).toBe("STN-SEAGLASS");
  });

  it("does not resolve a media item under the wrong station", async () => {
    await expect(
      repository.getMediaItem("STN-KESTREL", "STN-SEAGLASS-CAM1-20250210-0600"),
    ).resolves.toBeUndefined();
  });

  it("resolves a time-lapse's related stills, scoped to the same station", async () => {
    const related = await repository.getRelatedMediaItems(
      "STN-SEAGLASS",
      "STN-SEAGLASS-CAM1-20250210-TIMELAPSE",
    );
    expect(related.length).toBeGreaterThan(0);
    expect(related.every((item) => item.stationId === "STN-SEAGLASS")).toBe(true);
  });
});

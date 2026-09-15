import { describe, expect, it } from "vitest";
import { CAMERAS } from "./sample/cameras";
import { MEDIA } from "./sample/media";
import { STATIONS } from "./sample/stations";
import {
  filterMediaByDateRange,
  filterMediaByType,
  getAllStations,
  getCameraById,
  getCamerasForStation,
  getMediaForCamera,
  getMediaForStation,
  getRelatedMedia,
  getStationById,
  sortMediaByCaptureTime,
} from "./queries";

describe("station lookup", () => {
  it("returns all sample stations", () => {
    expect(getAllStations()).toHaveLength(STATIONS.length);
  });

  it("finds a station by ID", () => {
    const station = getStationById("STN-SEAGLASS");
    expect(station?.name).toBe("Seaglass Point");
  });

  it("returns undefined for an invalid station ID", () => {
    expect(getStationById("STN-DOES-NOT-EXIST")).toBeUndefined();
  });
});

describe("camera lookup", () => {
  it("returns exactly two cameras per station", () => {
    for (const station of STATIONS) {
      expect(getCamerasForStation(station.id)).toHaveLength(2);
    }
  });

  it("returns an empty array for a station with no cameras", () => {
    expect(getCamerasForStation("STN-DOES-NOT-EXIST")).toEqual([]);
  });

  it("finds a camera by ID", () => {
    const camera = getCameraById("STN-KESTREL-CAM2");
    expect(camera?.status).toBe("offline");
  });

  it("returns undefined for an invalid camera ID", () => {
    expect(getCameraById("CAM-DOES-NOT-EXIST")).toBeUndefined();
  });
});

describe("media lookup", () => {
  it("returns at least eight media records for every camera", () => {
    for (const camera of CAMERAS) {
      expect(getMediaForCamera(camera.id).length).toBeGreaterThanOrEqual(8);
    }
  });

  it("returns only media belonging to the requested station", () => {
    const media = getMediaForStation("STN-SEAGLASS");
    expect(media.length).toBeGreaterThan(0);
    expect(media.every((item) => item.stationId === "STN-SEAGLASS")).toBe(true);
  });

  it("returns an empty array for an invalid media owner", () => {
    expect(getMediaForStation("STN-DOES-NOT-EXIST")).toEqual([]);
    expect(getMediaForCamera("CAM-DOES-NOT-EXIST")).toEqual([]);
  });
});

describe("date-range filtering", () => {
  it("finds the day with no observations for the affected camera", () => {
    const media = getMediaForCamera("STN-WINDARA-CAM1");
    // Windara Bluff displays Australia/Adelaide time (UTC+10:30), so local
    // midnight-to-midnight on 2025-02-11 is this UTC window, not the naive
    // 2025-02-11T00:00Z-2025-02-11T23:59Z UTC calendar day (which would
    // wrongly catch the *next* local day's early-morning UTC timestamp).
    const emptyDay = filterMediaByDateRange(
      media,
      "2025-02-10T13:30:00.000Z",
      "2025-02-11T13:29:59.999Z",
    );
    expect(emptyDay).toEqual([]);
  });

  it("has no observations at all for the skipped local date", () => {
    const media = getMediaForCamera("STN-WINDARA-CAM1");
    expect(media.some((item) => item.id.includes("20250211"))).toBe(false);
  });

  it("returns an empty array when nothing falls in range", () => {
    expect(filterMediaByDateRange(MEDIA, "2099-01-01", "2099-01-02")).toEqual([]);
  });

  it("includes items on the boundary of an inclusive range", () => {
    const target = MEDIA.find((item) => item.id === "STN-SEAGLASS-CAM1-20250210-0600")!;
    const result = filterMediaByDateRange(
      [target],
      target.capturedAtUtc,
      target.capturedAtUtc,
    );
    expect(result).toEqual([target]);
  });
});

describe("media-type filtering", () => {
  it("finds every media type represented in the sample data", () => {
    expect(filterMediaByType(MEDIA, "image").length).toBeGreaterThan(0);
    expect(filterMediaByType(MEDIA, "composite").length).toBeGreaterThan(0);
    expect(filterMediaByType(MEDIA, "timelapse").length).toBeGreaterThan(0);
  });

  it("only returns items of the requested type", () => {
    const timelapses = filterMediaByType(MEDIA, "timelapse");
    expect(timelapses.every((item) => item.mediaType === "timelapse")).toBe(true);
  });
});

describe("chronological sorting", () => {
  it("sorts ascending by default", () => {
    const media = getMediaForCamera("STN-SEAGLASS-CAM1");
    const sorted = sortMediaByCaptureTime(media);
    for (let i = 1; i < sorted.length; i += 1) {
      expect(new Date(sorted[i].capturedAtUtc).getTime()).toBeGreaterThanOrEqual(
        new Date(sorted[i - 1].capturedAtUtc).getTime(),
      );
    }
  });

  it("sorts descending when requested", () => {
    const media = getMediaForCamera("STN-SEAGLASS-CAM1");
    const sorted = sortMediaByCaptureTime(media, "desc");
    for (let i = 1; i < sorted.length; i += 1) {
      expect(new Date(sorted[i].capturedAtUtc).getTime()).toBeLessThanOrEqual(
        new Date(sorted[i - 1].capturedAtUtc).getTime(),
      );
    }
  });

  it("does not mutate the input array", () => {
    const media = getMediaForCamera("STN-SEAGLASS-CAM1");
    const originalFirstId = media[0].id;
    sortMediaByCaptureTime(media, "desc");
    expect(media[0].id).toBe(originalFirstId);
  });
});

describe("related media", () => {
  it("resolves a time-lapse's related stills", () => {
    const related = getRelatedMedia("STN-SEAGLASS-CAM1-20250210-TIMELAPSE");
    expect(related.length).toBeGreaterThanOrEqual(5);
    expect(related.every((item) => item.mediaType === "image" || item.mediaType === "composite")).toBe(
      true,
    );
  });

  it("resolves a still's link back to its time-lapse", () => {
    const related = getRelatedMedia("STN-SEAGLASS-CAM1-20250210-0600");
    expect(related.some((item) => item.mediaType === "timelapse")).toBe(true);
  });

  it("returns an empty array for an invalid media ID", () => {
    expect(getRelatedMedia("MEDIA-DOES-NOT-EXIST")).toEqual([]);
  });
});

describe("edge cases baked into the sample data", () => {
  it("has exactly one item still processing", () => {
    const processing = MEDIA.filter((item) => item.processingStatus === "processing");
    expect(processing).toHaveLength(1);
    expect(processing[0].thumbnailUrl).toBeNull();
  });

  it("has exactly one item with an unavailable preview", () => {
    const unavailablePreview = MEDIA.filter(
      (item) => item.processingStatus === "processed" && item.previewUrl === null,
    );
    expect(unavailablePreview).toHaveLength(1);
    expect(unavailablePreview[0].thumbnailUrl).not.toBeNull();
  });

  it("has exactly one failed item", () => {
    const failed = MEDIA.filter((item) => item.processingStatus === "failed");
    expect(failed).toHaveLength(1);
    expect(failed[0].thumbnailUrl).toBeNull();
    expect(failed[0].previewUrl).toBeNull();
  });

  it("has one offline camera", () => {
    const offline = CAMERAS.filter((camera) => camera.status === "offline");
    expect(offline).toHaveLength(1);
  });

  it("records the same nominal local time as different UTC instants across time zones", () => {
    const talwarra = MEDIA.find((item) => item.id === "STN-TALWARRA-CAM1-20250210-0600")!;
    const mirrigan = MEDIA.find((item) => item.id === "STN-MIRRIGAN-CAM1-20250210-0600")!;
    expect(talwarra.capturedAtUtc).not.toBe(mirrigan.capturedAtUtc);
    expect(talwarra.capturedAtUtc).toBe("2025-02-09T20:00:00.000Z");
    expect(mirrigan.capturedAtUtc).toBe("2025-02-09T22:00:00.000Z");
  });
});

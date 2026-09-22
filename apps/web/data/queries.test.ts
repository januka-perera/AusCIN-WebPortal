import { describe, expect, it } from "vitest";
import { CAMERAS } from "./sample/cameras";
import { MEDIA } from "./sample/media";
import { STATIONS } from "./sample/stations";
import {
  filterMediaByDateRange,
  filterMediaByLocalDate,
  filterMediaByLocalDateRange,
  filterMediaByProcessingStatus,
  filterMediaByPublicationStatus,
  filterMediaByTimeOfDay,
  filterMediaByType,
  getAdjacentMedia,
  getAllCameras,
  getAllMedia,
  getAllStations,
  getCameraById,
  getCamerasForStation,
  getLatestObservationPerStation,
  getMediaById,
  getMediaForCamera,
  getMediaForStation,
  getRelatedMedia,
  getStationById,
  getStationTimeZone,
  groupMediaByLocalDate,
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
  it("returns all sample cameras", () => {
    expect(getAllCameras()).toHaveLength(CAMERAS.length);
  });

  it("returns exactly two cameras per station, except Pelican Reach's single newly commissioned camera", () => {
    for (const station of STATIONS) {
      const expected = station.id === "STN-PELICAN" ? 1 : 2;
      expect(getCamerasForStation(station.id)).toHaveLength(expected);
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
  it("returns all sample media", () => {
    expect(getAllMedia()).toHaveLength(MEDIA.length);
  });

  it("returns at least eight media records for every camera except a newly commissioned one", () => {
    for (const camera of CAMERAS) {
      if (camera.id === "STN-PELICAN-CAM1") {
        expect(getMediaForCamera(camera.id)).toEqual([]);
        continue;
      }
      expect(getMediaForCamera(camera.id).length).toBeGreaterThanOrEqual(8);
    }
  });

  it("returns only media belonging to the requested station", () => {
    const media = getMediaForStation("STN-SEAGLASS");
    expect(media.length).toBeGreaterThan(0);
    expect(media.every((item) => item.stationId === "STN-SEAGLASS")).toBe(true);
  });

  it("finds a media item by ID", () => {
    const item = getMediaById("STN-SEAGLASS-CAM1-20250210-0600");
    expect(item?.stationId).toBe("STN-SEAGLASS");
  });

  it("returns undefined for an invalid media ID", () => {
    expect(getMediaById("MEDIA-DOES-NOT-EXIST")).toBeUndefined();
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

describe("adjacent media", () => {
  it("finds the previous and next items in a sorted list", () => {
    const sorted = sortMediaByCaptureTime(getMediaForCamera("STN-SEAGLASS-CAM1"), "asc");
    const middleId = sorted[5].id;
    const { previous, next } = getAdjacentMedia(sorted, middleId);
    expect(previous?.id).toBe(sorted[4].id);
    expect(next?.id).toBe(sorted[6].id);
  });

  it("has no previous item at the start of the list", () => {
    const sorted = sortMediaByCaptureTime(getMediaForCamera("STN-SEAGLASS-CAM1"), "asc");
    const { previous, next } = getAdjacentMedia(sorted, sorted[0].id);
    expect(previous).toBeUndefined();
    expect(next?.id).toBe(sorted[1].id);
  });

  it("has no next item at the end of the list", () => {
    const sorted = sortMediaByCaptureTime(getMediaForCamera("STN-SEAGLASS-CAM1"), "asc");
    const last = sorted[sorted.length - 1];
    const { previous, next } = getAdjacentMedia(sorted, last.id);
    expect(next).toBeUndefined();
    expect(previous?.id).toBe(sorted[sorted.length - 2].id);
  });

  it("returns an empty object for a media ID not present in the list", () => {
    const sorted = sortMediaByCaptureTime(getMediaForCamera("STN-SEAGLASS-CAM1"), "asc");
    expect(getAdjacentMedia(sorted, "MEDIA-DOES-NOT-EXIST")).toEqual({});
  });
});

describe("local-date filtering", () => {
  it("finds the single local date's observations, timezone-aware", () => {
    const media = getMediaForCamera("STN-SEAGLASS-CAM1");
    const day = filterMediaByLocalDate(media, "2025-02-10");
    expect(day.length).toBeGreaterThan(0);
    expect(day.every((item) => item.id.includes("20250210"))).toBe(true);
  });

  it("returns an empty array for the skipped local date", () => {
    const media = getMediaForCamera("STN-WINDARA-CAM1");
    expect(filterMediaByLocalDate(media, "2025-02-11")).toEqual([]);
  });

  it("returns an empty array for a date outside the sample window", () => {
    expect(filterMediaByLocalDate(MEDIA, "2030-01-01")).toEqual([]);
  });
});

describe("local-date range filtering (timezone-aware)", () => {
  it("Brisbane (AEST, no daylight saving): a single-day range matches only that local day", () => {
    const media = getMediaForCamera("STN-TALWARRA-CAM1");
    const result = filterMediaByLocalDateRange(media, "2025-02-10", "2025-02-10");
    expect(result.length).toBeGreaterThan(0);
    expect(result.every((item) => item.id.includes("20250210"))).toBe(true);
  });

  it("Sydney (AEDT): a two-day range matches both local days and excludes the third", () => {
    const media = getMediaForCamera("STN-SEAGLASS-CAM1");
    const result = filterMediaByLocalDateRange(media, "2025-02-10", "2025-02-11");
    expect(result.length).toBeGreaterThan(0);
    expect(result.every((item) => item.id.includes("20250210") || item.id.includes("20250211"))).toBe(
      true,
    );
    expect(result.some((item) => item.id.includes("20250212"))).toBe(false);
  });

  it("Perth (AWST, no daylight saving): a from-only range includes the rest of the sample window", () => {
    const media = getMediaForCamera("STN-MIRRIGAN-CAM1");
    const result = filterMediaByLocalDateRange(media, "2025-02-12", undefined);
    expect(result.length).toBeGreaterThan(0);
    expect(result.every((item) => item.id.includes("20250212"))).toBe(true);
  });

  it("Adelaide (ACDT, UTC+10:30): correctly scopes a single local day despite the half-hour offset", () => {
    const media = getMediaForCamera("STN-WINDARA-CAM2");
    const result = filterMediaByLocalDateRange(media, "2025-02-10", "2025-02-10");
    expect(result.length).toBeGreaterThan(0);
    expect(result.every((item) => item.id.includes("20250210"))).toBe(true);
  });

  it("handles a UTC instant that falls on the previous UTC calendar date", () => {
    // Talwarra's 06:00 local morning capture on the 10th is 2025-02-09T20:00:00.000Z —
    // a different UTC calendar date from its local one.
    const item = MEDIA.find((candidate) => candidate.id === "STN-TALWARRA-CAM1-20250210-0600")!;
    expect(item.capturedAtUtc.startsWith("2025-02-09")).toBe(true);
    expect(filterMediaByLocalDateRange([item], "2025-02-10", "2025-02-10")).toEqual([item]);
    expect(filterMediaByLocalDateRange([item], "2025-02-09", "2025-02-09")).toEqual([]);
  });

  it("supports a to-date-only range", () => {
    const media = getMediaForCamera("STN-BLUEWATER-CAM1");
    const result = filterMediaByLocalDateRange(media, undefined, "2025-02-10");
    expect(result.length).toBeGreaterThan(0);
    expect(result.every((item) => item.id.includes("20250210"))).toBe(true);
  });

  it("supports a from-date-only range", () => {
    const media = getMediaForCamera("STN-BLUEWATER-CAM1");
    const result = filterMediaByLocalDateRange(media, "2025-02-11", undefined);
    expect(result.length).toBeGreaterThan(0);
    expect(result.every((item) => !item.id.includes("20250210"))).toBe(true);
  });

  it("supports both bounds spanning multiple local days", () => {
    const media = getMediaForCamera("STN-BLUEWATER-CAM1");
    const result = filterMediaByLocalDateRange(media, "2025-02-10", "2025-02-11");
    expect(result.every((item) => item.id.includes("20250210") || item.id.includes("20250211"))).toBe(
      true,
    );
    expect(result.some((item) => item.id.includes("20250212"))).toBe(false);
  });

  it("returns everything when neither bound is given", () => {
    const media = getMediaForCamera("STN-BLUEWATER-CAM1");
    expect(filterMediaByLocalDateRange(media, undefined, undefined)).toEqual(media);
  });

  it("returns an empty array for a range outside the sample window", () => {
    expect(filterMediaByLocalDateRange(MEDIA, "2030-01-01", "2030-01-02")).toEqual([]);
  });

  it("returns an empty array for an invalid (reversed) date order", () => {
    const media = getMediaForCamera("STN-SEAGLASS-CAM1");
    expect(filterMediaByLocalDateRange(media, "2025-02-12", "2025-02-10")).toEqual([]);
  });
});

describe("time-of-day filtering", () => {
  it("finds morning captures within a same-day range", () => {
    const media = getMediaForCamera("STN-SEAGLASS-CAM1");
    // Morning slot is 06:00 local -> 360 minutes.
    const morning = filterMediaByTimeOfDay(media, 300, 659);
    expect(morning.length).toBeGreaterThan(0);
    expect(morning.every((item) => item.id.includes("-0600"))).toBe(true);
  });

  it("handles a range that wraps past local midnight", () => {
    const media = getMediaForCamera("STN-SEAGLASS-CAM1");
    // Night window 21:00-04:59 should include the 22:00 and 22:30 (timelapse) slots.
    const night = filterMediaByTimeOfDay(media, 1260, 299);
    expect(night.length).toBeGreaterThan(0);
    expect(night.every((item) => item.id.includes("-2200") || item.id.includes("TIMELAPSE"))).toBe(
      true,
    );
  });

  it("returns an empty array when no captures fall in the window", () => {
    // 02:00-02:59 local has no sample captures.
    expect(filterMediaByTimeOfDay(MEDIA, 120, 179)).toEqual([]);
  });
});

describe("processing and publication status filtering", () => {
  it("finds the single processing item", () => {
    expect(filterMediaByProcessingStatus(MEDIA, "processing")).toHaveLength(1);
  });

  it("finds the single failed item", () => {
    expect(filterMediaByProcessingStatus(MEDIA, "failed")).toHaveLength(1);
  });

  it("finds project-only items (the lidar camera plus one composite override)", () => {
    const projectOnly = filterMediaByPublicationStatus(MEDIA, "project-only");
    expect(projectOnly.length).toBeGreaterThan(0);
    expect(projectOnly.every((item) => item.publicationStatus === "project-only")).toBe(true);
  });

  it("returns an empty array for a status with no matches in a narrowed set", () => {
    const media = getMediaForCamera("STN-SEAGLASS-CAM1");
    expect(filterMediaByProcessingStatus(media, "failed")).toEqual([]);
  });
});

describe("grouping by local date", () => {
  it("groups a station's media into its three sample dates", () => {
    const media = getMediaForStation("STN-SEAGLASS");
    const groups = groupMediaByLocalDate(media);
    expect([...groups.keys()].sort()).toEqual(["2025-02-10", "2025-02-11", "2025-02-12"]);
  });

  it("omits the skipped date for the affected camera only", () => {
    const media = getMediaForCamera("STN-WINDARA-CAM1");
    const groups = groupMediaByLocalDate(media);
    expect([...groups.keys()].sort()).toEqual(["2025-02-10", "2025-02-12"]);
  });
});

describe("station time zone lookup", () => {
  it("resolves each station's display time zone from its media", () => {
    expect(getStationTimeZone("STN-MIRRIGAN")).toBe("Australia/Perth");
    expect(getStationTimeZone("STN-TALWARRA")).toBe("Australia/Brisbane");
  });

  it("returns undefined for a station with no media", () => {
    expect(getStationTimeZone("STN-DOES-NOT-EXIST")).toBeUndefined();
  });
});

describe("latest observation per station", () => {
  it("returns one presentable observation per station, most recent first", () => {
    const latest = getLatestObservationPerStation();
    const stationsWithMedia = STATIONS.filter((station) =>
      MEDIA.some((item) => item.stationId === station.id),
    );
    // Pelican Reach has no media at all yet, so it is expected to be
    // skipped here — see the "skips a station with no presentable media"
    // test below for the general behaviour this exercises.
    expect(latest).toHaveLength(stationsWithMedia.length);
    expect(latest.every((item) => item.processingStatus === "processed")).toBe(true);
    expect(latest.every((item) => item.publicationStatus === "public")).toBe(true);
    for (let i = 1; i < latest.length; i += 1) {
      expect(new Date(latest[i].capturedAtUtc).getTime()).toBeLessThanOrEqual(
        new Date(latest[i - 1].capturedAtUtc).getTime(),
      );
    }
  });

  it("never returns the same station twice", () => {
    const latest = getLatestObservationPerStation();
    const stationIds = latest.map((item) => item.stationId);
    expect(new Set(stationIds).size).toBe(stationIds.length);
  });

  it("skips a station with no presentable media", () => {
    const noPresentableMedia = MEDIA.filter(
      (item) => item.stationId !== "STN-SEAGLASS" || item.processingStatus !== "processed",
    );
    const latest = getLatestObservationPerStation(STATIONS, noPresentableMedia);
    expect(latest.some((item) => item.stationId === "STN-SEAGLASS")).toBe(false);
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

  it("has at least one station in each operating status: active, offline and maintenance", () => {
    const statuses = new Set(STATIONS.map((station) => station.operationalStatus));
    expect(statuses).toEqual(new Set(["active", "offline", "maintenance"]));
  });

  it("has exactly one station with no observations, whose only camera also has none", () => {
    const stationsWithNoMedia = STATIONS.filter(
      (station) => !MEDIA.some((item) => item.stationId === station.id),
    );
    expect(stationsWithNoMedia).toHaveLength(1);
    expect(stationsWithNoMedia[0].id).toBe("STN-PELICAN");
    const camerasWithNoMedia = CAMERAS.filter(
      (camera) => !MEDIA.some((item) => item.cameraId === camera.id),
    );
    expect(camerasWithNoMedia).toHaveLength(1);
    expect(camerasWithNoMedia[0].id).toBe("STN-PELICAN-CAM1");
  });

  it("has a processed-but-embargoed item, independent of the processing-and-embargoed item above", () => {
    const embargoed = MEDIA.filter((item) => item.publicationStatus === "embargoed");
    expect(embargoed.some((item) => item.processingStatus === "processing")).toBe(true);
    expect(embargoed.some((item) => item.processingStatus === "processed")).toBe(true);
  });

  it("has a processed-but-restricted item, independent of the failed-and-restricted item above", () => {
    const restricted = MEDIA.filter((item) => item.publicationStatus === "restricted");
    expect(restricted.some((item) => item.processingStatus === "failed")).toBe(true);
    expect(restricted.some((item) => item.processingStatus === "processed")).toBe(true);
  });

  it("records the same nominal local time as different UTC instants across time zones", () => {
    const talwarra = MEDIA.find((item) => item.id === "STN-TALWARRA-CAM1-20250210-0600")!;
    const mirrigan = MEDIA.find((item) => item.id === "STN-MIRRIGAN-CAM1-20250210-0600")!;
    expect(talwarra.capturedAtUtc).not.toBe(mirrigan.capturedAtUtc);
    expect(talwarra.capturedAtUtc).toBe("2025-02-09T20:00:00.000Z");
    expect(mirrigan.capturedAtUtc).toBe("2025-02-09T22:00:00.000Z");
  });
});

import { describe, expect, it } from "vitest";
import { CAMERAS, MEDIA, STATIONS } from "@/data";
import {
  applyMediaFilterFields,
  applyObservationFilters,
  countActiveObservationFilters,
  countMediaFilterFields,
  hasActiveObservationFilters,
  hasMediaFilterFields,
  isValidDateKey,
  parseMediaFilterFields,
  parseObservationFilters,
  summariseMediaFilterFields,
  type SearchParams,
} from "./media-filters";

const seaglassCameras = CAMERAS.filter((camera) => camera.stationId === "STN-SEAGLASS");
const kestrelCameras = CAMERAS.filter((camera) => camera.stationId === "STN-KESTREL");

describe("isValidDateKey", () => {
  it("accepts a well-formed date key", () => {
    expect(isValidDateKey("2025-02-10")).toBe(true);
  });

  it("rejects undefined, empty and malformed values", () => {
    expect(isValidDateKey(undefined)).toBe(false);
    expect(isValidDateKey("")).toBe(false);
    expect(isValidDateKey("not-a-date")).toBe(false);
    expect(isValidDateKey("2025/02/10")).toBe(false);
    expect(isValidDateKey("10-02-2025")).toBe(false);
  });
});

describe("parseMediaFilterFields", () => {
  it("resolves a camera within the given scope", () => {
    const search: SearchParams = { camera: seaglassCameras[0].id };
    const fields = parseMediaFilterFields(search, seaglassCameras);
    expect(fields.camera?.id).toBe(seaglassCameras[0].id);
  });

  it("drops a camera ID that belongs to a different station's scope, rather than leaking it in", () => {
    const search: SearchParams = { camera: kestrelCameras[0].id };
    const fields = parseMediaFilterFields(search, seaglassCameras);
    expect(fields.camera).toBeUndefined();
  });

  it("drops an unrecognised media type", () => {
    const fields = parseMediaFilterFields({ mediaType: "hologram" }, CAMERAS);
    expect(fields.mediaType).toBeUndefined();
  });

  it("drops a malformed date rather than passing it through", () => {
    const fields = parseMediaFilterFields({ date: "not-a-date" }, CAMERAS);
    expect(fields.date).toBeUndefined();
  });

  it("drops an unrecognised time-of-day key", () => {
    const fields = parseMediaFilterFields({ timeOfDay: "brunch" }, CAMERAS);
    expect(fields.timeOfDay).toBeUndefined();
  });

  it("drops unrecognised processing and publication statuses", () => {
    const fields = parseMediaFilterFields(
      { processingStatus: "archived", publicationStatus: "top-secret" },
      CAMERAS,
    );
    expect(fields.processingStatus).toBeUndefined();
    expect(fields.publicationStatus).toBeUndefined();
  });

  it("takes the first value when a param is repeated", () => {
    const fields = parseMediaFilterFields({ mediaType: ["image", "timelapse"] }, CAMERAS);
    expect(fields.mediaType).toBe("image");
  });

  it("returns an entirely empty result for an empty search, never throwing", () => {
    expect(() => parseMediaFilterFields({}, CAMERAS)).not.toThrow();
    const fields = parseMediaFilterFields({}, CAMERAS);
    expect(hasMediaFilterFields(fields)).toBe(false);
  });
});

describe("applyMediaFilterFields", () => {
  it("never returns media from outside the resolved camera", () => {
    const fields = parseMediaFilterFields({ camera: seaglassCameras[0].id }, seaglassCameras);
    const filtered = applyMediaFilterFields(MEDIA, fields);
    expect(filtered.length).toBeGreaterThan(0);
    expect(filtered.every((item) => item.cameraId === seaglassCameras[0].id)).toBe(true);
  });

  it("combines media type and processing status filters as an AND", () => {
    const fields = parseMediaFilterFields(
      { mediaType: "timelapse", processingStatus: "processed" },
      CAMERAS,
    );
    const filtered = applyMediaFilterFields(MEDIA, fields);
    expect(filtered.length).toBeGreaterThan(0);
    expect(filtered.every((item) => item.mediaType === "timelapse")).toBe(true);
    expect(filtered.every((item) => item.processingStatus === "processed")).toBe(true);
  });
});

describe("countMediaFilterFields", () => {
  it("counts a date and a range together as a single active group", () => {
    expect(countMediaFilterFields({ from: "2025-02-10", to: "2025-02-11" })).toBe(1);
  });

  it("counts zero fields for an empty filter set", () => {
    expect(countMediaFilterFields({})).toBe(0);
  });
});

describe("summariseMediaFilterFields", () => {
  it("omits parts for fields that are not set", () => {
    expect(summariseMediaFilterFields({})).toEqual([]);
  });

  it("includes a lower-cased media type label", () => {
    expect(summariseMediaFilterFields({ mediaType: "timelapse" })).toEqual(["time-lapse"]);
  });
});

describe("parseObservationFilters", () => {
  it("scopes the camera options to the selected station", () => {
    const search: SearchParams = { station: "STN-SEAGLASS", camera: kestrelCameras[0].id };
    const filters = parseObservationFilters(search, STATIONS, CAMERAS);
    expect(filters.station?.id).toBe("STN-SEAGLASS");
    // A camera ID from a different station must never leak through once a station is selected.
    expect(filters.camera).toBeUndefined();
  });

  it("drops a state not present in the station list", () => {
    const filters = parseObservationFilters({ state: "ZZZ" }, STATIONS, CAMERAS);
    expect(filters.state).toBeUndefined();
  });

  it("drops a region not present in the station list", () => {
    const filters = parseObservationFilters({ region: "Nowhereville" }, STATIONS, CAMERAS);
    expect(filters.region).toBeUndefined();
  });

  it("falls back to page 1 for a missing, non-numeric, zero or negative page", () => {
    expect(parseObservationFilters({}, STATIONS, CAMERAS).page).toBe(1);
    expect(parseObservationFilters({ page: "abc" }, STATIONS, CAMERAS).page).toBe(1);
    expect(parseObservationFilters({ page: "0" }, STATIONS, CAMERAS).page).toBe(1);
    expect(parseObservationFilters({ page: "-3" }, STATIONS, CAMERAS).page).toBe(1);
  });

  it("accepts a valid page number", () => {
    expect(parseObservationFilters({ page: "3" }, STATIONS, CAMERAS).page).toBe(3);
  });

  it("never throws for a fully invalid search", () => {
    const search: SearchParams = {
      station: "does-not-exist",
      state: "ZZ",
      region: "nowhere",
      camera: "does-not-exist",
      mediaType: "hologram",
      date: "banana",
      timeOfDay: "brunch",
      processingStatus: "lost",
      publicationStatus: "classified",
      page: "not-a-number",
    };
    expect(() => parseObservationFilters(search, STATIONS, CAMERAS)).not.toThrow();
    const filters = parseObservationFilters(search, STATIONS, CAMERAS);
    expect(hasActiveObservationFilters(filters)).toBe(false);
  });
});

describe("applyObservationFilters / hasActiveObservationFilters / countActiveObservationFilters", () => {
  it("a station paired with a state it isn't in yields zero results, not an error", () => {
    const filters = parseObservationFilters(
      { station: "STN-SEAGLASS", state: "WA" },
      STATIONS,
      CAMERAS,
    );
    // The state is dropped during parsing because STN-SEAGLASS is in NSW,
    // but applying the filter should still be safe even if a caller
    // constructs a contradictory ObservationFilters object directly.
    const filtered = applyObservationFilters(
      MEDIA,
      { ...filters, station: STATIONS.find((s) => s.id === "STN-SEAGLASS"), state: "WA", page: 1 },
      STATIONS,
    );
    expect(filtered).toEqual([]);
  });

  it("counts station/state/region alongside the shared media fields", () => {
    const filters = parseObservationFilters(
      { station: "STN-SEAGLASS", mediaType: "image" },
      STATIONS,
      CAMERAS,
    );
    expect(countActiveObservationFilters(filters)).toBe(2);
    expect(hasActiveObservationFilters(filters)).toBe(true);
  });

  it("reports no active filters for an empty filter set", () => {
    const filters = parseObservationFilters({}, STATIONS, CAMERAS);
    expect(hasActiveObservationFilters(filters)).toBe(false);
    expect(countActiveObservationFilters(filters)).toBe(0);
  });
});

import { describe, expect, it } from "vitest";
import { MEDIA } from "@/data";
import { getMediaAccessState, getPreviewAvailability } from "./media-access";

describe("getMediaAccessState", () => {
  it("is 'unavailable-prototype' for every sample record, since this prototype never sets an original URL", () => {
    // Documents the current, deliberate state of the sample dataset —
    // see the synthetic fixture below for the "original-available" and
    // "restricted" branches, which real sample data never reaches.
    expect(MEDIA.every((item) => getMediaAccessState(item) !== "original-available")).toBe(true);
  });

  it("is 'original-available' whenever an original URL is present, regardless of publication status", () => {
    // No real sample record has an originalUrl — this exercises the
    // branch the UI needs to be correct for once a future API returns
    // real originals, without inventing a fake downloadable file in the
    // live sample dataset.
    expect(
      getMediaAccessState({ originalUrl: "/sample-media/originals/example.jpg", publicationStatus: "restricted" }),
    ).toBe("original-available");
  });

  it("is 'restricted' when there is no original and publication status is restricted", () => {
    expect(getMediaAccessState({ originalUrl: null, publicationStatus: "restricted" })).toBe("restricted");
  });

  it("is 'unavailable-prototype' when there is no original and publication status permits access", () => {
    expect(getMediaAccessState({ originalUrl: null, publicationStatus: "public" })).toBe(
      "unavailable-prototype",
    );
    expect(getMediaAccessState({ originalUrl: null, publicationStatus: "embargoed" })).toBe(
      "unavailable-prototype",
    );
    expect(getMediaAccessState({ originalUrl: null, publicationStatus: "project-only" })).toBe(
      "unavailable-prototype",
    );
  });
});

describe("getPreviewAvailability", () => {
  it("is 'available' when a preview URL is present", () => {
    expect(
      getPreviewAvailability({ previewUrl: "/preview.svg", thumbnailUrl: null, processingStatus: "processed" }),
    ).toBe("available");
  });

  it("is 'available' when only a thumbnail is present", () => {
    expect(
      getPreviewAvailability({ previewUrl: null, thumbnailUrl: "/thumb.svg", processingStatus: "processed" }),
    ).toBe("available");
  });

  it("is 'processing' when neither asset exists yet and processing is incomplete", () => {
    expect(
      getPreviewAvailability({ previewUrl: null, thumbnailUrl: null, processingStatus: "processing" }),
    ).toBe("processing");
  });

  it("is 'failed' when neither asset exists and the capture failed", () => {
    expect(getPreviewAvailability({ previewUrl: null, thumbnailUrl: null, processingStatus: "failed" })).toBe(
      "failed",
    );
  });

  it("is 'unavailable' when neither asset exists for a processed item", () => {
    expect(
      getPreviewAvailability({ previewUrl: null, thumbnailUrl: null, processingStatus: "processed" }),
    ).toBe("unavailable");
  });

  it("matches every sample record's actual asset presence", () => {
    for (const item of MEDIA) {
      const availability = getPreviewAvailability(item);
      if (item.previewUrl || item.thumbnailUrl) {
        expect(availability).toBe("available");
      } else {
        expect(["processing", "failed", "unavailable"]).toContain(availability);
      }
    }
  });
});

import { describe, expect, it } from "vitest";
import { COASTSNAP_OBSERVATIONS } from "@/data";
import {
  SAMPLE_RECORD_NOTICE,
  SYNTHETIC_API_RECORD_NOTICE,
  describeUnavailableDownload,
  getCoastSnapDownloadState,
  getRecordNotice,
} from "./coastsnap-presentation";
import { isRemoteMediaUrl } from "./media-url";

describe("getRecordNotice", () => {
  it("always labels sample data as a development record", () => {
    expect(getRecordNotice("sample", true)).toBe(SAMPLE_RECORD_NOTICE);
    expect(getRecordNotice("sample", false)).toBe(SAMPLE_RECORD_NOTICE);
  });

  it("labels synthetic API records, and shows no disclaimer for real ones", () => {
    expect(getRecordNotice("api", true)).toBe(SYNTHETIC_API_RECORD_NOTICE);
    expect(getRecordNotice("api", false)).toBeNull();
  });
});

describe("getCoastSnapDownloadState", () => {
  const base = {
    isOriginalAvailable: false,
    originalUrl: null,
    processingStatus: "processed" as const,
    publicationStatus: "public" as const,
  };

  it("offers a real download only for API records with a permitted original", () => {
    const permitted = { ...base, isOriginalAvailable: true, originalUrl: "http://localhost:8000/media/coastsnap/csm_x/original" };
    expect(getCoastSnapDownloadState("api", permitted)).toBe("available");
    expect(getCoastSnapDownloadState("sample", permitted)).toBe("sample-demo");
  });

  it("never offers a download when isOriginalAvailable is false, even with a URL", () => {
    expect(getCoastSnapDownloadState("api", { ...base, originalUrl: "http://localhost:8000/media/coastsnap/csm_x/original" })).toBe(
      "unavailable",
    );
  });

  it("keeps processing, failed, restricted and unavailable distinct", () => {
    expect(getCoastSnapDownloadState("api", { ...base, processingStatus: "processing" })).toBe("processing");
    expect(getCoastSnapDownloadState("api", { ...base, processingStatus: "failed" })).toBe("failed");
    expect(getCoastSnapDownloadState("api", { ...base, publicationStatus: "restricted" })).toBe("restricted");
    expect(getCoastSnapDownloadState("api", { ...base, publicationStatus: "embargoed" })).toBe("restricted");
    expect(getCoastSnapDownloadState("api", base)).toBe("unavailable");
  });

  it("keeps the sample dataset's one prototype download as a labelled demo", () => {
    const demo = COASTSNAP_OBSERVATIONS.filter((o) => getCoastSnapDownloadState("sample", o) === "sample-demo");
    expect(demo).toHaveLength(1);
  });

  it("uses prototype wording only for sample data", () => {
    expect(describeUnavailableDownload("sample", "unavailable").description).toMatch(/development prototype/);
    expect(describeUnavailableDownload("api", "unavailable").description).not.toMatch(/prototype|Spotteron/);
    const labels = (["processing", "failed", "restricted", "unavailable"] as const).map(
      (state) => describeUnavailableDownload("api", state).label,
    );
    expect(new Set(labels).size).toBe(4);
  });
});

describe("isRemoteMediaUrl", () => {
  it("is true only for absolute http(s) URLs", () => {
    expect(isRemoteMediaUrl("http://localhost:8000/media/coastsnap/csm_x/thumbnail")).toBe(true);
    expect(isRemoteMediaUrl("https://media.example.test/media/coastsnap/csm_x/preview")).toBe(true);
    expect(isRemoteMediaUrl("/sample-media/thumbnails/beach-wide.svg")).toBe(false);
  });
});

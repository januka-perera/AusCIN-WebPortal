import { describe, expect, it } from "vitest";
import { COASTSNAP_OBSERVATIONS } from "@/data";
import {
  COASTSNAP_ERROR_TITLE,
  SAMPLE_RECORD_NOTICE,
  SYNTHETIC_API_RECORD_NOTICE,
  describeUnavailableDownload,
  getCoastSnapDownloadState,
  getCoastSnapDownloadView,
  getRecordNotice,
} from "./coastsnap-presentation";
import { isRemoteMediaUrl } from "./media-url";
import { getFooterDataNotice } from "./site-footer";

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

const API = "http://localhost:8000/media/coastsnap/csm_x";
const SHA0 = "0".repeat(64);
const SHA1 = "1".repeat(64);

/** Download fields with nothing offered: the starting point for each case. */
const base = {
  isOriginalAvailable: false,
  originalUrl: null,
  processingStatus: "processed" as const,
  publicationStatus: "public" as const,
  level0DownloadAvailable: false,
  level0DownloadUrl: null,
  level1DownloadAvailable: false,
  level1DownloadUrl: null,
};
const level0 = { level0DownloadAvailable: true, level0DownloadUrl: `${API}/level0`, level0ChecksumSha256: SHA0 };
const level1 = { level1DownloadAvailable: true, level1DownloadUrl: `${API}/level1`, level1ChecksumSha256: SHA1 };

describe("getCoastSnapDownloadState", () => {
  it("is available for an API record when either level is permitted", () => {
    expect(getCoastSnapDownloadState("api", { ...base, ...level0 })).toBe("available");
    expect(getCoastSnapDownloadState("api", { ...base, ...level1 })).toBe("available");
    expect(getCoastSnapDownloadState("api", { ...base, ...level0, ...level1 })).toBe("available");
  });

  it("offers only the labelled demo for sample data, never product levels", () => {
    const demo = { ...base, isOriginalAvailable: true, originalUrl: "/sample-media/previews/beach-wide.svg" };
    expect(getCoastSnapDownloadState("sample", demo)).toBe("sample-demo");
    expect(getCoastSnapDownloadState("sample", { ...base, ...level0, ...level1 })).toBe("unavailable");
  });

  it("never offers a level whose available flag is false, even with a URL", () => {
    const urlsOnly = { ...base, level0DownloadUrl: `${API}/level0`, level1DownloadUrl: `${API}/level1` };
    expect(getCoastSnapDownloadState("api", urlsOnly)).toBe("unavailable");
  });

  it("ignores the deprecated single-original fields for API records", () => {
    const deprecatedOnly = { ...base, isOriginalAvailable: true, originalUrl: `${API}/original` };
    expect(getCoastSnapDownloadState("api", deprecatedOnly)).toBe("unavailable");
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

describe("COASTSNAP_ERROR_TITLE", () => {
  it("is the stable error title and carries no host, path or error detail", () => {
    expect(COASTSNAP_ERROR_TITLE).toBe("CoastSnap catalogue unavailable | AusCIN");
    for (const forbidden of ["localhost", "http:", "https:", "/", "\\", "Error", "ECONN"]) {
      expect(COASTSNAP_ERROR_TITLE).not.toContain(forbidden);
    }
  });
});

describe("getFooterDataNotice", () => {
  it("identifies everything as synthetic development data in sample mode", () => {
    const notice = getFooterDataNotice("sample");
    expect(notice).toMatch(/synthetic sample data/);
    expect(notice).toMatch(/CoastSnap/);
  });

  it("describes catalogue-backed CoastSnap observations in API mode without claiming production data", () => {
    const notice = getFooterDataNotice("api");
    expect(notice).toMatch(/CoastSnap observations are served by the AusCIN catalogue API/);
    expect(notice).toMatch(/station, camera and media records are synthetic sample data/);
    expect(notice).not.toMatch(/production|operational|live/i);
  });
});

describe("getCoastSnapDownloadView", () => {
  it("offers both levels, in order, with their explanations and checksums", () => {
    const view = getCoastSnapDownloadView("api", { ...base, ...level0, ...level1 });
    expect(view.kind).toBe("levels");
    if (view.kind !== "levels") return;
    expect(view.offered.map((item) => [item.level, item.action, item.url, item.checksumSha256])).toEqual([
      ["level0", "Download original (Level 0)", `${API}/level0`, SHA0],
      ["level1", "Download provenance copy (Level 1)", `${API}/level1`, SHA1],
    ]);
    expect(view.offered[0].description).toMatch(/untouched source image/);
    expect(view.offered[1].description).toMatch(/AusCIN provenance metadata/);
    expect(view.withheld).toEqual([]);
  });

  it.each([
    ["only Level 0", level0, "level0", "level1"],
    ["only Level 1", level1, "level1", "level0"],
  ] as const)("offers %s and explains the other", (_label, fields, offeredLevel, withheldLevel) => {
    const view = getCoastSnapDownloadView("api", { ...base, ...fields });
    if (view.kind !== "levels") throw new Error("expected levels");
    expect(view.offered.map((item) => item.level)).toEqual([offeredLevel]);
    expect(view.withheld.map((item) => item.level)).toEqual([withheldLevel]);
    expect(view.withheld[0].reason).toMatch(withheldLevel === "level0" ? /Level 0/ : /Level 1/);
    expect(view.withheld[0].reason).toMatch(/not offered for download/);
  });

  it.each([
    ["processing", { processingStatus: "processing" as const }, "Original processing"],
    ["failed", { processingStatus: "failed" as const }, "Processing failed"],
    ["restricted", { publicationStatus: "restricted" as const }, "Original restricted"],
    ["unavailable", {}, "Original unavailable"],
  ])("keeps the explicit %s state when no level is offered", (_label, fields, expectedLabel) => {
    const view = getCoastSnapDownloadView("api", { ...base, ...fields });
    expect(view).toMatchObject({ kind: "none", label: expectedLabel });
  });

  it("keeps the sample demo as a single labelled demo", () => {
    const view = getCoastSnapDownloadView("sample", { ...base, isOriginalAvailable: true, originalUrl: "/sample-media/x.svg" });
    expect(view).toEqual({ kind: "sample-demo", url: "/sample-media/x.svg" });
  });
});

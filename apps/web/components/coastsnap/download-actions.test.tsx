import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { CoastSnapObservation } from "@/data";
import { getCoastSnapDownloadView } from "@/lib/coastsnap-presentation";
import { CoastSnapDownloadActions } from "./download-actions";

/**
 * Renders the detail page's data-access actions to static HTML, the same
 * server-rendered markup visitors receive, for each download policy.
 */

const API = "http://localhost:8000/media/coastsnap/csm_5cea933ee069d94a0cd93aaa";
const SHA0 = "a".repeat(64);
const SHA1 = "b".repeat(64);

type Fields = Parameters<typeof getCoastSnapDownloadView>[1];

const none: Fields = {
  isOriginalAvailable: false,
  originalUrl: null,
  processingStatus: "processed",
  publicationStatus: "public",
  level0DownloadAvailable: false,
  level0DownloadUrl: null,
  level1DownloadAvailable: false,
  level1DownloadUrl: null,
};
const withLevel0: Partial<CoastSnapObservation> = {
  level0DownloadAvailable: true,
  level0DownloadUrl: `${API}/level0`,
  level0ChecksumSha256: SHA0,
};
const withLevel1: Partial<CoastSnapObservation> = {
  level1DownloadAvailable: true,
  level1DownloadUrl: `${API}/level1`,
  level1ChecksumSha256: SHA1,
};

function render(fields: Partial<Fields>, source: "api" | "sample" = "api"): string {
  return renderToStaticMarkup(<CoastSnapDownloadActions view={getCoastSnapDownloadView(source, { ...none, ...fields })} />);
}

function hrefs(html: string): string[] {
  return [...html.matchAll(/<a [^>]*href="([^"]+)"/g)].map((match) => match[1]);
}

describe("CoastSnapDownloadActions", () => {
  it("renders both buttons when both levels are permitted", () => {
    const html = render({ ...withLevel0, ...withLevel1 });
    expect(html).toContain("Download original (Level 0)");
    expect(html).toContain("Download provenance copy (Level 1)");
    expect(hrefs(html)).toEqual([`${API}/level0`, `${API}/level1`]);
    expect(html).toContain("untouched source image");
    expect(html).toContain("AusCIN provenance metadata");
    expect(html).toContain(SHA0);
    expect(html).toContain(SHA1);
    expect(html).not.toContain("not offered for download");
  });

  it("renders only the Level 0 button, and explains Level 1, when only Level 0 is permitted", () => {
    const html = render(withLevel0);
    expect(hrefs(html)).toEqual([`${API}/level0`]);
    expect(html).toContain("Download original (Level 0)");
    expect(html).not.toContain("Download provenance copy (Level 1)");
    expect(html).toContain("Level 1 (provenance copy) is not offered for download");
    expect(html).not.toContain(SHA1);
  });

  it("renders only the Level 1 button, and explains Level 0, when only Level 1 is permitted", () => {
    const html = render(withLevel1);
    expect(hrefs(html)).toEqual([`${API}/level1`]);
    expect(html).toContain("Download provenance copy (Level 1)");
    expect(html).not.toContain("Download original (Level 0)");
    expect(html).toContain("Level 0 (untouched source image) is not offered for download");
  });

  it("renders no download link and keeps the explicit state when nothing is permitted", () => {
    expect(hrefs(render({}))).toEqual([]);
    expect(render({})).toContain("Original unavailable");
    expect(render({ processingStatus: "processing" })).toContain("Original processing");
    expect(render({ processingStatus: "failed" })).toContain("Processing failed");
    expect(render({ publicationStatus: "restricted" })).toContain("Original restricted");
  });

  it("uses plain anchors to the API origin for downloads, never client-side routing or a Next.js path", () => {
    const html = render({ ...withLevel0, ...withLevel1 });
    for (const href of hrefs(html)) {
      expect(href.startsWith("http://localhost:8000/media/coastsnap/")).toBe(true);
    }
  });

  it("never renders the deprecated /original URL for API records", () => {
    const html = render({ ...withLevel1, isOriginalAvailable: true, originalUrl: `${API}/original` });
    expect(html).not.toContain("/original");
  });

  it("keeps the sample prototype demo wording for sample data only", () => {
    const html = render({ isOriginalAvailable: true, originalUrl: "/sample-media/previews/beach-wide.svg" }, "sample");
    expect(html).toContain("Download original (prototype demo)");
    expect(html).not.toContain("Level 0");
    expect(render({ ...withLevel0, ...withLevel1 })).not.toContain("prototype");
  });

  it("contains no filesystem paths or internal identifiers", () => {
    const html = render({ ...withLevel0, ...withLevel1 });
    for (const forbidden of ["/g/data", "level-0", "level-1", "TEST_OBS", "root-", "staging"]) {
      expect(html).not.toContain(forbidden);
    }
  });
});

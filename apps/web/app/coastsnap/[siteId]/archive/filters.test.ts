import { describe, expect, it } from "vitest";
import {
  buildArchiveHref,
  countActiveFilters,
  filtersToParamState,
  hasActiveFilters,
  parseCoastSnapArchiveFilters,
  summariseFilters,
  type SearchParams,
} from "./filters";

describe("parseCoastSnapArchiveFilters", () => {
  it("parses a valid media type", () => {
    expect(parseCoastSnapArchiveFilters({ mediaType: "composite" }).mediaType).toBe("composite");
  });

  it("drops an unrecognised media type", () => {
    expect(parseCoastSnapArchiveFilters({ mediaType: "hologram" }).mediaType).toBeUndefined();
  });

  it("parses a well-formed date", () => {
    expect(parseCoastSnapArchiveFilters({ date: "2026-08-01" }).date).toBe("2026-08-01");
  });

  it("drops a malformed date rather than passing it through", () => {
    expect(parseCoastSnapArchiveFilters({ date: "not-a-date" }).date).toBeUndefined();
    expect(parseCoastSnapArchiveFilters({ date: "2026/08/01" }).date).toBeUndefined();
    expect(parseCoastSnapArchiveFilters({ date: "" }).date).toBeUndefined();
  });

  it("parses a well-formed from/to range", () => {
    const filters = parseCoastSnapArchiveFilters({ from: "2026-08-01", to: "2026-08-10" });
    expect(filters.from).toBe("2026-08-01");
    expect(filters.to).toBe("2026-08-10");
  });

  it("drops a malformed from or to value independently", () => {
    const filters = parseCoastSnapArchiveFilters({ from: "bad", to: "2026-08-10" });
    expect(filters.from).toBeUndefined();
    expect(filters.to).toBe("2026-08-10");
  });

  it("defaults to page 1 for a missing, non-numeric, zero or negative page", () => {
    expect(parseCoastSnapArchiveFilters({}).page).toBe(1);
    expect(parseCoastSnapArchiveFilters({ page: "abc" }).page).toBe(1);
    expect(parseCoastSnapArchiveFilters({ page: "0" }).page).toBe(1);
    expect(parseCoastSnapArchiveFilters({ page: "-2" }).page).toBe(1);
  });

  it("accepts a valid page number", () => {
    expect(parseCoastSnapArchiveFilters({ page: "3" }).page).toBe(3);
  });

  it("takes the first value when a param is repeated", () => {
    expect(parseCoastSnapArchiveFilters({ mediaType: ["image", "composite"] }).mediaType).toBe("image");
  });

  it("never throws for a fully invalid search and yields no active filters", () => {
    const search: SearchParams = {
      mediaType: "hologram",
      date: "banana",
      from: "also-banana",
      to: "still-banana",
      page: "not-a-number",
    };
    expect(() => parseCoastSnapArchiveFilters(search)).not.toThrow();
    const filters = parseCoastSnapArchiveFilters(search);
    expect(hasActiveFilters(filters)).toBe(false);
    expect(filters.page).toBe(1);
  });
});

describe("hasActiveFilters / countActiveFilters", () => {
  it("reports no active filters for an empty filter set", () => {
    const filters = parseCoastSnapArchiveFilters({});
    expect(hasActiveFilters(filters)).toBe(false);
    expect(countActiveFilters(filters)).toBe(0);
  });

  it("counts a date and a range together as a single active group", () => {
    const filters = parseCoastSnapArchiveFilters({ from: "2026-08-01", to: "2026-08-10" });
    expect(countActiveFilters(filters)).toBe(1);
  });

  it("counts media type and date independently", () => {
    const filters = parseCoastSnapArchiveFilters({ mediaType: "image", date: "2026-08-01" });
    expect(countActiveFilters(filters)).toBe(2);
    expect(hasActiveFilters(filters)).toBe(true);
  });
});

describe("filtersToParamState / buildArchiveHref (URL filter preservation)", () => {
  it("round-trips a filter set into a URL and omits unset fields", () => {
    const filters = parseCoastSnapArchiveFilters({ mediaType: "composite", from: "2026-08-01" });
    const state = filtersToParamState(filters);
    const href = buildArchiveHref("CS-DRIFTWOOD", state);
    expect(href).toBe("/coastsnap/CS-DRIFTWOOD/archive?mediaType=composite&from=2026-08-01");
  });

  it("builds a bare archive href when no filters are set", () => {
    const filters = parseCoastSnapArchiveFilters({});
    const href = buildArchiveHref("CS-DRIFTWOOD", filtersToParamState(filters));
    expect(href).toBe("/coastsnap/CS-DRIFTWOOD/archive");
  });

  it("carries an explicit page forward alongside preserved filters", () => {
    const filters = parseCoastSnapArchiveFilters({ mediaType: "image" });
    const href = buildArchiveHref("CS-DRIFTWOOD", { ...filtersToParamState(filters), page: "2" });
    expect(href).toBe("/coastsnap/CS-DRIFTWOOD/archive?mediaType=image&page=2");
  });

  it("never includes a rejected invalid value in the rebuilt URL", () => {
    const filters = parseCoastSnapArchiveFilters({ mediaType: "hologram", date: "not-a-date" });
    const href = buildArchiveHref("CS-DRIFTWOOD", filtersToParamState(filters));
    expect(href).toBe("/coastsnap/CS-DRIFTWOOD/archive");
  });
});

describe("summariseFilters", () => {
  it("is empty for no active filters", () => {
    expect(summariseFilters(parseCoastSnapArchiveFilters({}))).toEqual([]);
  });

  it("includes a lower-cased media type label", () => {
    expect(summariseFilters(parseCoastSnapArchiveFilters({ mediaType: "composite" }))).toEqual([
      "composite",
    ]);
  });

  it("describes an open-ended from-only range", () => {
    expect(summariseFilters(parseCoastSnapArchiveFilters({ from: "2026-08-01" }))).toEqual([
      "1 Aug to now",
    ]);
  });
});

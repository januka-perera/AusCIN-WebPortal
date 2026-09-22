import { describe, expect, it } from "vitest";
import { paginate } from "./pagination";

const ITEMS = Array.from({ length: 25 }, (_, index) => index + 1);

describe("paginate", () => {
  it("returns the first page by default shape", () => {
    const result = paginate(ITEMS, 1, 10);
    expect(result).toEqual({ items: ITEMS.slice(0, 10), total: 25, page: 1, pageSize: 10, totalPages: 3 });
  });

  it("returns the last, partial page", () => {
    const result = paginate(ITEMS, 3, 10);
    expect(result.items).toEqual([21, 22, 23, 24, 25]);
    expect(result.totalPages).toBe(3);
  });

  it("clamps a page number above the last page down to the last page", () => {
    const result = paginate(ITEMS, 99, 10);
    expect(result.page).toBe(3);
    expect(result.items).toEqual([21, 22, 23, 24, 25]);
  });

  it("clamps a zero or negative page number up to page 1", () => {
    expect(paginate(ITEMS, 0, 10).page).toBe(1);
    expect(paginate(ITEMS, -5, 10).page).toBe(1);
  });

  it("returns exactly one empty page for an empty input, never a zero or negative page count", () => {
    const result = paginate([], 1, 10);
    expect(result).toEqual({ items: [], total: 0, page: 1, pageSize: 10, totalPages: 1 });
  });

  it("handles a page count that divides evenly with no trailing empty page", () => {
    const result = paginate(ITEMS.slice(0, 20), 2, 10);
    expect(result.totalPages).toBe(2);
    expect(result.items).toHaveLength(10);
  });
});

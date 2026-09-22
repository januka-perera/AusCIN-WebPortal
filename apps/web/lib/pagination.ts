import type { PaginatedResult } from "@/data/types/api";

/** Default page size for the cross-station observations list. */
export const DEFAULT_PAGE_SIZE = 24;

/**
 * Slices an already-filtered, already-sorted array into one page.
 * `page` is clamped into [1, totalPages] so an out-of-range page number
 * (too high, zero, negative) falls back to the nearest valid page
 * instead of returning an empty or out-of-bounds slice.
 */
export function paginate<T>(items: T[], page: number, pageSize: number): PaginatedResult<T> {
  const total = items.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const safePage = Math.min(Math.max(1, page), totalPages);
  const start = (safePage - 1) * pageSize;
  return {
    items: items.slice(start, start + pageSize),
    total,
    page: safePage,
    pageSize,
    totalPages,
  };
}

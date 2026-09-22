/**
 * API-shaped result types, independent of the sample-data implementation.
 *
 * These describe the *shape* a future FastAPI catalogue is expected to
 * return, so the frontend can be written against them now and keep
 * working unchanged once `data/repository.ts`'s sample implementation is
 * swapped for a real HTTP client. Nothing here may import from
 * `data/sample` or `data/queries` — that would tie an API-shaped
 * contract back to one specific implementation of it.
 */

/** A page of results from a collection endpoint, with enough context to render pagination controls. */
export type PaginatedResult<T> = {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
};

/** The request-side counterpart of PaginatedResult: which page and how large. */
export type PaginationParams = {
  page: number;
  pageSize: number;
};

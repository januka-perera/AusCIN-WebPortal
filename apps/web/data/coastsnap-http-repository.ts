import type { CoastSnapObservationDateRange, CoastSnapObservationFilters } from "./coastsnap-queries";
import type { CoastSnapRepository } from "./coastsnap-repository";
import type { CoastSnapContributor, CoastSnapObservation, CoastSnapSite } from "./types/coastsnap";
import type { PaginatedResult, PaginationParams } from "./types/api";
import type {
  MediaType,
  OperatingStatus,
  ProcessingStatus,
  PublicationStatus,
  StateOrTerritory,
} from "./types/media";

/**
 * `CoastSnapRepository` backed by the AusCIN catalogue API (apps/api).
 *
 * Server-side only. It is selected by `COASTSNAP_API_BASE_URL` in
 * `coastsnap-repository.ts`, and the base URL never reaches the browser.
 *
 * Contract: the API's camelCase JSON (see apps/api/README.md) is checked at
 * runtime and mapped onto the existing frontend types. Unknown extra fields
 * are dropped. Anything malformed becomes a `CoastSnapApiError` rather than
 * a half-trusted object.
 *
 * Status codes:
 *  - 404 → `undefined` (or an empty list or page), exactly like the sample
 *    repository for an unknown ID. The API returns the same 404 for
 *    non-public sites, so they're indistinguishable from unknown ones here too.
 *  - Any other non-2xx, a network failure, a timeout or an invalid body →
 *    `CoastSnapApiError`. The app/coastsnap error boundary shows it as a
 *    controlled "catalogue unavailable" state.
 *
 * Media URLs: the API returns either root-relative (`/media/coastsnap/…`)
 * or absolute URLs, depending on its `AUSCIN_MEDIA_BASE_URL`. Every media
 * URL is resolved against one explicit, browser-reachable **media origin**:
 * `COASTSNAP_MEDIA_ORIGIN`, defaulting to the origin of
 * `COASTSNAP_API_BASE_URL`. That way a root-relative URL can never resolve
 * against the Next.js origin. A URL is kept only if all of these hold:
 *  - it resolves to that media origin
 *  - its path is exactly `/media/coastsnap/<this observation's mediaId>/<kind>`
 *  - it has no credentials, query or fragment
 * Anything else (another host, `file:`, `javascript:`, a `/g/data` or
 * other filesystem-looking path) becomes `null`, so the UI shows its normal
 * "unavailable" state instead.
 *
 * Fetches use `cache: "no-store"`. Catalogue data is live, and this keeps
 * `next build` from ever needing the API.
 */

export type CoastSnapApiErrorKind = "config" | "network" | "timeout" | "http" | "invalid-response";

/** A controlled failure. The message names the request path only, never the API host or a filesystem path. */
export class CoastSnapApiError extends Error {
  readonly kind: CoastSnapApiErrorKind;
  readonly status?: number;

  constructor(kind: CoastSnapApiErrorKind, message: string, status?: number) {
    super(message);
    this.name = "CoastSnapApiError";
    this.kind = kind;
    this.status = status;
  }
}

export type HttpCoastSnapRepositoryOptions = {
  /** Server-side API base, e.g. "http://localhost:8000". May include a path prefix. */
  apiBaseUrl: string;
  /** Browser-reachable origin that media URLs must use. Defaults to the API base URL's origin. */
  mediaOrigin?: string;
  fetchImpl?: typeof fetch;
  timeoutMs?: number;
};

const DEFAULT_TIMEOUT_MS = 10_000;
/** The API's maximum page size. */
const API_MAX_PAGE_SIZE = 100;
/** listObservationsForSite() returns a full array, so it pages through the API. It stops here instead of loading an unbounded archive into memory. */
export const MAX_FULL_LIST_OBSERVATIONS = 2_000;

/** Site and media IDs are opaque tokens. Anything else can't exist in the API, so it's answered without a request. */
const SAFE_ID_PATTERN = /^[A-Za-z0-9_-]{1,128}$/;

const STATES: readonly StateOrTerritory[] = ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "NT", "ACT"];
const OPERATING_STATUSES: readonly OperatingStatus[] = ["active", "offline", "maintenance"];
const MEDIA_TYPES: readonly MediaType[] = ["image", "composite", "timelapse"];
const PROCESSING_STATUSES: readonly ProcessingStatus[] = ["processed", "processing", "failed"];
const PUBLICATION_STATUSES: readonly PublicationStatus[] = ["public", "embargoed", "project-only", "restricted"];
type MediaKind = "thumbnail" | "preview" | "original";

// --- URL handling ----------------------------------------------------------------

/** Parses an http(s) base or origin URL. Rejects credentials, queries and fragments. */
export function parseHttpBaseUrl(raw: string, name: string): URL {
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    throw new CoastSnapApiError("config", `${name} is not a valid URL.`);
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new CoastSnapApiError("config", `${name} must use http or https.`);
  }
  if (url.username || url.password || url.search || url.hash) {
    throw new CoastSnapApiError("config", `${name} must not include credentials, a query or a fragment.`);
  }
  return url;
}

/**
 * Resolves an API media URL against the media origin and keeps it only if it
 * is exactly `/media/coastsnap/<mediaId>/<kind>` on that origin. Returns
 * null otherwise. See the module comment.
 */
export function normalizeMediaUrl(
  raw: unknown,
  mediaOrigin: string,
  mediaId: string,
  kind: MediaKind,
): string | null {
  if (typeof raw !== "string" || raw.length === 0) return null;
  let resolved: URL;
  try {
    resolved = new URL(raw, `${mediaOrigin}/`);
  } catch {
    return null;
  }
  if (resolved.origin !== mediaOrigin) return null;
  if (resolved.username || resolved.password || resolved.search || resolved.hash) return null;
  if (resolved.pathname !== `/media/coastsnap/${encodeURIComponent(mediaId)}/${kind}`) return null;
  return resolved.toString();
}

// --- Runtime validation of API JSON ---------------------------------------------------

type Json = Record<string, unknown>;

function invalid(path: string, detail: string): CoastSnapApiError {
  return new CoastSnapApiError("invalid-response", `Unexpected response from ${path}: ${detail}.`);
}

function asObject(value: unknown, path: string, what: string): Json {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw invalid(path, `${what} is not an object`);
  return value as Json;
}

function str(obj: Json, key: string, path: string): string {
  const value = obj[key];
  if (typeof value !== "string") throw invalid(path, `"${key}" is not a string`);
  return value;
}

function num(obj: Json, key: string, path: string): number {
  const value = obj[key];
  if (typeof value !== "number" || !Number.isFinite(value)) throw invalid(path, `"${key}" is not a number`);
  return value;
}

function int(obj: Json, key: string, path: string, min: number): number {
  const value = num(obj, key, path);
  if (!Number.isInteger(value) || value < min) throw invalid(path, `"${key}" is not an integer ≥ ${min}`);
  return value;
}

function bool(obj: Json, key: string, path: string): boolean {
  const value = obj[key];
  if (typeof value !== "boolean") throw invalid(path, `"${key}" is not a boolean`);
  return value;
}

function oneOf<T extends string>(obj: Json, key: string, allowed: readonly T[], path: string): T {
  const value = str(obj, key, path);
  if (!(allowed as readonly string[]).includes(value)) throw invalid(path, `"${key}" has an unexpected value`);
  return value as T;
}

function safeId(obj: Json, key: string, path: string): string {
  const value = str(obj, key, path);
  if (!SAFE_ID_PATTERN.test(value)) throw invalid(path, `"${key}" is not an opaque identifier`);
  return value;
}

function isoTimestamp(obj: Json, key: string, path: string): string {
  const value = str(obj, key, path);
  if (Number.isNaN(Date.parse(value))) throw invalid(path, `"${key}" is not a timestamp`);
  return value;
}

function optionalDimension(obj: Json, key: string, path: string): number | undefined {
  if (obj[key] === undefined || obj[key] === null) return undefined;
  return int(obj, key, path, 1);
}

// --- Mapping ------------------------------------------------------------------------

export function mapSite(value: unknown, path: string, mediaOrigin: string): CoastSnapSite {
  const obj = asObject(value, path, "site");
  const id = safeId(obj, "id", path);
  const representative = obj.representativeImageUrl;
  return {
    id,
    name: str(obj, "name", path),
    state: oneOf(obj, "state", STATES, path),
    latitude: num(obj, "latitude", path),
    longitude: num(obj, "longitude", path),
    region: str(obj, "region", path),
    description: str(obj, "description", path),
    status: oneOf(obj, "status", OPERATING_STATUSES, path),
    establishedSince: str(obj, "establishedSince", path),
    // The API has no per-site image yet (always null). If it ever sends one,
    // it must be an API media URL on the media origin; the owning media ID is
    // unknown here, so only the path prefix is checked.
    representativeImageUrl:
      typeof representative === "string" ? normalizeRepresentativeUrl(representative, mediaOrigin) : null,
    isSynthetic: bool(obj, "isSynthetic", path),
  };
}

function normalizeRepresentativeUrl(raw: string, mediaOrigin: string): string | null {
  const match = /^(?:https?:\/\/[^/]+)?\/media\/coastsnap\/([A-Za-z0-9_-]{1,128})\/(thumbnail|preview)$/.exec(raw);
  return match ? normalizeMediaUrl(raw, mediaOrigin, match[1], match[2] as MediaKind) : null;
}

export function mapObservation(value: unknown, path: string, mediaOrigin: string): CoastSnapObservation {
  const obj = asObject(value, path, "observation");
  const mediaId = safeId(obj, "mediaId", path);
  const contributorObj = asObject(obj.contributor, path, "contributor");
  // The API only ever sends a display name its contributor policy allows (currently a
  // fixed placeholder). Nothing else from the source record is read here.
  const contributor: CoastSnapContributor = {
    displayName: str(contributorObj, "displayName", path),
    attributionText: str(contributorObj, "attributionText", path),
  };
  if (obj.sourcePlatform !== "spotteron") throw invalid(path, `"sourcePlatform" has an unexpected value`);

  const originalUrl = normalizeMediaUrl(obj.originalUrl, mediaOrigin, mediaId, "original");
  const observation: CoastSnapObservation = {
    id: safeId(obj, "id", path),
    siteId: safeId(obj, "siteId", path),
    sourcePlatform: "spotteron",
    mediaId,
    mediaType: oneOf(obj, "mediaType", MEDIA_TYPES, path),
    capturedAtUtc: isoTimestamp(obj, "capturedAtUtc", path),
    displayTimeZone: str(obj, "displayTimeZone", path),
    contributor,
    processingStatus: oneOf(obj, "processingStatus", PROCESSING_STATUSES, path),
    publicationStatus: oneOf(obj, "publicationStatus", PUBLICATION_STATUSES, path),
    thumbnailUrl: normalizeMediaUrl(obj.thumbnailUrl, mediaOrigin, mediaId, "thumbnail"),
    previewUrl: normalizeMediaUrl(obj.previewUrl, mediaOrigin, mediaId, "preview"),
    // A download is offered only when the API says so AND the URL is safe. Either on its own is not enough.
    isOriginalAvailable: bool(obj, "isOriginalAvailable", path) && originalUrl !== null,
    originalUrl,
    caption: str(obj, "caption", path),
    altText: str(obj, "altText", path),
    isSynthetic: bool(obj, "isSynthetic", path),
  };
  const width = optionalDimension(obj, "width", path);
  const height = optionalDimension(obj, "height", path);
  if (width !== undefined && height !== undefined) {
    observation.width = width;
    observation.height = height;
  }
  return observation;
}

function mapPage(value: unknown, path: string, mediaOrigin: string): PaginatedResult<CoastSnapObservation> {
  const obj = asObject(value, path, "page");
  if (!Array.isArray(obj.items)) throw invalid(path, `"items" is not an array`);
  return {
    items: obj.items.map((item) => mapObservation(item, path, mediaOrigin)),
    total: int(obj, "total", path, 0),
    page: int(obj, "page", path, 1),
    pageSize: int(obj, "pageSize", path, 1),
    totalPages: int(obj, "totalPages", path, 1),
  };
}

// --- Repository ---------------------------------------------------------------------

export class HttpCoastSnapRepository implements CoastSnapRepository {
  private readonly apiBase: URL;
  private readonly mediaOrigin: string;
  /** Injected for tests. Otherwise the global fetch is looked up per request (Next.js patches it). */
  private readonly fetchImpl?: typeof fetch;
  private readonly timeoutMs: number;

  constructor(options: HttpCoastSnapRepositoryOptions) {
    this.apiBase = parseHttpBaseUrl(options.apiBaseUrl, "COASTSNAP_API_BASE_URL");
    this.mediaOrigin = options.mediaOrigin
      ? parseHttpBaseUrl(options.mediaOrigin, "COASTSNAP_MEDIA_ORIGIN").origin
      : this.apiBase.origin;
    this.fetchImpl = options.fetchImpl;
    this.timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  }

  /** GETs an API path. Returns undefined on 404 and throws CoastSnapApiError on any other failure. */
  private async getJson(path: string, query?: URLSearchParams): Promise<unknown | undefined> {
    const prefix = this.apiBase.pathname.replace(/\/+$/, "");
    const url = new URL(`${prefix}${path}`, this.apiBase.origin);
    if (query && [...query].length > 0) url.search = query.toString();

    let response: Response;
    try {
      response = await (this.fetchImpl ?? globalThis.fetch)(url, {
        cache: "no-store",
        headers: { Accept: "application/json" },
        signal: AbortSignal.timeout(this.timeoutMs),
      });
    } catch (error) {
      const timedOut = error instanceof DOMException && (error.name === "TimeoutError" || error.name === "AbortError");
      throw new CoastSnapApiError(
        timedOut ? "timeout" : "network",
        timedOut ? `CoastSnap catalogue request timed out: ${path}` : `CoastSnap catalogue is unreachable: ${path}`,
      );
    }

    if (response.status === 404) return undefined;
    if (!response.ok) {
      throw new CoastSnapApiError("http", `CoastSnap catalogue returned HTTP ${response.status}: ${path}`, response.status);
    }
    try {
      return await response.json();
    } catch {
      throw invalid(path, "body is not JSON");
    }
  }

  async listSites(): Promise<CoastSnapSite[]> {
    const path = "/api/v1/coastsnap/sites";
    const body = await this.getJson(path);
    if (!Array.isArray(body)) throw invalid(path, "expected an array of sites");
    return body.map((site) => mapSite(site, path, this.mediaOrigin));
  }

  async getSite(siteId: string): Promise<CoastSnapSite | undefined> {
    if (!SAFE_ID_PATTERN.test(siteId)) return undefined;
    const path = `/api/v1/coastsnap/sites/${encodeURIComponent(siteId)}`;
    const body = await this.getJson(path);
    return body === undefined ? undefined : mapSite(body, path, this.mediaOrigin);
  }

  async listObservationsForSitePaginated(
    siteId: string,
    filters: CoastSnapObservationFilters,
    pagination: PaginationParams,
  ): Promise<PaginatedResult<CoastSnapObservation>> {
    const pageSize = Math.min(Math.max(1, Math.trunc(pagination.pageSize)), API_MAX_PAGE_SIZE);
    const page = Math.max(1, Math.trunc(pagination.page));
    const empty: PaginatedResult<CoastSnapObservation> = { items: [], total: 0, page: 1, pageSize, totalPages: 1 };
    if (!SAFE_ID_PATTERN.test(siteId)) return empty;

    const query = new URLSearchParams();
    if (filters.mediaType) query.set("mediaType", filters.mediaType);
    if (filters.date) query.set("date", filters.date);
    if (filters.from) query.set("from", filters.from);
    if (filters.to) query.set("to", filters.to);
    query.set("page", String(page));
    query.set("pageSize", String(pageSize));

    const path = `/api/v1/coastsnap/sites/${encodeURIComponent(siteId)}/observations`;
    const body = await this.getJson(path, query);
    return body === undefined ? empty : mapPage(body, path, this.mediaOrigin);
  }

  async listObservationsForSite(
    siteId: string,
    filters: CoastSnapObservationFilters = {},
  ): Promise<CoastSnapObservation[]> {
    const all: CoastSnapObservation[] = [];
    for (let page = 1; ; page += 1) {
      const result = await this.listObservationsForSitePaginated(siteId, filters, { page, pageSize: API_MAX_PAGE_SIZE });
      all.push(...result.items);
      if (result.page >= result.totalPages || result.items.length === 0) return all;
      if (all.length >= MAX_FULL_LIST_OBSERVATIONS) {
        throw new CoastSnapApiError(
          "invalid-response",
          `Site has more than ${MAX_FULL_LIST_OBSERVATIONS} observations; use the paginated listing instead.`,
        );
      }
    }
  }

  async getObservationForSite(siteId: string, observationId: string): Promise<CoastSnapObservation | undefined> {
    if (!SAFE_ID_PATTERN.test(siteId) || !SAFE_ID_PATTERN.test(observationId)) return undefined;
    const path = `/api/v1/coastsnap/sites/${encodeURIComponent(siteId)}/observations/${encodeURIComponent(observationId)}`;
    const body = await this.getJson(path);
    if (body === undefined) return undefined;
    const observation = mapObservation(body, path, this.mediaOrigin);
    // Defence in depth: never show another site's record under this site's URL.
    return observation.siteId === siteId ? observation : undefined;
  }

  /** The API has no cross-site lookup, so this searches each public site. Pages use the site-scoped lookup. */
  async getObservation(observationId: string): Promise<CoastSnapObservation | undefined> {
    if (!SAFE_ID_PATTERN.test(observationId)) return undefined;
    for (const site of await this.listSites()) {
      const found = await this.getObservationForSite(site.id, observationId);
      if (found) return found;
    }
    return undefined;
  }

  async listLatestObservationPerSite(): Promise<CoastSnapObservation[]> {
    const latest: CoastSnapObservation[] = [];
    for (const site of await this.listSites()) {
      const { items } = await this.listObservationsForSitePaginated(site.id, {}, { page: 1, pageSize: 1 });
      const newest = items[0];
      if (newest && newest.processingStatus === "processed" && newest.publicationStatus === "public") {
        latest.push(newest);
      }
    }
    return latest.sort((a, b) => Date.parse(b.capturedAtUtc) - Date.parse(a.capturedAtUtc));
  }

  async getObservationDateRange(siteId: string): Promise<CoastSnapObservationDateRange | undefined> {
    if (!SAFE_ID_PATTERN.test(siteId)) return undefined;
    const path = `/api/v1/coastsnap/sites/${encodeURIComponent(siteId)}/date-range`;
    const body = await this.getJson(path);
    if (body === undefined) return undefined;
    const obj = asObject(body, path, "date range");
    // Both null means the site exists but has no observations. The sample repository returns undefined for that too.
    if (obj.earliest === null && obj.latest === null) return undefined;
    return {
      earliest: mapObservation(obj.earliest, path, this.mediaOrigin),
      latest: mapObservation(obj.latest, path, this.mediaOrigin),
    };
  }
}

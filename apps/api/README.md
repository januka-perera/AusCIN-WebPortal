# AusCIN catalogue API (apps/api)

Local, fixture-backed milestones of the catalogue described in
[`docs/implementation/coastsnap-single-site-publication.md`](../../docs/implementation/coastsnap-single-site-publication.md).
This is a read-only FastAPI service that serves CoastSnap metadata and local
media from an in-memory catalogue built at startup from these inputs:

1. **A reviewed site registry** (JSON). This is the only thing that decides whether
   a site is public and whether its originals may be downloaded.
2. **One worker manifest** in the existing `apps/worker` format
   (`manifests/<root_id>.json`). It is parsed with the worker's own
   `coastsnap_import.models.Manifest`.
3. **An optional derivatives index** (JSON) listing thumbnails and previews.
4. **An optional local media root** that every relative path resolves beneath.

Not implemented yet:

- PostgreSQL and Nginx
- Real Spotteron access
- `/g/data` access or production storage routing
- Frontend changes
- Licence or contributor-display policy

## Installation (Windows PowerShell)

```powershell
cd apps\api
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
# The worker package provides the manifest schema. Install it from the
# checkout first — it is intentionally not a declared dependency.
.\.venv\Scripts\python.exe -m pip install -e ..\worker -e ".[dev]"
```

On Linux/Nectar the same steps apply with `python3 -m venv .venv` and
`.venv/bin/python`.

## Configuration

Environment variables (see `.env.example`; names only, never commit values):

| Variable | Required | Meaning |
|---|---|---|
| `AUSCIN_API_ENV` | no (default `development`) | `development`, `test` or `production`. Outside production, any path under `/g/data` is refused at startup. |
| `COASTSNAP_SITE_REGISTRY_PATH` | yes | Reviewed site registry JSON |
| `COASTSNAP_MANIFEST_PATH` | yes | One worker manifest JSON |
| `COASTSNAP_DERIVATIVES_INDEX_PATH` | no | Thumbnail/preview index. Without it, no derivative URLs are offered. |
| `COASTSNAP_MEDIA_ROOT` | no | Local media root. Without it, media URLs are null and media endpoints return 503. If set, it must exist when the app starts. |
| `AUSCIN_MEDIA_BASE_URL` | no | An http(s) origin used as a prefix for media URLs, e.g. `http://localhost:8000`. Without it, media URLs are root-relative. |

## Running locally against the synthetic fixtures

```powershell
cd apps\api
# Generate synthetic JPEGs (not real photos) into a git-ignored media root:
.\.venv\Scripts\python.exe tests\fixtures\synthetic_media.py .local-media

$env:COASTSNAP_SITE_REGISTRY_PATH = "tests/fixtures/coastsnap/sites-registry.json"
$env:COASTSNAP_MANIFEST_PATH = "tests/fixtures/coastsnap/manifest.json"
$env:COASTSNAP_DERIVATIVES_INDEX_PATH = "tests/fixtures/coastsnap/derivatives-index.json"
$env:COASTSNAP_MEDIA_ROOT = ".local-media"
$env:AUSCIN_MEDIA_BASE_URL = "http://localhost:8000"
.\.venv\Scripts\python.exe -m uvicorn auscin_api.main:create_app --factory --reload --port 8000
```

Then open <http://localhost:8000/api/v1/health> or the OpenAPI docs at
<http://localhost:8000/docs>.

## Endpoints

### Catalogue (JSON)

| Method + path | Response |
|---|---|
| `GET /api/v1/health` | `{status, publicSiteCount, publicObservationCount}` |
| `GET /api/v1/coastsnap/sites` | Public sites (`CoastSnapSite` shape) |
| `GET /api/v1/coastsnap/sites/{site_id}` | One public site, or 404 |
| `GET /api/v1/coastsnap/sites/{site_id}/observations` | `PaginatedResult<CoastSnapObservation>`, newest first |
| `GET /api/v1/coastsnap/sites/{site_id}/observations/{media_id}` | One observation, scoped to the site, or 404 |
| `GET /api/v1/coastsnap/sites/{site_id}/date-range` | `{earliest, latest}` observations; both `null` if the site has none |

Observation query parameters mirror the frontend archive filters
(`apps/web/data/coastsnap-queries.ts`):

- `mediaType`: `image` | `composite` | `timelapse`
- `date`: `YYYY-MM-DD`, the capture date in the site's display time zone. When set, it takes precedence over `from`/`to`.
- `from` / `to`: an inclusive range of local dates.
- `page`: at least 1. A page past the end returns the last page, the same as the frontend's `paginate()`.
- `pageSize`: 1–100, default 24.

Invalid values return 422.

### Media (GET and HEAD)

| Path | Serves | Notes |
|---|---|---|
| `/media/coastsnap/{media_id}/original` | The **Level 1** file | `Content-Disposition: attachment; filename="<media_id>.<ext>"`, the correct `Content-Type`, `ETag` = catalogue SHA-256, HTTP Range requests supported |
| `/media/coastsnap/{media_id}/preview` | Browser-sized preview JPEG | Served inline |
| `/media/coastsnap/{media_id}/thumbnail` | Thumbnail JPEG | Served inline |

Media responses and errors:

| Status | `code` | When |
|---|---|---|
| 200 / 206 | — | File served, fully (200) or as a byte range (206) |
| 403 | `download_not_permitted` | The registry doesn't permit original downloads for the site |
| 404 | `media_not_found` | Unknown media ID, an ID minted for another site, a non-public site, or an incomplete manifest entry |
| 404 | `preview_not_available` / `thumbnail_not_available` | No such rendition in the derivatives index. **There is never a fallback to the original.** |
| 404 | `original_not_available` | The Level 1 file type isn't one the API serves (JPEG, PNG or WebP) |
| 416 | — | Unsatisfiable range |
| 503 | `media_unavailable` | Covers four cases: no media root is configured; a recorded file is missing or unreadable; the file's size no longer matches the catalogue; or a path was rejected by the media store |

Errors use one controlled shape, and request input and paths are never echoed:

```json
{ "error": { "code": "site_not_found", "message": "No public CoastSnap site has this identifier." } }
```

A non-public site returns exactly the same 404 as an unknown site.

### Range requests

Supported natively by Starlette's `FileResponse` (Starlette 1.7):

- single ranges → 206, with `Content-Range`
- multiple ranges → `multipart/byteranges`
- unsatisfiable ranges → 416
- `If-Range` is checked against the checksum ETag

Previews and thumbnails also support ranges. They use Starlette's default
ETag, which is based on mtime and size.

### Download policy (provisional)

`original` serves the **Level 1** product, which is the Level 0 image bytes plus
embedded AusCIN provenance XMP. Whether the public download should be Level 0
or Level 1 is still undecided. When it is decided, the change is confined to
`MediaRecord` and the `original` route.

`isOriginalAvailable` is true only when all of these hold:

- the site is public
- its registry entry has `original_download_permitted: true` (default `false`)
- the Level 1 type is servable
- a media root is configured

File existence is not checked when building JSON, because stat-ing every file
would be a directory scan. A missing file surfaces as a 503 from the media
endpoint instead.

## Catalogue and media-store rules

### Visibility

Only registry entries with `publication_status: "public"` are exposed.
Observations are only exposed when the manifest's `root_id` maps to such a
site. A manifest or media file on disk never publishes anything by itself.

### Load-time path safety

Every relative path in the manifest and in the derivatives index must be a
plain, forward-slash, relative path inside its expected tree:

- `level-0|level-1/root-<root_id>/…`
- `metadata/source-records/…`
- `derivatives/thumbnails|previews/root-<root_id>/…`

Any of the following rejects the **whole** input at startup:

- absolute POSIX paths, Windows drive paths or UNC paths
- backslashes or colons
- empty, `.` or `..` segments
- segments ending in a dot or space
- NUL bytes

### Serve-time path safety

`LocalMediaStore` applies the same rules again as defence in depth. It
resolves paths only from catalogue records, never from a request. It follows
symlinks and junctions and then requires the resolved file to be inside the
media root. The only request inputs are the opaque media ID and a fixed kind:
`original`, `preview` or `thumbnail`.

### No paths in responses

- `MediaRecord` (the internal relative paths, size, checksum and dimensions) is
  never serialised.
- Media URLs contain only the opaque media ID.
- Headers carry only the opaque filename.

### Other consistency checks

The loader also rejects:

- entries whose root ID doesn't match the manifest
- duplicate observations
- Level 1 checksums that aren't SHA-256 hex
- a registry with duplicate site or root IDs, or unknown fields
- a derivatives index for another root, for unknown observations, with
  non-JPEG derivatives, or with unknown fields
- naive (non-UTC) timestamps

### Presentable entries

An entry is shown only when both Level 0 and Level 1 are present and
`spotted_at_utc` is known.

### Opaque IDs

`media_id` (also returned as `id`) is `csm_` + 24 hex characters of a SHA-256
over (site ID, source observation ID). It is stable across reloads and
reveals neither the Spotteron ID nor any path. Site IDs are the registry's
human-legible slugs.

### Timestamps

- `capturedAtUtc` is the worker's `spotted_at_utc`.
- `capturedAtSourceRaw` is the worker's unmodified `spotted_at_raw`.
- `ingestedAtUtc` is the manifest entry's `ingested_at_utc`.

The source time zone behind `spotted_at_utc` is still the worker's documented
assumption (default UTC).

## Derivatives index (provisional format)

The index will eventually be written by the planned worker derivatives step.
Until then it is hand-authored for fixtures:

```json
{
  "schema_version": 1,
  "root_id": "<root_id>",
  "derivatives": [
    {
      "observation_id": "<observation_id>",
      "width": 4032, "height": 3024,
      "thumbnail_relative_path": "derivatives/thumbnails/root-<root_id>/2026/08/01/<observation_id>.jpg",
      "preview_relative_path": "derivatives/previews/root-<root_id>/2026/08/01/<observation_id>.jpg"
    }
  ]
}
```

All fields other than `observation_id` are optional. Width and height are
the original's pixel dimensions. They are held internally and not yet
returned in JSON.

## Contract differences from the frontend types

Compared with `apps/web/data/types/coastsnap.ts`:

- **Media URLs:** `thumbnailUrl`, `previewUrl` and `originalUrl` are API media
  URLs when available, otherwise `null`. `representativeImageUrl` is always
  `null`, but the frontend declares it as `string`, so it needs to become
  `string | null` when the frontend is connected.
- **Contributor:** `contributor.displayName` is always the placeholder
  `"CoastSnap contributor"`, and `attributionText` comes from the registry.
- **Additive fields:** `capturedAtSourceRaw`, `ingestedAtUtc`, and
  `displayTimeZone` on the site.
- **Omitted:** `spotteronSiteId`, `spotteronObservationId`,
  `spotteronMediaId`, `sourceUrl`, `checksumSha256`, `width` and `height`.

## Tests

```powershell
cd apps\api
.\.venv\Scripts\python.exe -m pytest -q -rs
```

### Temporary files

`tests/conftest.py` points pytest's `--basetemp` at the git-ignored
`apps/api/.pytest-tmp/`, unless `--basetemp` is passed explicitly. This
avoids `PermissionError`s from pytest's default `%TEMP%\pytest-of-<user>`
directory on locked-down Windows machines. pytest clears that directory at
the start of each run.

### Symlink tests

The symlink-escape tests need permission to create symlinks. On Windows that
means Developer Mode or `SeCreateSymbolicLinkPrivilege`. Without it they are
**skipped**, not passed, and the skip reason is shown with `-rs`. The NTFS
junction-escape test needs no privilege and always runs on Windows.

### Fixtures

Fixtures are entirely synthetic:

- **Placeholder IDs:** `TEST_ROOT_ID`, `TEST_OBS_000n`, `CS-TEST-SITE`.
- **Placeholder values:** `remote_root` is `TEST_PUBLICATION_ROOT`, and
  source URLs use `example.invalid`.
- **Images:** there are no committed images. The tests generate tiny JPEGs
  at runtime (`tests/fixtures/synthetic_media.py`).
- **Checksums:** the manifest fixture was produced with the worker's own
  Pydantic models. Its Level 0/1 sizes and checksums are those of the
  synthetic JPEGs, so tests can verify the ETag against the served bytes.

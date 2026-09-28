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
   It is written by the worker's `python -m coastsnap_import.derivatives`
   command and parsed with the worker's own
   `coastsnap_import.derivatives.DerivativesIndex`.
4. **An optional local media root** that the Level 1 paths resolve beneath,
   and an optional **separate derivatives root** for the worker's
   `--output-root`.

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
# The worker package provides the manifest and derivatives-index schemas.
# Install it from the checkout first — it is intentionally not a declared
# dependency. The [derivatives] extra brings in Pillow. The API never imports
# Pillow; it's needed only for the worker-to-API integration test (skipped
# without it).
.\.venv\Scripts\python.exe -m pip install -e "..\worker[derivatives]" -e ".[dev]"
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
| `COASTSNAP_MEDIA_ROOT` | no | Local media root for Level 1 paths (the worker's staging directory). Without it, media URLs are null and media endpoints return 503. If set, it must exist when the app starts. |
| `COASTSNAP_DERIVATIVES_ROOT` | no | Directory the derivatives index's paths resolve beneath (the worker's `--output-root`). Defaults to `COASTSNAP_MEDIA_ROOT`, and requires it to be set. |
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
| `/media/coastsnap/{media_id}/level0` | **Level 0**: the untouched source image, exactly as downloaded from Spotteron | `Content-Disposition: attachment; filename="<media_id>_level0.<ext>"`, the correct `Content-Type`, `ETag` = the Level 0 manifest SHA-256, HTTP Range requests supported |
| `/media/coastsnap/{media_id}/level1` | **Level 1**: the AusCIN provenance copy (Level 0's image bytes plus embedded provenance XMP) | The same, with `filename="<media_id>_level1.<ext>"` and `ETag` = the Level 1 manifest SHA-256 |
| `/media/coastsnap/{media_id}/original` | **Deprecated** alias for `/level1` | The identical Level 1 response, plus `Deprecation: true` and `Link: </media/coastsnap/{media_id}/level1>; rel="successor-version"`. It is marked `deprecated` in OpenAPI. Kept temporarily for compatibility; new clients must use `/level0` or `/level1`. |
| `/media/coastsnap/{media_id}/preview` | Browser-sized preview JPEG (≤ 1600 px) | Served inline, `ETag` = index SHA-256 |
| `/media/coastsnap/{media_id}/thumbnail` | Thumbnail JPEG (≤ 400 px) | Served inline, `ETag` = index SHA-256 |

HEAD is served for every media path but is omitted from the OpenAPI schema,
so each operation ID stays unique.

Media responses and errors:

| Status | `code` | When |
|---|---|---|
| 200 / 206 | — | File served, fully (200) or as a byte range (206) |
| 403 | `download_not_permitted` | The registry doesn't permit downloads of **that level** for the site. The message names the level. |
| 404 | `media_not_found` | Unknown media ID, an ID minted for another site, a non-public site, or an incomplete manifest entry |
| 404 | `preview_not_available` / `thumbnail_not_available` | No such rendition in the derivatives index, or the index entry is stale (see below). **There is never a fallback to Level 0 or Level 1.** |
| 404 | `level0_not_available` / `level1_not_available` | That level's file type isn't one the API serves (JPEG, PNG or WebP) |
| 416 | — | Unsatisfiable range |
| 503 | `media_unavailable` | Covers four cases: no media root is configured; a recorded file is missing or unreadable; the file's size no longer matches the manifest or index; or a path was rejected by the media store |

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

Previews and thumbnails also support ranges. Their ETag is the SHA-256
recorded in the derivatives index.

### Download policy (per product level)

Both product levels can be downloaded explicitly:

- **Level 0** is the untouched source image.
- **Level 1** is the AusCIN provenance copy.

Each has its own registry permission, `level0_download_permitted` and
`level1_download_permitted`. Both default to `false`, and neither implies
the other. The single `original_download_permitted` flag has been retired:
the registry model rejects it.

`levelNDownloadAvailable` is true only when all of these hold:

- the site is public
- its registry entry has `levelN_download_permitted: true`
- that level's file type is servable
- a media root is configured

When a level is available, the response also carries `levelNDownloadUrl` and
`levelNChecksumSha256`. The checksum is public integrity metadata, published
only alongside a downloadable file. Internal paths are never returned.

**Deprecated fields.** `isOriginalAvailable` and `originalUrl` still appear in
responses for compatibility. They mirror Level 1 (`originalUrl` is the
`/level1` URL), and the frontend no longer reads them.

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
`level0`, `level1`, `original` (deprecated), `preview` or `thumbnail`.

### No paths in responses

- `MediaRecord` is never serialised. It holds each level's internal relative
  path, content type, size, checksum and download permission, plus the
  derivative records and dimensions. Only the public URLs, availability flags
  and published checksums derived from it are returned.
- Media URLs contain only the opaque media ID.
- Headers carry only the opaque filename.

### Other consistency checks

The loader also rejects:

- entries whose root ID doesn't match the manifest
- duplicate observations
- Level 0 or Level 1 checksums that aren't SHA-256 hex
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

## Derivatives index (worker-generated, `schema_version: 2`)

The index is produced by the worker's separate derivatives command. See
`apps/worker/README.md`, "Generating thumbnails and previews":

```powershell
cd apps\worker
.\.venv\Scripts\python.exe -m coastsnap_import.derivatives `
  --manifest <staging>\manifests\<root_id>.json --input-root <staging> `
  --output-root <derivatives-root> --index-output <derivatives-root>\derivatives-index.json
```

Point `COASTSNAP_MEDIA_ROOT` at `<staging>`, `COASTSNAP_DERIVATIVES_ROOT` at
`<derivatives-root>`, and `COASTSNAP_DERIVATIVES_INDEX_PATH` at the index.
The API parses it with the worker's own `DerivativesIndex` model, so there
is one format. The shape is:

```json
{
  "schema_version": 2,
  "root_id": "<root_id>",
  "generated_at_utc": "…", "generator": "coastsnap-import/0.1.0",
  "specs": { "thumbnail": {"max_dimension": 400, "jpeg_quality": 80},
             "preview":   {"max_dimension": 1600, "jpeg_quality": 85} },
  "derivatives": [
    {
      "observation_id": "<observation_id>",
      "level1_product_id": "<observation_id>-L1",
      "source_sha256": "<Level 1 checksum the renditions were made from>",
      "source_width": 4032, "source_height": 3024,
      "thumbnail": { "relative_path": "derivatives/thumbnails/root-<root_id>/2026/08/01/<observation_id>.jpg",
                     "content_type": "image/jpeg", "width": 400, "height": 300,
                     "file_size_bytes": 41234, "sha256": "…" },
      "preview":   { "relative_path": "derivatives/previews/root-<root_id>/2026/08/01/<observation_id>.jpg",
                     "…": "…" }
    }
  ]
}
```

On top of the model's own validation, the API applies these checks:

- **Rejects the whole index** when it has any of:
  - unsafe or misplaced paths
  - non-JPEG renditions
  - a different `root_id`
  - unknown or duplicate observations
  - the old version-1 format
- **Drops stale entries:** an entry whose `source_sha256` or
  `level1_product_id` no longer matches the manifest is ignored, with a
  logged warning. Its URLs are then null and its routes return 404, so
  renditions of an older Level 1 are never served.

`source_width`/`source_height` are returned as the observation's `width` and
`height`: the Level 1 pixel dimensions as displayed, with EXIF orientation
applied. Both are `null` when the observation has no current (non-stale)
index entry; they are never guessed. `thumbnail`/`preview` may be `null`;
the committed fixture uses this to exercise a missing preview.

## Contract differences from the frontend types

Compared with `apps/web/data/types/coastsnap.ts`:

- **Media URLs:** `thumbnailUrl`, `previewUrl`, `level0DownloadUrl` and
  `level1DownloadUrl` are API media URLs when available, otherwise `null`.
  `representativeImageUrl` is always `null`; the frontend type allows that,
  and falls back to a recent observation's rendition.
- **Downloads:** `level0DownloadAvailable` / `level1DownloadAvailable`, plus
  `level0ChecksumSha256` / `level1ChecksumSha256` (which are `null` unless
  that level is available). `isOriginalAvailable` / `originalUrl` are
  deprecated and mirror Level 1.
- **Dimensions:** `width`/`height` are integers from the derivatives index,
  or `null`. The frontend treats `null` as "not recorded".
- **Contributor:** `contributor.displayName` is always the placeholder
  `"CoastSnap contributor"`, and `attributionText` comes from the registry.
- **Additive fields:** `capturedAtSourceRaw`, `ingestedAtUtc`, and
  `displayTimeZone` on the site.
- **Omitted:** `spotteronSiteId`, `spotteronObservationId`,
  `spotteronMediaId`, `sourceUrl` and `checksumSha256`.

## Local end-to-end workflow

This proves the whole chain locally, with synthetic data only:

```
worker manifest → worker-generated thumbnails/previews → FastAPI catalogue
  → Next.js CoastSnap pages → preview → Level 0 and Level 1 downloads (checksum-verified)
```

It never touches Spotteron, Nectar, Gadi or `/g/data`.

### Automated (recommended)

From the repository root, using this API virtual environment (which has the
API, the worker package with its `derivatives` extra, Pillow and httpx), with
Node.js/npm on PATH:

```powershell
apps\api\.venv\Scripts\python.exe scripts\coastsnap_e2e_smoke.py
```

`scripts/coastsnap_e2e_smoke.py` does the following:

1. **Stages synthetic data outside the repository.** It creates a temporary
   directory under the system temp directory (refusing any location inside
   the repository). In it, it writes five synthetic Level 0 JPEGs generated
   with Pillow (1600–3000 px), Level 1 copies of them with an added
   provenance segment (so the two levels differ), and a manifest written
   with the worker's own models. The manifest uses the fixture registry's `TEST_ROOT_ID` /
   `CS-TEST-SITE`.
2. **Generates derivatives with the real worker command.** It runs
   `python -m coastsnap_import.derivatives` with `--max-images 4`, so the
   fifth observation deliberately has no derivatives. It then runs it again
   and requires `processed=0 reused=4`.
3. **Starts FastAPI** on `127.0.0.1` with:
   - the fixture site registry
   - the generated manifest
   - the generated derivatives index
   - `COASTSNAP_MEDIA_ROOT` = the staging directory
   - `COASTSNAP_DERIVATIVES_ROOT` = the derivatives output root
   - `AUSCIN_MEDIA_BASE_URL` = the API origin
4. **Starts Next.js.** It runs `next build`, then `next start` with
   `COASTSNAP_API_BASE_URL` set.
5. **Checks the API and pages.** It checks all of the following:
   - **API:** thumbnail/preview URLs are present when derivatives exist, and
     `null` otherwise. Trusted dimensions are returned.
   - **Pages:** `/coastsnap`, the site archive and a media detail page are
     API-backed and use the API-mode footer.
   - **Renditions:** thumbnail and preview responses are JPEGs within
     400/1600 px.
   - **Level 0 and Level 1 downloads:** each must be an attachment named
     `<media_id>_<level>.jpg`, with that level's ETag, SHA-256 equal to that
     level's manifest checksum, a matching published checksum, and Range
     support. The two levels must differ, and the deprecated `/original`
     must still serve Level 1.
   - **Detail page:** it shows both buttons, "Download original (Level 0)" and
     "Download provenance copy (Level 1)", with explanations.
   - **No fallback:** a missing derivative returns 404 and is never
     substituted with either level.
   - **No leaks:** no `/g/data`, staging, repository or internal paths, and
     no raw Spotteron IDs, in any public response or rendered page.
6. **Restarts the API with Level 0 withheld and Level 1 permitted.** Level 0's
   URL and checksum must become null, `/level0` must return 403, Level 1 and
   `/original` must keep working, and the page must show only the Level 1
   button, with an explanation of why Level 0 is unavailable.
7. **Cleans up.** It stops both servers (whole process trees) and deletes the
   staging directory.

It prints one line per check and exits 1 on any failure, with the tail of each
server log. Options:

| Option | Effect |
|---|---|
| `--skip-build` | Reuse an existing `apps/web/.next` build |
| `--keep-staging` | Keep the staging directory for inspection |
| `--staging-parent <dir>` | Create staging under this directory |
| `--npm <path>` | Use this npm |

### Manual walk-through

The same flow by hand. Use any staging directory **outside** the repository.
The quickest way to get synthetic Level 1 files and a manifest there is to
keep the automated script's staging directory:

```powershell
apps\api\.venv\Scripts\python.exe scripts\coastsnap_e2e_smoke.py --keep-staging --skip-build
# It prints "Staging (outside the repository): <path>". Use that path:
$staging = "<path printed above>"
```

Then, in PowerShell:

```powershell
# Worker derivatives (the real command), twice. The second run reports reused=N.
cd apps\worker
.\.venv\Scripts\python.exe -m coastsnap_import.derivatives `
  --manifest "$staging\manifests\TEST_ROOT_ID.json" --input-root $staging `
  --output-root "$staging\derivatives-out" --index-output "$staging\derivatives-out\derivatives-index.json"

# FastAPI (second terminal, with $staging set there too)
cd apps\api
$env:COASTSNAP_SITE_REGISTRY_PATH = "tests/fixtures/coastsnap/sites-registry.json"
$env:COASTSNAP_MANIFEST_PATH = "$staging\manifests\TEST_ROOT_ID.json"
$env:COASTSNAP_DERIVATIVES_INDEX_PATH = "$staging\derivatives-out\derivatives-index.json"
$env:COASTSNAP_MEDIA_ROOT = $staging
$env:COASTSNAP_DERIVATIVES_ROOT = "$staging\derivatives-out"
$env:AUSCIN_MEDIA_BASE_URL = "http://127.0.0.1:8000"
.\.venv\Scripts\python.exe -m uvicorn auscin_api.main:create_app --factory --host 127.0.0.1 --port 8000

# Next.js (third terminal), then open http://localhost:3000/coastsnap
cd apps\web
$env:COASTSNAP_API_BASE_URL = "http://127.0.0.1:8000"
npm run dev

# Verify both downloads against the manifest: each hash must equal that entry's
# level0.checksum.sha256 / level1.checksum.sha256 (also published as
# level0ChecksumSha256 / level1ChecksumSha256). Take a mediaId from
# http://127.0.0.1:8000/api/v1/coastsnap/sites/CS-TEST-SITE/observations
$id = "<mediaId>"
Invoke-WebRequest "http://127.0.0.1:8000/media/coastsnap/$id/level0" -OutFile "$staging\download-level0.jpg"
Invoke-WebRequest "http://127.0.0.1:8000/media/coastsnap/$id/level1" -OutFile "$staging\download-level1.jpg"
(Get-FileHash "$staging\download-level0.jpg" -Algorithm SHA256).Hash.ToLower()
(Get-FileHash "$staging\download-level1.jpg" -Algorithm SHA256).Hash.ToLower()

# Clean up: stop both servers first
Remove-Item -Recurse -Force $staging
```

### Moving to the real test site

The full, step-by-step runbook is
[`docs/implementation/coastsnap-real-site-staging.md`](../../docs/implementation/coastsnap-real-site-staging.md).
It covers the steps from worker preflight to the reviewed SFTP transfer. It
is driven by one env file created from `config/coastsnap-site.env.example`
and kept outside the repository. Two offline commands support it:

- `python -m auscin_api.site_config validate --env-file <file> [--for-transfer]`
  refuses any of the following:
  - unset or blank values, and unresolved `<...>` placeholders
  - an invalid slug or root ID, out-of-range coordinates, or an invalid time
    zone or date
  - a missing explicit publication decision, or a missing explicit
    `COASTSNAP_SITE_LEVEL0_DOWNLOAD_PERMITTED` /
    `COASTSNAP_SITE_LEVEL1_DOWNLOAD_PERMITTED` decision (the retired single
    `COASTSNAP_SITE_DOWNLOAD_PERMITTED` is refused)
  - local paths inside the repository or under `/g/data`
  - a manifest path that isn't the worker's default

  It never contacts Spotteron, Gadi or NCI.
- `python -m auscin_api.site_config write-registry --env-file <file> --output <outside-repo>/site-registry.json`
  writes the reviewed one-site registry (`is_synthetic: false`) from those
  values only. Nothing defaults to public or downloadable.

In outline, once the project owner supplies the real values:

1. **Worker.** Run `--process-local` for `<SPOTTERON_ROOT_ID>` into a staging
   directory on the Nectar VM, then run the derivatives command against it.
   See `apps/worker/README.md`.
2. **Registry.** Add a reviewed entry to a real site registry, never
   committed with real values:
   - `site_id: "<COASTSNAP_SITE_SLUG>"`
   - `spotteron_root_id: "<SPOTTERON_ROOT_ID>"`
   - real name, region, coordinates, description and time zone
   - `publication_status`
   - `level0_download_permitted` and `level1_download_permitted`, each set
     deliberately
   - licence and attribution text, once decided
3. **Media roots.** Point `COASTSNAP_MEDIA_ROOT` / `COASTSNAP_DERIVATIVES_ROOT`
   at local, read-only published copies. Serving directly from
   `<NCI_PUBLICATION_ROOT>` is out of scope until the NCI serving option in
   the implementation note (section 5) is agreed. Paths under `/g/data`
   are refused outside `AUSCIN_API_ENV=production`.

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

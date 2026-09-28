# Implementation note: one real CoastSnap site, viewable and downloadable

Status: **in progress.** Date: 2026-09-28.

- Sequencing step 1 (fixture-backed JSON catalogue) is implemented in
  `apps/api` — see `apps/api/README.md`. It differs from the proposal below in
  three ways:
  - `media_id` is a hash-derived opaque ID (`csm_…`), not
    `<site_id>-<observation_id>`.
  - The date-range endpoint returns `null`s, not 404, for a public site with
    no observations.
  - Unmatched routes also return the controlled error shape.
- Step 2 (local media delivery) is implemented: a `LocalMediaStore`, the
  `/media/coastsnap/{media_id}/original|preview|thumbnail` endpoints, and a
  per-site `original_download_permitted` registry flag.
  - `original` serves Level 1. This is **provisional** until the Level 0 vs
    Level 1 decision is made.
  - Derivatives come from a provisional derivatives index until worker step 3
    exists.
  - HTTP Range requests are supported natively by Starlette's `FileResponse`.
- Steps 3–6 are not started.

## Objective

Make one real CoastSnap test site (one Spotteron `root_id`) browsable in the
existing `/coastsnap` pages, with thumbnails, previews, metadata and a
permitted original-file download, served through a minimal FastAPI catalogue.

Placeholders used throughout (never commit real values):

| Placeholder | Meaning |
|---|---|
| `<SPOTTERON_ROOT_ID>` | Real Spotteron root ID for the test site |
| `<NCI_PUBLICATION_ROOT>` | Published NCI directory the worker transfers into (production only) |
| `<COASTSNAP_SITE_SLUG>` | Human-legible AusCIN site ID, e.g. `CS-EXAMPLE` |

Out of scope: PostgreSQL, Redis, Docker, multi-site ingestion, scheduling,
video, auth/embargo workflows, any access to `/g/data/qu34` from a dev machine.

---

## 1. Existing worker outputs and manifest structure

`apps/worker/coastsnap_import` (`--preflight`, `--plan-only`,
`--process-local`, `--transfer`) produces, under `COASTSNAP_STAGING_DIR`
locally and mirrored under `remote_root` on Gadi:

```
level-0/root-<root_id>/<yyyy>/<mm>/<dd>/images/<observation_id>.<ext>   # byte-for-byte original
level-1/root-<root_id>/<yyyy>/<mm>/<dd>/images/<observation_id>.<ext>   # copy + embedded XMP
metadata/source-records/sites/<root_id>.json                           # raw Spotteron (staging only)
metadata/source-records/observations/<observation_id>.json             # raw Spotteron (staging only)
manifests/<root_id>.json                                               # default --manifest path
```

Manifest (`models.py`, `schema_version: 1`):

- `Manifest`: `run_id`, `root_id`, `topic_id`, `date_from_utc`, `date_to_utc`,
  `generated_at_utc`, `remote_root`, `entries[]`.
- `ManifestEntry`:
  - `site: SourceSite` — only `root_id` is populated; `name`/lat/lon are `None`
    (no confirmed Spotteron site resource).
  - `observation: SourceObservation` — `observation_id`, `spotted_at_raw`,
    `spotted_at_utc` (source TZ is an **assumption**, default `UTC`), lat/lon,
    `image_url`, `media_reference`, `contributor_display_name`,
    `contributor_attribution_permitted` (defaults `False`).
  - `level0` / `level1` — `product_id` (`<obs>-L0`/`<obs>-L1`),
    `local_relative_path`, `remote_relative_path`, `file_size_bytes`,
    `content_type` (L0), `checksum.sha256`, processing details (L1).
  - `level0_transfer` / `level1_transfer` — `TransferResult` with `state`
    (`verified`/`skipped_existing` = published).
- Every path in the manifest is **relative**; no absolute host paths.

Gaps relevant to publication:

1. **No thumbnails or previews.** The worker only produces L0/L1 originals.
   AGENTS.md requires gallery cards to use thumbnails and detail pages to use
   browser-sized previews.
2. **No width/height** recorded (optional in the frontend type, so not blocking).
3. **No site display metadata** (name, state, region, description, coordinates).
4. **No publication status / licence** — nothing says the site is approved
   for public release.
5. `manifest.remote_root` in `--process-local` runs is the configured default
   (currently under `/g/data/qu34`), which is informational only; it must not
   be treated as a readable path by the API.

## 2. Existing CoastSnap frontend data boundary

- Types: `apps/web/data/types/coastsnap.ts` (`CoastSnapSite`,
  `CoastSnapObservation`) — already has fields for `spotteronSiteId`,
  `spotteronObservationId`, `spotteronMediaId`, `sourceUrl`,
  `checksumSha256`, `isOriginalAvailable`, `originalUrl`, `isSynthetic`.
- Boundary: `CoastSnapRepository` in `apps/web/data/coastsnap-repository.ts`,
  async, with a single exported instance `coastSnapRepository` backed by
  `SampleCoastSnapRepository` (sample data in `data/sample/coastsnap-*.ts`).
- Pages (`app/coastsnap/page.tsx`, `[siteId]/page.tsx`,
  `[siteId]/archive/page.tsx`, `[siteId]/archive/[mediaId]/page.tsx`) only
  talk to `coastSnapRepository` — they never import sample data directly.
- Pagination is offset-based (`PaginatedResult`: `page`, `pageSize`, `total`).
- Images render through `next/image` (`ObservationThumbnail`, `ImageCard`,
  detail page). Current sources are same-origin `/sample-media/*.svg`.
- Download UI already exists on the detail page but is labelled
  "prototype demo"; `lib/media-access.ts` already models
  `original-available` / `restricted` / `unavailable-prototype`.

This boundary is the right seam: a new HTTP-backed repository implementing
the same interface lets the pages stay essentially unchanged.

## 3. Proposed FastAPI catalogue boundary (`apps/api`)

Deliberately minimal: read-only, no database, catalogue loaded from
worker manifests + a reviewed site registry at startup.

### Inputs

- **Site registry** (`COASTSNAP_SITE_REGISTRY_PATH`, JSON, reviewed by a
  human; example committed as `apps/api/config/coastsnap-sites.example.json`):
  `site_id` (`<COASTSNAP_SITE_SLUG>`), `spotteron_root_id`
  (`<SPOTTERON_ROOT_ID>`), name, state, region, description, lat/lon,
  `display_time_zone`, `publication_status`, `licence`, `attribution_text`,
  `manifest_relative_path`. **Only sites listed here, with
  `publication_status: "public"`, are exposed** — a manifest existing on disk
  never publishes anything by itself.
- **Media root** (`COASTSNAP_MEDIA_ROOT`): the directory the manifest's
  relative paths resolve against (staging dir locally,
  `<NCI_PUBLICATION_ROOT>` mount in production).
- **Derivatives root** (`COASTSNAP_DERIVATIVES_ROOT`): thumbnails/previews
  (see §4/§5).

### Catalogue rules

- Include an entry only if it has `level1` (and, in production mode,
  `level1_transfer.state ∈ {verified, skipped_existing}`), a non-null
  `spotted_at_utc`, and its SHA-256 checksum is present.
- Opaque media ID: `<site_id>-<observation_id>` (observation IDs are Spotteron
  numeric IDs, validated as `^[0-9]+$` at load time).
- Contributor name only shown if `contributor_attribution_permitted` is true;
  otherwise the registry's generic `attribution_text`.
- Path safety: every file served is `media_root / relative_path`, then
  `resolve()` and required to be inside `media_root.resolve()`
  (`Path.is_relative_to`); paths are never accepted from the request.

### Endpoints (JSON shaped to match `CoastSnapSite` / `CoastSnapObservation`)

| Method + path | Returns |
|---|---|
| `GET /api/v1/health` | Liveness + catalogue load status (counts only, no paths) |
| `GET /api/v1/coastsnap/sites` | `CoastSnapSite[]` |
| `GET /api/v1/coastsnap/sites/{site_id}` | `CoastSnapSite` or 404 |
| `GET /api/v1/coastsnap/sites/{site_id}/observations?date_from&date_to&time_of_day&contributor&page&page_size` | `PaginatedResult<CoastSnapObservation>` (validated query params, `page_size ≤ 100`) |
| `GET /api/v1/coastsnap/sites/{site_id}/observations/{media_id}` | `CoastSnapObservation` or 404 (site-scoped) |
| `GET /api/v1/coastsnap/sites/{site_id}/date-range` | `{earliest, latest}` or 404 |
| `GET /api/v1/coastsnap/latest` | latest observation per site |
| `GET /media/coastsnap/{media_id}/thumbnail` | JPEG thumbnail |
| `GET /media/coastsnap/{media_id}/preview` | JPEG preview |
| `GET /media/coastsnap/{media_id}/original` | Level 1 file, `Content-Disposition: attachment`, `ETag` = sha256, Range support |

Offset pagination is kept for now to match the existing `PaginatedResult`
contract; cursor pagination is a documented follow-up once archives grow.

Filtering logic mirrors `data/coastsnap-queries.ts`; the API is a separate
implementation, so both sides get tests over the same fixtures.

### Which file is the "original" download?

Proposed default: **Level 1** (identical image bytes, plus AusCIN provenance
XMP). Level 0 stays archival and is not exposed in this iteration. This is a
decision for the project owner — see open questions.

## 4. Local development data strategy

- Never read Gadi or `/g/data/qu34`. The API refuses to start if
  `COASTSNAP_MEDIA_ROOT` starts with `/g/data` unless
  `AUSCIN_ENV=production` (defence in depth, same idea as the worker's
  `--confirm-production-remote-root`).
- Two local modes:
  1. **Fixture mode (default, committed):** a tiny synthetic manifest under
     `apps/api/tests/fixtures/` referencing generated placeholder JPEGs created
     in a temp dir at test time — no real photos in Git. Used by pytest and by
     anyone without a real staging run.
  2. **Real-site mode (developer machine only):** run the existing worker
     `--process-local --root-id <SPOTTERON_ROOT_ID> --max-images <small>`
     into a staging dir **outside the repo**, run the new derivatives command
     over it, then point `COASTSNAP_MEDIA_ROOT` / `COASTSNAP_DERIVATIVES_ROOT`
     / `COASTSNAP_SITE_REGISTRY_PATH` at it via `apps/api/.env` (git-ignored).
- Frontend: `COASTSNAP_API_BASE_URL` (server-side env, in
  `apps/web/.env.local`). **Unset → current sample repository, unchanged.**
  Set → `HttpCoastSnapRepository`. This keeps the prototype working with zero
  setup.
- Thumbnails/previews: a new, separate worker step
  (`python -m coastsnap_import.derivatives --manifest ... --output-root ...`)
  reads Level 1, writes `thumb/…_400.jpg` and `preview/…_1600.jpg` plus a small
  derivatives index (dimensions, checksums). Uses Pillow (new dependency).
  It never modifies L0/L1 and does not change any existing CLI mode.
- The existing `test-coastsnap.jpg` and `tools/` in the repo root are
  untracked; the plan does not depend on them and they should stay uncommitted
  (or `tools/` be committed separately if intended).

## 5. Nectar / NCI production data strategy

- Worker (already built) runs on the Nectar VM: `--transfer` to
  `<NCI_PUBLICATION_ROOT>` after explicit confirmation; manifest is the
  record of what is verified on Gadi.
- The API runs on the Nirin/Nectar VM, **not** on Gadi. It needs read-only
  access to the published files. Options, in order of preference — **must be
  confirmed with NCI**:
  1. Serve originals from an NCI public HTTP endpoint (e.g. THREDDS/fileserver
     over `<NCI_PUBLICATION_ROOT>`) and have `/media/.../original` return a
     `302` to it — no bulk bytes through the VM.
  2. A read-only mount of `<NCI_PUBLICATION_ROOT>` on the VM (if NCI permits).
  3. Keep a VM-local, read-only published copy of Level 1 produced by the
     worker alongside the transfer (simplest for one test site; duplicates
     storage).
  The API hides this behind a small `MediaStore` interface
  (`LocalFileMediaStore`, later `RedirectMediaStore`) so the choice doesn't
  change the HTTP contract.
- Thumbnails/previews are generated on the Nectar VM from staged Level 1 before
  or alongside transfer, and served from VM-local disk (small, cacheable).
- The site stays hidden until the registry entry is set to `public` by a
  human; the manifest's `site.name`, coordinates etc. are never guessed.
- Nginx in front of the API for TLS and range/caching is expected later
  (not part of this change).

## 6. Files to be added or changed

### Added

```
docs/implementation/coastsnap-single-site-publication.md   # this note
apps/api/pyproject.toml                                    # fastapi, uvicorn, pydantic; pytest, httpx (dev)
apps/api/.env.example                                      # names only
apps/api/README.md
apps/api/config/coastsnap-sites.example.json               # placeholders only
apps/api/auscin_api/__init__.py
apps/api/auscin_api/main.py                                # app factory, routers, CORS off by default
apps/api/auscin_api/settings.py                            # env config, /g/data guard
apps/api/auscin_api/catalogue.py                           # manifest + registry -> in-memory catalogue
apps/api/auscin_api/schemas.py                             # response models mirroring coastsnap.ts
apps/api/auscin_api/media_store.py                         # safe path resolution, file responses
apps/api/auscin_api/routes/coastsnap.py
apps/api/auscin_api/routes/media.py
apps/api/tests/conftest.py                                 # builds temp media root + fixture JPEGs
apps/api/tests/fixtures/manifest_single_site.json
apps/api/tests/fixtures/sites_registry.json
apps/api/tests/test_catalogue.py
apps/api/tests/test_routes_coastsnap.py
apps/api/tests/test_media_paths.py                         # traversal, unknown IDs, non-public sites
apps/worker/coastsnap_import/derivatives.py                # thumbnail/preview step (new, separate command)
apps/worker/tests/test_derivatives.py
apps/web/data/coastsnap-http-repository.ts                 # CoastSnapRepository over fetch
apps/web/data/coastsnap-http-repository.test.ts
```

### Changed

```
apps/web/data/coastsnap-repository.ts   # select sample vs HTTP repository from COASTSNAP_API_BASE_URL
apps/web/.env.example                   # add COASTSNAP_API_BASE_URL
apps/web/next.config.ts                 # images.remotePatterns for the API media host (from env)
apps/web/app/coastsnap/[siteId]/archive/[mediaId]/page.tsx
                                        # download label: "Download original" for real records,
                                        # keep "(prototype demo)" wording only when isSynthetic
apps/web/app/coastsnap/[siteId]/page.tsx
                                        # download explanation text conditional on isSynthetic
apps/worker/pyproject.toml              # add Pillow (derivatives step only)
apps/worker/README.md                   # document the derivatives step
.gitignore                              # apps/api staging/derivative dirs, apps/api/.env
.claude/launch.json                     # optional "api" configuration (uvicorn)
```

Not changed: existing worker modes, manifest schema (v1), sample data,
station/camera pages, the `CoastSnapRepository` interface.

## Proposed sequencing (one coherent change each)

1. `apps/api` skeleton + catalogue + JSON endpoints + tests (fixture mode).
2. Media endpoints with path safety + Range + tests.
3. Worker derivatives step + tests.
4. Frontend `HttpCoastSnapRepository` behind env var + UI copy tweaks; verify in
   browser at desktop and mobile widths against both sample and API modes.
5. Local end-to-end with a real `<SPOTTERON_ROOT_ID>` staged outside the repo.
6. Production storage option agreed with NCI, then Nectar deployment.

## Open questions / assumptions

- **Download product:** Level 1 (proposed) or Level 0?
- **Licence and attribution** text for the test site, and whether contributor
  names may be shown at all.
- **Spotteron source timezone** is still assumed UTC; displayed capture times
  are only as correct as that assumption. The UI should label the time zone.
- **NCI serving path** (§5) — which option NCI supports for the VM.
- **Site metadata** (name, region, coordinates, description) must be supplied
  by the project owner for the registry.
- Offset pagination retained for now; cursor pagination deferred.

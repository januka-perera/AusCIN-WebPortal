# CoastSnap importer release checklist

Work through this before every push to the Nectar VM and before the
first real `--transfer` run. See [README.md](README.md) for full detail
behind each step. Nothing here requires or performs a Gadi connection
except the final, clearly-marked transfer-readiness section.

## 1. Automated tests

```bash
cd apps/worker
source .venv/bin/activate   # or: .venv\Scripts\activate on Windows
pip install -e ".[dev]"
pytest -q
```

- [ ] All worker tests pass (no Spotteron/Gadi network call is made by
      any test — HTTP is mocked with `responses`, SFTP/SSH is faked
      in-memory).
- [ ] If frontend code under `apps/web` was also touched in this
      change, additionally run `npm run lint`, `npm test`, and
      `npm run build` from `apps/web` and confirm they pass.

## 2. Preflight (environment) check

```bash
python -m coastsnap_import.cli --preflight
```

- [ ] Every check prints `[PASS]`.
- [ ] If any check fails, fix it and rerun before continuing — do not
      skip ahead to a process-local run with a failing preflight.

## 3. Process-local import (one real image)

```bash
python -m coastsnap_import.cli \
  --root-id <REAL_ROOT_ID> \
  --date-from 2026-08-23T00:00:00Z \
  --date-to 2026-09-23T00:00:00Z \
  --max-images 1 \
  --process-local \
  --staging-dir "$HOME/auscin-staging"
```

Replace `<REAL_ROOT_ID>` with a real Spotteron `root_id` and adjust the
date range to one you expect to contain at least one observation. This
makes real Spotteron requests and downloads one real image, but never
contacts Gadi.

- [ ] Exit code is `0` and the summary line shows `failed=0`.
- [ ] If `failed>0`, see README's "Identifying failed records" before
      proceeding.

### Expected output files

Under `--staging-dir`:

- [ ] `level-0/root-<root-id>/<yyyy>/<mm>/<dd>/images/<id>.<ext>` — the
      original file, byte-for-byte.
- [ ] `level-1/root-<root-id>/<yyyy>/<mm>/<dd>/images/<id>.<ext>` — a
      copy with approved metadata embedded.
- [ ] `metadata/source-records/observations/<id>.json` — the full raw
      Spotteron record for this observation.
- [ ] `metadata/source-records/sites/<root-id>.json` — the (synthetic,
      parameters-only) site record.
- [ ] `manifests/<root-id>.json` — the run manifest.

### Checksum verification

```bash
sha256sum "$HOME/auscin-staging/level-0/root-<root-id>/<yyyy>/<mm>/<dd>/images/<id>.<ext>"
sha256sum "$HOME/auscin-staging/level-1/root-<root-id>/<yyyy>/<mm>/<dd>/images/<id>.<ext>"
```

- [ ] Both checksums match what's recorded in the manifest
      (`level0.checksum.sha256` / `level1.checksum.sha256`).
- [ ] The two checksums are **different** from each other (Level 1 has
      metadata embedded; Level 0 does not).
- [ ] `level0.file_size_bytes` in the manifest matches the actual file
      size on disk.

### XMP inspection

```bash
exiftool -config coastsnap_import/exiftool_config/auscin.config -a -G1 -s \
  "$HOME/auscin-staging/level-1/root-<root-id>/<yyyy>/<mm>/<dd>/images/<id>.<ext>" \
  | grep -E "auscin|XMP-dc|XMP-photoshop|XMP-xmp|GPS|DateTimeOriginal"
```

- [ ] `[XMP-auscin] SourcePlatform`, `SpotteronRootId`,
      `SpotteronObservationId` are present and correct.
- [ ] No token, password, private key, internal filesystem path, or
      private contributor detail appears anywhere in the output.
- [ ] Level 0 has **no** `XMP-auscin:*` tags at all:
      `exiftool -config coastsnap_import/exiftool_config/auscin.config -XMP-auscin:all <level-0-file>`
      prints nothing.

### Manifest inspection

```bash
python -m json.tool "$HOME/auscin-staging/manifests/<root-id>.json"
```

- [ ] `entries[].observation.root_id`, `.observation_id` match what
      was requested.
- [ ] `entries[].observation.media_reference` matches the source
      record's `attributes.image` exactly, and `.image_url` is built
      from that same reference — neither is null unless the source
      record truly omitted `attributes.image`.
- [ ] `entries[].observation.spotted_at_raw` and `.spotted_at_utc` are
      both present (raw source value alongside the normalised UTC
      value — see README's "Timestamp interpretation policy").
- [ ] `entries[].observation.latitude`/`.longitude` are present when
      the source record had them.
- [ ] No manifest path is absolute; every `*_relative_path` field is
      relative.
- [ ] No full raw Spotteron JSON is duplicated inside the manifest
      entry itself (it lives only under `metadata/source-records/`).
- [ ] `entries[].level0_transfer`/`.level1_transfer` are `null` (this
      was `--process-local`, not `--transfer`).

## 4. Security checks

- [ ] `git status` / `git diff` show no `.env` file, no private key
      file, and no bearer token value added anywhere.
- [ ] No file under `apps/worker/` contains a real hostname, username,
      or path that should stay private (grep the diff for `GADI_`,
      `SPOTTERON_BEARER_TOKEN`, and any real IP/hostname).
- [ ] `.gitignore` still excludes `apps/worker/**/*.jpg` etc., `.venv/`,
      `.staging/` — confirm with `git status --short` that no generated
      Level 0/1 file, manifest, or source record from a test run is
      staged.
- [ ] The SSH private key file used for `--transfer` (once that stage
      is reached) has restrictive permissions (`chmod 600`) and lives
      outside the git checkout.

## 5. Confirm nothing generated or secret is committed

```bash
git status
git diff --stat
git add -n .
```

- [ ] `git add -n .` (dry run) lists only source, test, fixture,
      documentation, and config-template changes you intend to commit
      — no raw images, no `.env`, no manifests, no staged output.
- [ ] Re-run the full [Section 1](#1-automated-tests) test suite one
      more time after any last-minute edit.

## 6. First manual Nectar VM test

Follow README.md's ["Nectar VM deployment
procedure"](README.md#nectar-vm-deployment-procedure-step-by-step) in
full, in order, on the actual Nectar VM — not just in local
development. In particular:

- [ ] Steps 1–8 (Python/ExifTool install, clone, venv, install,
      staging directory, `.env`, Spotteron config) are done on the VM
      itself, not copied from a local `.venv`.
- [ ] `--preflight` (step 9) passes on the VM.
- [ ] The one-image `--process-local` run (step 10) succeeds on the VM
      against the real Spotteron API.
- [ ] Steps 11–12 (inspect, then clean up) are done before declaring
      the VM ready.
- [ ] **`--transfer` is not run** as part of this checklist. It
      remains out of scope until the Gadi destination
      (`GADI_SFTP_HOST`/`GADI_SFTP_USERNAME`/`GADI_SFTP_PRIVATE_KEY_PATH`/
      `GADI_REMOTE_ROOT`) has been explicitly reviewed and approved
      separately, and the first `--transfer` attempt should target a
      non-production `GADI_REMOTE_ROOT` before anything under
      `/g/data/qu34` is ever touched.

# CoastSnap importer (apps/worker)

A single-site, single-run proof-of-concept importer: pulls observations
for one Spotteron `root_id` over one UTC date range, downloads the
original image (**Level 0**, byte-for-byte), creates a metadata-embedded
copy (**Level 1**, XMP via ExifTool), writes a JSON manifest, and —
only in `--transfer` mode, and only once explicitly configured —
uploads both to Gadi over SFTP.

This proof of concept never touches `/g/data/qu34` or Gadi from a local
development machine. It is intended to be run for real from the Nectar
VM, against a small, explicit date range and `--max-images` cap.

> **Do not run `--transfer` until the Gadi destination is explicitly
> configured** (`GADI_SFTP_HOST`, `GADI_SFTP_USERNAME`,
> `GADI_SFTP_PRIVATE_KEY_PATH`, and a reviewed `GADI_REMOTE_ROOT`). Every
> other mode (`--preflight`, `--plan-only`, `--process-local`) makes no
> Gadi connection at all — use those to validate everything else first.

## Runtime requirements (Ubuntu / Nectar)

| Requirement | Version / detail |
|---|---|
| Python | 3.11 or later (see `pyproject.toml`'s `requires-python`) |
| Python packages | `pydantic>=2,<3`, `requests>=2.31,<3`, `paramiko>=3.4,<4` (installed automatically by `pip install -e .`); `pytest>=8,<9` and `responses>=0.25,<1` for the dev/test extra only |
| ExifTool | Any recent version (developed against 13.x; the custom `XMP-auscin` namespace config only needs standard `-config` support, present in all modern releases) |
| Perl | Required by ExifTool itself (it's a Perl program) and by the `-config` file this project ships, which is Perl source. Ubuntu's `libimage-exiftool-perl` package pulls in a compatible Perl automatically — there is nothing to install separately on a standard Ubuntu/Nectar image. |
| Filesystem permissions | The account running the importer needs read/write access to the staging directory (create/write/delete files and subdirectories) and read access to this repository checkout. No elevated/root permissions are needed for `--plan-only`/`--process-local`. `--transfer` additionally needs the SSH private key file to be readable only by that account (standard `chmod 600`). |
| Recommended staging directory | `$HOME/coastsnap-staging` (or any path outside the git checkout — never commit staged files; see `.gitignore`) |
| Required environment variables | `SPOTTERON_BASE_URL`, `COASTSNAP_STAGING_DIR` at minimum — see [Configuration](#configuration) below |

## Installation

```bash
# 1. Clone/pull the repository, then from apps/worker:
cd apps/worker

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install the package (editable) with dev/test dependencies
pip install --upgrade pip
pip install -e ".[dev]"
```

### ExifTool installation (Ubuntu)

```bash
sudo apt update
sudo apt install -y libimage-exiftool-perl

# Confirm it's on PATH and check the version:
exiftool -ver
```

If your environment cannot use `apt` (e.g. a restricted Nectar image),
download a release tarball from the [ExifTool site](https://exiftool.org/)
and point `EXIFTOOL_PATH` at the extracted `exiftool` script instead of
relying on PATH.

## Configuration

Copy `.env.example` and fill in real values (never commit the result):

```bash
cp .env.example .env
# edit .env, then export it into your shell, e.g.:
set -a; source .env; set +a
```

At minimum, for `--plan-only`/`--process-local`:

- `SPOTTERON_BASE_URL` — e.g. `https://www.spotteron.com`
- `COASTSNAP_STAGING_DIR` — e.g. `$HOME/coastsnap-staging`

Optional but commonly set:

- `SPOTTERON_BEARER_TOKEN` — only if you have one; public GET works without it
- `SPOTTERON_TOPIC_ID` — defaults to `37`
- `EXIFTOOL_PATH` — only if `exiftool` isn't on PATH

Only required for `--transfer` (do not set these until you're actually
ready to transfer to Gadi):

- `GADI_SFTP_HOST`, `GADI_SFTP_USERNAME`, `GADI_SFTP_PRIVATE_KEY_PATH`
- `GADI_REMOTE_ROOT` (defaults to `/g/data/qu34/AusCIN/coastsnap-test`)
- `GADI_CHECKSUM_STRATEGY` — `ssh-exec` (default) or `read-back` if the
  remote host has no `sha256sum` on PATH

See `.env.example` for the complete, documented list — it never contains
real values, only variable names.

## Preflight check

Before a real run, verify the environment without touching Gadi or
downloading any image:

```bash
python -m coastsnap_import.cli --preflight
```

This checks: Python version, required Python packages, ExifTool
availability/version, that the `XMP-auscin` namespace config loads
without error, that the staging directory is writable with enough free
space, and that the configured Spotteron API host is reachable (one
bounded metadata request, `limit=1`). It prints `[PASS]`/`[FAIL]` per
check and exits non-zero if anything fails.

## Running a local process-only import

This downloads real images and writes real local files, but makes no
Gadi connection at all:

```bash
python -m coastsnap_import.cli \
  --root-id <REAL_ROOT_ID> \
  --date-from 2026-08-23T00:00:00Z \
  --date-to 2026-09-23T00:00:00Z \
  --max-images 1 \
  --process-local \
  --staging-dir "$HOME/coastsnap-staging"
```

`--date-from`/`--date-to` accept either a bare UTC date (`YYYY-MM-DD`)
or a full ISO-8601 UTC timestamp as shown above. Start with
`--max-images 1` for the first real run against a site.

If you'd rather see what *would* be processed without downloading
anything, use `--plan-only` (the default mode if no mode flag is
given) instead of `--process-local`.

## Inspecting the results

### Level 0 and Level 1 files

Both live under the staging directory, partitioned by site/date:

```bash
find "$HOME/coastsnap-staging/level-0" -type f
find "$HOME/coastsnap-staging/level-1" -type f

# Level 0 must be byte-identical to what was downloaded; Level 1 is a
# copy with metadata embedded — confirm they differ only in metadata,
# not in image content, by comparing sizes/hashes:
sha256sum "$HOME/coastsnap-staging/level-0/<root-id>/<yyyy>/<mm>/<dd>/images/<id>.jpg"
sha256sum "$HOME/coastsnap-staging/level-1/<root-id>/<yyyy>/<mm>/<dd>/images/<id>.jpg"
```

### Embedded XMP metadata (Level 1 only)

Use `-a -G1 -s` (list every tag, grouped by family, short names) rather
than `-XMP-all` — the latter does not reliably expand this project's
user-defined `XMP-auscin` namespace:

```bash
exiftool -config coastsnap_import/exiftool_config/auscin.config -a -G1 -s \
  "$HOME/coastsnap-staging/level-1/<root-id>/<yyyy>/<mm>/<dd>/images/<id>.jpg" | grep -E "auscin|XMP-dc|XMP-photoshop|XMP-xmp|GPS|DateTimeOriginal"
```

Verified against a real live image (2026-09-23): this prints
`[XMP-auscin] SourcePlatform`, `SpotteronRootId`,
`SpotteronObservationId` (and `SpotteronMediaReference` when present),
`[XMP-dc] Source`, `[XMP-photoshop] DateCreated`, `[XMP-xmp] CreatorTool`,
and `[ExifIFD] DateTimeOriginal`/GPS tags when latitude/longitude were
available — and nothing else: no tokens, paths, or private contributor
details, by construction (see `metadata_embedder.py`'s `MetadataFields`
whitelist).

Level 0 should have **no** embedded AusCIN/XMP metadata at all — only
whatever the original file already contained:

```bash
exiftool -config coastsnap_import/exiftool_config/auscin.config -XMP-auscin:all \
  "$HOME/coastsnap-staging/level-0/<root-id>/<yyyy>/<mm>/<dd>/images/<id>.jpg"
```

### The manifest

```bash
cat "$HOME/coastsnap-staging/manifests/<root-id>.json" | python -m json.tool
```

Each entry records the observation, the site, relative Level 0/Level 1
paths and checksums, processing details, and (once transferred) transfer
state — never an absolute filesystem path, and never the full raw
Spotteron record (that's preserved separately under
`metadata/source-records/`).

### Raw source records

```bash
cat "$HOME/coastsnap-staging/metadata/source-records/observations/<id>.json"
```

## Run modes, in full

| Flag | Fetches metadata | Downloads images | Writes local files | Connects to Gadi |
|---|---|---|---|---|
| `--preflight` | one bounded check request | never | never | never |
| `--plan-only` (default) | yes | never | never | never |
| `--process-local` | yes | yes | yes (Level 0/1, manifest, source records) | never |
| `--transfer` | yes | yes | yes | **yes** — requires `GADI_SFTP_*` configuration |

`--delete-after-success` always exits with an error: deletion is not
implemented in this version, so the flag is rejected rather than
silently accepted and ignored.

## Tests and linting

```bash
pip install -e ".[dev]"
pytest -q
```

No test in this suite makes a real Spotteron or Gadi network call —
HTTP is mocked with `responses`, and SFTP/SSH is faked in-memory. There
is no separate lint tool configured for this package yet.

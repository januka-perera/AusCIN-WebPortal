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

## Nectar VM deployment procedure (step by step)

This is the exact procedure for the first manual run on the Ubuntu
Nectar VM. Each step links to the fuller detail below. Use
`$HOME/auscin-staging` as the staging directory throughout — never a
path inside the git checkout.

1. **Install Python 3.11 or newer** — `python3 --version`; if older,
   install a newer Python via your distribution's usual mechanism
   (e.g. `sudo apt install python3.11 python3.11-venv`).
2. **Install ExifTool and Perl** — see [ExifTool installation (Ubuntu)](#exiftool-installation-ubuntu)
   below (`sudo apt install -y libimage-exiftool-perl`; Perl comes with it).
3. **Clone or copy the repository** onto the Nectar VM, e.g.
   `git clone <repo-url> && cd AusCIN-WebPortal/apps/worker`.
4. **Create a virtual environment** — see [Installation](#installation)
   below (`python3 -m venv .venv && source .venv/bin/activate`).
5. **Install the worker** — `pip install --upgrade pip && pip install -e ".[dev]"`.
6. **Create a staging directory outside the git checkout**:
   ```bash
   mkdir -p "$HOME/auscin-staging"
   ```
7. **Create a `.env` file from `.env.example`** — see [Configuration](#configuration)
   below (`cp .env.example .env`, then edit it; never commit `.env`).
8. **Configure Spotteron public API access** — at minimum set
   `SPOTTERON_BASE_URL=https://www.spotteron.com` and
   `COASTSNAP_STAGING_DIR="$HOME/auscin-staging"` in `.env`, then load it:
   `set -a; source .env; set +a`. Leave every `GADI_*` variable unset for now.
9. **Run preflight** — see [Preflight check](#preflight-check) below:
   ```bash
   python -m coastsnap_import.cli --preflight
   ```
   Do not continue until every check prints `[PASS]`.
10. **Run a one-image process-local import** — see [Running a local
    process-only import](#running-a-local-process-only-import) below,
    using a real `root_id` and `--max-images 1`.
11. **Inspect the output** — see [Inspecting the results](#inspecting-the-results)
    below: Level 0/Level 1 checksums, embedded XMP metadata, the
    manifest, and (if `processed=0`/`failed>0` was printed) [how to
    identify failed records](#identifying-failed-records).
12. **Clean up only after inspection** — see [Cleaning up](#cleaning-up-after-inspection)
    below. Do not delete the staging directory before you've actually
    looked at the files; there is no undo.

> `--transfer` is **not** part of this procedure. Do not run it until
> the Gadi destination is explicitly configured and reviewed — see the
> warning at the top of this document and [Run modes, in full](#run-modes-in-full).

## Runtime requirements (Ubuntu / Nectar)

| Requirement | Version / detail |
|---|---|
| Python | 3.11 or later (see `pyproject.toml`'s `requires-python`) |
| Python packages | `pydantic>=2,<3`, `requests>=2.31,<3`, `paramiko>=3.4,<4` (installed automatically by `pip install -e .`); `pytest>=8,<9` and `responses>=0.25,<1` for the dev/test extra only |
| ExifTool | Any recent version (developed against 13.x; the custom `XMP-auscin` namespace config only needs standard `-config` support, present in all modern releases) |
| Perl | Required by ExifTool itself (it's a Perl program) and by the `-config` file this project ships, which is Perl source. Ubuntu's `libimage-exiftool-perl` package pulls in a compatible Perl automatically — there is nothing to install separately on a standard Ubuntu/Nectar image. |
| Filesystem permissions | The account running the importer needs read/write access to the staging directory (create/write/delete files and subdirectories) and read access to this repository checkout. No elevated/root permissions are needed for `--plan-only`/`--process-local`. `--transfer` additionally needs the SSH private key file to be readable only by that account (standard `chmod 600`). |
| Recommended staging directory | `$HOME/auscin-staging` (or any path outside the git checkout — never commit staged files; see `.gitignore`) |
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
- `COASTSNAP_STAGING_DIR` — e.g. `$HOME/auscin-staging`

Optional but commonly set:

- `SPOTTERON_BEARER_TOKEN` — only if you have one; public GET works without it
- `SPOTTERON_TOPIC_ID` — defaults to `37`
- `SPOTTERON_SOURCE_TIMEZONE` — defaults to `UTC`. The real Spotteron
  `spotted_at` value has **no timezone marker at all** (confirmed:
  `"2026-09-23 14:57:28"`). `UTC` is an explicit, documented
  *assumption*, not a confirmed fact — see [Timestamp interpretation
  policy](#timestamp-interpretation-policy) below before relying on it
  for anything time-sensitive.
- `EXIFTOOL_PATH` — only if `exiftool` isn't on PATH

Only required for `--transfer` (do not set these until you're actually
ready to transfer to Gadi):

- `GADI_SFTP_HOST`, `GADI_SFTP_USERNAME`, `GADI_SFTP_PRIVATE_KEY_PATH`
- `GADI_REMOTE_ROOT` (defaults to `/g/data/qu34/AusCIN/coastsnap-test` —
  see the warning below, this default is itself under production storage)
- `GADI_CHECKSUM_STRATEGY` — `ssh-exec` (default) or `read-back` if the
  remote host has no `sha256sum` on PATH

See `.env.example` for the complete, documented list — it never contains
real values, only variable names.

### Timestamp interpretation policy

Spotteron's real `attributes.spotted_at` value is timezone-less
(`"YYYY-MM-DD HH:MM:SS"`, confirmed live). This importer does not
silently assume that means UTC:

- If a `spotted_at` string ever carries an explicit offset (`Z` or
  `+HH:MM`), that offset is trusted directly.
- A timezone-less string (the confirmed real case) is interpreted in
  `SPOTTERON_SOURCE_TIMEZONE` (default `UTC`, an explicit assumption)
  before being converted to UTC for date filtering and the manifest.

Both the raw, unconverted string and the normalised UTC value are
always written to the manifest (`observation.spotted_at_raw` and
`observation.spotted_at_utc`), so the original source value stays
auditable regardless of which timezone was assumed. If you confirm the
real server-side convention (e.g. from Spotteron support, or by
comparing against the public CoastSnap web app's displayed times for a
known observation), set `SPOTTERON_SOURCE_TIMEZONE` to that IANA zone
name (e.g. `Australia/Brisbane`).

### Production remote root safety

`GADI_REMOTE_ROOT`'s default value is itself under `/g/data/qu34` (the
production NCI project storage). `--transfer` refuses to run against
**any** remote root starting with `/g/data/qu34` unless you also pass
`--confirm-production-remote-root`. Point `GADI_REMOTE_ROOT` at a
non-production test destination for routine testing, and only add
`--confirm-production-remote-root` once you deliberately mean to write
under `/g/data/qu34`.

## Preflight check

Before a real run, verify the environment without touching Gadi or
downloading any image:

```bash
python -m coastsnap_import.cli --preflight
```

This checks: Python version, required Python packages (with installed
versions), ExifTool availability/version, that the `XMP-auscin`
namespace config loads without error, that the staging directory is
writable with enough free space, that the configured Spotteron API
host is reachable (one bounded metadata request, `limit=1`), whether a
bearer token is configured (without ever printing its value), and
whether Gadi SFTP configuration is present (informational only — it's
irrelevant to `--plan-only`/`--process-local`, which never construct
an SFTP client regardless). It prints `[PASS]`/`[FAIL]` per check and
exits non-zero if anything fails.

## Deployment smoke test

`--preflight` (above) **is** this project's deployment smoke-test
command — there is no separate script. Run it once per environment
(a fresh Nectar VM, after a dependency upgrade, after moving the
staging directory) before trusting a real import to it:

```bash
python -m coastsnap_import.cli --preflight
```

| Check | What it proves |
|---|---|
| Python version | Meets `pyproject.toml`'s `requires-python >= 3.11` |
| Python package: pydantic / requests / paramiko | Installed, with version shown |
| ExifTool available | Resolvable on `PATH` (or at `EXIFTOOL_PATH`) |
| ExifTool version | The binary actually runs |
| ExifTool auscin namespace config | `exiftool_config/auscin.config` parses without a Perl syntax error |
| Staging directory writable | Can create/write/delete a file there |
| Staging directory disk space | Free space reported (informational floor: 100 MB) |
| Spotteron API reachable | One bounded `limit=1` metadata request succeeds (never an image, never Gadi) |
| Spotteron bearer token | Whether one is configured — never prints the value |
| Gadi SFTP configuration | Whether Gadi config is present — informational only; never blocks `--process-local` |

This smoke test never contacts Gadi and never downloads an image —
confirmed by `tests/test_preflight.py` and the CLI-integration tests
in `tests/test_cli.py`.

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
  --staging-dir "$HOME/auscin-staging"
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
find "$HOME/auscin-staging/level-0" -type f
find "$HOME/auscin-staging/level-1" -type f

# Level 0 must be byte-identical to what was downloaded; Level 1 is a
# copy with metadata embedded — confirm they differ only in metadata,
# not in image content, by comparing sizes/hashes:
sha256sum "$HOME/auscin-staging/level-0/root-<root-id>/<yyyy>/<mm>/<dd>/images/<id>.jpg"
sha256sum "$HOME/auscin-staging/level-1/root-<root-id>/<yyyy>/<mm>/<dd>/images/<id>.jpg"
```

### Embedded XMP metadata (Level 1 only)

Use `-a -G1 -s` (list every tag, grouped by family, short names) rather
than `-XMP-all` — the latter does not reliably expand this project's
user-defined `XMP-auscin` namespace:

```bash
exiftool -config coastsnap_import/exiftool_config/auscin.config -a -G1 -s \
  "$HOME/auscin-staging/level-1/root-<root-id>/<yyyy>/<mm>/<dd>/images/<id>.jpg" | grep -E "auscin|XMP-dc|XMP-photoshop|XMP-xmp|GPS|DateTimeOriginal"
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
  "$HOME/auscin-staging/level-0/root-<root-id>/<yyyy>/<mm>/<dd>/images/<id>.jpg"
```

### The manifest

```bash
cat "$HOME/auscin-staging/manifests/<root-id>.json" | python -m json.tool
```

Each entry records the observation, the site, relative Level 0/Level 1
paths and checksums, processing details, and (once transferred) transfer
state — never an absolute filesystem path, and never the full raw
Spotteron record (that's preserved separately under
`metadata/source-records/`).

### Raw source records

```bash
cat "$HOME/auscin-staging/metadata/source-records/observations/<id>.json"
```

### Identifying failed records

`cli.py` prints one line per observation while running (`[processed]`,
`[reused-local]`, `[skip]`, or `[error]` on stderr), and a summary line
at the end:

```
[error] <observation_id>: <reason>
...
Run complete: processed=<n> reused_local=<n> skipped_remote_verified=<n> failed=<n> manifest=<path>
```

- `processed` — Level 0 was (re)downloaded and/or Level 1 was
  (re)created this run: real local work happened.
- `reused_local` — both Level 0 and Level 1 already existed on disk
  with a checksum matching the manifest; nothing was downloaded or
  re-embedded.
- `skipped_remote_verified` — the manifest already recorded both
  transfers as verified; only ever non-zero after a prior `--transfer`
  run. Never used for local-only reuse — that's `reused_local`.
- `failed` — the observation raised an error and was not added/updated
  in the manifest.

A non-zero `failed` count (and a non-zero process exit code) means at
least one observation didn't make it into the manifest at all — check
the `[error]` lines above the summary for the reason (a common one:
`ImageUrlResolutionError`, if the image reference couldn't be
validated). A record that *is* in the manifest but has
`"level0_transfer": null`/`"level1_transfer": null` simply hasn't been
transferred yet (expected for `--process-local`) — that is not a
failure.

### Rerunning safely

Rerunning the exact same command is always safe and idempotent. A
`--process-local` rerun still does some real work every time (it
rewrites the raw source-record JSON, which is cheap, and re-validates
the image URL with one HTTP HEAD request per observation, to catch a
since-changed reference) — but the expensive work is skipped when
unnecessary:

- A local Level 0/Level 1 file whose on-disk SHA-256 still matches the
  manifest's recorded checksum is reused, not re-downloaded or
  re-embedded — reported as `reused_local`, independently for each of
  Level 0 and Level 1 (corrupting only one does not force the other to
  be redone).
- A local file that's missing or whose checksum no longer matches
  (e.g. it was corrupted or deleted) is transparently redownloaded/
  reprocessed — this is a clean redo, never a silent skip of bad data —
  and the observation is reported as `processed`, not `reused_local`.
- An observation whose transfer already reported `verified` in the
  manifest is never re-uploaded on a later `--transfer` rerun —
  reported as `skipped_remote_verified`, and the observation is not
  even revisited locally in that case.

There is no `--delete-after-success`: nothing is ever deleted
automatically, so a rerun can never destroy previous output.

### Cleaning up after inspection

Only remove staged files once you've actually inspected them (Level
0/1 checksums, XMP metadata, the manifest) — there is no undo:

```bash
rm -rf "$HOME/auscin-staging"
```

This deletes local files only. It never touches Gadi or
`/g/data/qu34` — there is no delete capability against the remote side
in this version at all (see `sftp_publisher.py`'s module docstring).

## Run modes, in full

| Flag | Fetches metadata | Downloads images | Writes local files | Connects to Gadi |
|---|---|---|---|---|
| `--preflight` | one bounded check request | never | never | never |
| `--plan-only` (default) | yes | never | never | never |
| `--process-local` | yes | yes | yes (Level 0/1, manifest, source records) | never |
| `--transfer` | yes | yes | yes | **yes** — requires `GADI_SFTP_HOST`, `GADI_SFTP_USERNAME`, `GADI_SFTP_PRIVATE_KEY_PATH`, `GADI_REMOTE_ROOT`, and `--confirm-production-remote-root` if that root is under `/g/data/qu34` |

`--delete-after-success` always exits with an error: deletion is not
implemented in this version, so the flag is rejected rather than
silently accepted and ignored.

`--process-local` and `--plan-only` never construct an SFTP client at
all, structurally — not merely "don't call" it — see `run()` in
`cli.py`, where `ParamikoSshSftpTransport`/`ParamikoReadBackSftpTransport`
are only ever instantiated inside the `mode is RunMode.TRANSFER` branch.

## Tests and linting

```bash
pip install -e ".[dev]"
pytest -q
```

No test in this suite makes a real Spotteron or Gadi network call —
HTTP is mocked with `responses`, and SFTP/SSH is faked in-memory. There
is no separate lint tool configured for this package yet.

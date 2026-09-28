# Operator runbook: first manual run on the Nectar VM (metadata only)

Status: **prepared, not run.**

This covers the first real-site session. It sets up the branch on the Nectar
VM, validates the site configuration offline, runs the worker preflight and
makes **one metadata-only `--plan-only` request**. Then it **stops** for human
review. No image is downloaded, no file is staged, and nothing is transferred.

Everything after the review (the capped `--process-local` import,
derivatives, the local catalogue preview, checksums and the reviewed SFTP
transfer) is in [`coastsnap-real-site-staging.md`](coastsnap-real-site-staging.md),
steps 3–11.

## Who runs what

- **Claude Code stays on the Windows development PC.** It never connects to
  Nectar, Spotteron, Gadi or NCI, and it never runs any command in this
  runbook against real systems.
- **The operator runs every Nectar command by hand** in an SSH session on the
  Nectar VM, and reviews the output before moving on.
- **This first run uses only `--preflight` and `--plan-only`.** Do **not** use
  `--process-local` or `--transfer` in this session.
- **The worker's `GADI_*` variables stay unset** for the whole session. Step 9
  checks this.
- **No real values or credentials are ever committed.** The site
  configuration, the worker settings and any tokens live in
  `$HOME/auscin-site/`, outside the Git checkout, with `chmod 600`. Only the
  placeholder templates (`*.env.example`) belong in Git.

## Placeholders

Replace these in your own terminal or in the files under `$HOME/auscin-site/`,
never in the repository.

| Placeholder | Meaning |
|---|---|
| `<NECTAR_USER>` | Your login on the Nectar VM |
| `<NECTAR_HOST>` | The Nectar VM's hostname or IP |
| `<SPOTTERON_ROOT_ID>` | Real Spotteron root ID of the test site (set in the site env file) |
| `<COASTSNAP_SITE_SLUG>` | Public AusCIN site ID, `CS-...` (set in the site env file) |
| `<DATE_FROM>` / `<DATE_TO>` | A UTC window of **only a few days** (`YYYY-MM-DD`) that is known to contain at least one observation |
| `<NCI_PUBLICATION_ROOT>` | Remote NCI destination for the *later* transfer. It isn't used in this session; leave the variable **empty** (see step 7) until `validate --for-transfer` |

Paths used on the VM, all outside the checkout and never under `/g/data`:

| Path | Purpose |
|---|---|
| `$HOME/AusCIN-WebPortal` | Git checkout (code only) |
| `$HOME/auscin-site/` | Real configuration: `coastsnap-site.env`, `worker.env` and review notes (`chmod 700`) |
| `$HOME/auscin-staging` | `COASTSNAP_STAGING_DIR`. Created by preflight, and still empty after this session |
| `$HOME/auscin-derivatives` | `COASTSNAP_DERIVATIVES_ROOT`. Unused in this session |

---

## A. On the Windows PC (PowerShell): push the branch

Run these from the repository root on the development PC. The operator (not
Claude Code) runs the push.

```powershell
git switch feat/coastsnap-catalogue-api
git status --short
```

Only the untracked, never-committed files `test-coastsnap.jpg` and `tools/`
may appear. Nothing else should be listed.

```powershell
git push -u origin feat/coastsnap-catalogue-api
git fetch origin
git status -sb
```

This must show `## feat/coastsnap-catalogue-api...origin/feat/coastsnap-catalogue-api`
with no "ahead" or "behind" count. Then record the exact commit for the
Nectar side:

```powershell
git log -1 --format="%H %s"
```

---

## B. On the Nectar VM (Linux, over SSH)

Connect from the PC:

```bash
ssh <NECTAR_USER>@<NECTAR_HOST>
```

### 1. Clone or pull the current branch

First time:

```bash
cd "$HOME"
git clone --branch feat/coastsnap-catalogue-api https://github.com/januka-perera/AusCIN-WebPortal.git
cd "$HOME/AusCIN-WebPortal"
```

Existing checkout:

```bash
cd "$HOME/AusCIN-WebPortal"
git fetch origin
git switch feat/coastsnap-catalogue-api
git pull --ff-only origin feat/coastsnap-catalogue-api
```

Either way, confirm the commit:

```bash
git log -1 --format='%H %s'    # must equal the hash recorded on the PC in section A
git status --short             # must print nothing
```

If the repository is private, authenticate with your own GitHub credentials
or a read-only deploy key held in `~/.ssh` on the VM. Never write a token
into the checkout, a remote URL or any file in the repository.

System packages (once per VM). ExifTool is needed for preflight to pass, and
the worker needs Python 3.11 or newer:

```bash
python3 --version              # needs 3.11+; if older, install python3.11 and use it below
sudo apt update
sudo apt install -y git python3-venv libimage-exiftool-perl
exiftool -ver
```

The steps below use `PY=python3`. Set `PY=python3.11` instead if
`python3 --version` reported something older than 3.11.

```bash
PY=python3
```

### 2. Create the worker virtual environment

```bash
cd "$HOME/AusCIN-WebPortal/apps/worker"
$PY -m venv .venv
.venv/bin/python -m pip install --upgrade pip
```

### 3. Install the worker and its `derivatives` extra

```bash
.venv/bin/python -m pip install -e ".[derivatives]"
.venv/bin/python -c "import coastsnap_import, PIL; print('worker', coastsnap_import.__version__, 'pillow', PIL.__version__)"
```

### 4. Create the API virtual environment

```bash
cd "$HOME/AusCIN-WebPortal/apps/api"
$PY -m venv .venv
.venv/bin/python -m pip install --upgrade pip
```

### 5. Install the API dependencies

The API imports the worker's manifest and derivatives-index models, so the
worker package is installed into this environment too, from the checkout:

```bash
.venv/bin/python -m pip install -e "../worker[derivatives]" -e .
.venv/bin/python -c "import auscin_api.site_config, coastsnap_import.derivatives; print('api ok')"
```

Both virtual environments live inside the checkout but are git-ignored, and
contain no data.

### 6. Copy the configuration templates outside the repository

```bash
install -d -m 700 "$HOME/auscin-site"
cp "$HOME/AusCIN-WebPortal/apps/api/config/coastsnap-site.env.example" "$HOME/auscin-site/coastsnap-site.env"
cp "$HOME/AusCIN-WebPortal/apps/worker/.env.example"                  "$HOME/auscin-site/worker.env"
chmod 600 "$HOME/auscin-site/coastsnap-site.env" "$HOME/auscin-site/worker.env"
```

### 7. Replace the placeholders with reviewed real values

```bash
nano "$HOME/auscin-site/coastsnap-site.env"
```

In `coastsnap-site.env`:

- Replace every `<...>` with the reviewed value.
- Quote values that contain spaces with **single quotes**, for example
  `COASTSNAP_SITE_DESCRIPTION='...'`, so the shell never expands `$` or
  backticks in them.
- Use these absolute paths. Write them in full, because `$HOME` is not
  expanded by the validator:

  ```
  COASTSNAP_STAGING_DIR=/home/<NECTAR_USER>/auscin-staging
  COASTSNAP_DERIVATIVES_ROOT=/home/<NECTAR_USER>/auscin-derivatives
  COASTSNAP_MANIFEST_PATH=/home/<NECTAR_USER>/auscin-staging/manifests/<SPOTTERON_ROOT_ID>.json
  COASTSNAP_DERIVATIVES_INDEX_PATH=/home/<NECTAR_USER>/auscin-derivatives/derivatives-index.json
  ```

- For this first session, set **`COASTSNAP_SITE_PUBLICATION_STATUS=embargoed`**
  and **`COASTSNAP_SITE_DOWNLOAD_PERMITTED=false`**.
- Set `NCI_PUBLICATION_ROOT=` (empty) for now. It isn't needed until the
  transfer step, and the validator only requires it with `--for-transfer`.
  Don't leave the literal `<NCI_PUBLICATION_ROOT>` line in the file:
  `source` would read `<` as a shell redirection and fail. The same applies
  to any other unreplaced `<...>`, but the validator in step 8 catches those
  before anything is sourced.

```bash
nano "$HOME/auscin-site/worker.env"
```

In `worker.env`:

- Set `SPOTTERON_BASE_URL=https://www.spotteron.com`.
- Leave `COASTSNAP_STAGING_DIR` **empty**. It comes from `coastsnap-site.env`.
- Leave `SPOTTERON_BEARER_TOKEN` empty unless one has been issued. If one
  has, it lives only in this file.
- Leave **every `GADI_*` line empty**.

### 8. Run the offline site configuration validator

```bash
cd "$HOME/AusCIN-WebPortal"
apps/api/.venv/bin/python -m auscin_api.site_config validate --env-file "$HOME/auscin-site/coastsnap-site.env"
```

It must end with `Configuration is valid ... No network or storage was
accessed.` and exit 0. If anything prints `[FAIL]`, fix it in
`$HOME/auscin-site/coastsnap-site.env` and re-run. Don't continue on a
failure.

Only after it passes, load both files into this shell. The site file comes
second, so its `COASTSNAP_STAGING_DIR` wins:

```bash
set -a
source "$HOME/auscin-site/worker.env"
source "$HOME/auscin-site/coastsnap-site.env"
set +a
```

### 9. Worker preflight

First, confirm that no Gadi configuration is present in this shell:

```bash
unset GADI_SFTP_HOST GADI_SFTP_PORT GADI_SFTP_USERNAME GADI_SFTP_PRIVATE_KEY_PATH GADI_REMOTE_ROOT GADI_CHECKSUM_STRATEGY
env | grep '^GADI_' || echo "OK: no GADI_* variables set"
```

Also confirm the staging directory is outside the checkout and not under
`/g/data`:

```bash
echo "$COASTSNAP_STAGING_DIR"
case "$COASTSNAP_STAGING_DIR" in "$HOME/AusCIN-WebPortal"*|/g/data*) echo "STOP: bad staging dir";; *) echo "OK";; esac
```

Then run preflight:

```bash
cd "$HOME/AusCIN-WebPortal/apps/worker"
.venv/bin/python -m coastsnap_import.cli --preflight --staging-dir "$COASTSNAP_STAGING_DIR"
```

Every check must print `[PASS]`. The "Gadi SFTP configuration" line is
informational and should report that it isn't configured. Preflight makes
one bounded `limit=1` metadata request to Spotteron, downloads no image and
never contacts Gadi.

### 10. Short, metadata-only `--plan-only` request

`--plan-only` is the default mode, and it is passed explicitly here anyway.
Use the real root ID from the site file (`<SPOTTERON_ROOT_ID>`), a window of
only a few days, and `--max-images 1`:

```bash
.venv/bin/python -m coastsnap_import.cli --plan-only \
  --root-id "$SPOTTERON_ROOT_ID" \
  --date-from <DATE_FROM> --date-to <DATE_TO> \
  --max-images 1 \
  2>&1 | tee "$HOME/auscin-site/plan-only-$(date -u +%Y%m%dT%H%M%SZ).txt"
```

This fetches Spotteron metadata only:

- no image download
- no Level 0/Level 1 files
- no manifest
- no Gadi connection

Confirm that nothing was staged:

```bash
find "$COASTSNAP_STAGING_DIR" -type f | head    # must print nothing
```

### 11. STOP: human review before any image download or transfer

Do **not** continue to `--process-local` or `--transfer` in this session.
Send the saved `plan-only-*.txt` output to the reviewer. It lives in
`$HOME/auscin-site/`, outside the repository. The reviewer confirms all of
the following:

- The observation listed belongs to the expected site `<COASTSNAP_SITE_SLUG>`,
  for root ID `<SPOTTERON_ROOT_ID>`, within `<DATE_FROM>`–`<DATE_TO>`.
  Check it against the public CoastSnap app if possible.
- The capture time looks right under the documented timezone assumption
  (`SPOTTERON_SOURCE_TIMEZONE`, default UTC, is still an assumption).
- The image reference resolved, and no error lines were printed.
- The output contains nothing that shouldn't be recorded, such as personal
  details.

Only after that review, a later session continues with
[`coastsnap-real-site-staging.md`](coastsnap-real-site-staging.md) step 3.
That is a `--process-local` import capped at `--max-images 1` into
`$HOME/auscin-staging`. `GADI_*` stays unset until its step 11.

### End of session

```bash
exit    # leave the SSH session; nothing needs cleaning up (nothing was staged)
```

Keep `$HOME/auscin-site/` on the VM. It holds the reviewed configuration and
the plan-only record, and it is never copied into the repository.

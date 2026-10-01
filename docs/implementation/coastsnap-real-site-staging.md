# Runbook: staging one real CoastSnap test site

Status: **prepared, not run.** Nothing in this repository has contacted
Spotteron, Nectar, Gadi or `/g/data/qu34` for a real site. Every value below
is a placeholder. Real values live only in an env file **outside** the
repository, which is never committed.

This runbook takes one real Spotteron site from a capped local import to a
reviewed, browsable, downloadable staging preview. Only then, after human
review, does it cover the SFTP transfer. It does **not** cover:

- public production access, Nginx or PostgreSQL
- NCI storage mounts
- scheduled ingestion
- automatic publication or download permission

Background: `coastsnap-single-site-publication.md` (design) and
`apps/api/README.md` → "Local end-to-end workflow". The synthetic rehearsal of
steps 5–10 is `scripts/coastsnap_e2e_smoke.py`.

## Placeholders

| Placeholder | Meaning | Supplied by |
|---|---|---|
| `<SPOTTERON_ROOT_ID>` | Spotteron root/site ID of the test site | project owner |
| `<COASTSNAP_SITE_SLUG>` | Public AusCIN site ID, `CS-...` | project owner |
| `<COASTSNAP_SITE_*>` | Reviewed public site metadata and decisions | project owner |
| `<NCI_PUBLICATION_ROOT>` | Remote NCI directory for the final transfer | NCI / project owner |
| `<DATE_FROM>` / `<DATE_TO>` | A **short** UTC window with a handful of known observations | operator |
| `<NECTAR_HOST>` | SSH host of the Nectar VM | operator |
| `<MEDIA_ID>` | An opaque `csm_...` ID shown by the API | read from the API in step 9 |

## Safety rules for every step

- **Keep the first imports tiny.** Use a date range of a few days, with
  `--max-images 1` for the first run and at most `--max-images 5` for the
  first real batch. Widen only after steps 4–10 have been reviewed.
- **Keep all local paths outside the git checkout, and never under
  `/g/data`.** The validator enforces this.
- **Publication and each download level are explicit decisions.** Start with
  `COASTSNAP_SITE_PUBLICATION_STATUS=embargoed`,
  `COASTSNAP_SITE_LEVEL0_DOWNLOAD_PERMITTED=false` and
  `COASTSNAP_SITE_LEVEL1_DOWNLOAD_PERMITTED=false`. Change them only after
  review:
  - the API serves only `public` sites
  - the validator requires all three values to be set explicitly, and
    refuses the retired single `COASTSNAP_SITE_DOWNLOAD_PERMITTED`
  - nothing defaults to public or downloadable
  - Level 0 (the untouched source image) and Level 1 (the AusCIN provenance
    copy) are permitted independently; neither implies the other
  - for the private staging preview, enable a level only deliberately, for
    example to review both downloads in step 9
- **Run step 11 (`--transfer`) only after steps 1–10 have been reviewed,**
  and only with explicit `--confirm-production-remote-root` if the remote
  root is under `/g/data/qu34`.

## 0. Prepare the site configuration (offline)

The exact first-session commands for steps 0–2 are in
[`coastsnap-nectar-first-run.md`](coastsnap-nectar-first-run.md). They
cover cloning the branch, creating both virtual environments, the
validator, preflight and one `--plan-only` request, and they end with a
mandatory review stop. The summary below assumes that setup.

On the Nectar VM, from the repository checkout:

```bash
install -d -m 700 "$HOME/auscin-site"
cp apps/api/config/coastsnap-site.env.example "$HOME/auscin-site/coastsnap-site.env"
cp apps/worker/.env.example "$HOME/auscin-site/worker.env"
chmod 600 "$HOME/auscin-site/coastsnap-site.env" "$HOME/auscin-site/worker.env"
# Edit coastsnap-site.env and replace every <...> placeholder. Quote values
# containing spaces with single quotes, e.g. COASTSNAP_SITE_DESCRIPTION='...'.
# Leave NCI_PUBLICATION_ROOT empty until step 11: an unreplaced <...> would
# break `source`.
# In worker.env, set SPOTTERON_BASE_URL. Leave COASTSNAP_STAGING_DIR and
# every GADI_* value empty.
# Suggested local paths:
#   COASTSNAP_STAGING_DIR=$HOME/auscin-staging
#   COASTSNAP_DERIVATIVES_ROOT=$HOME/auscin-derivatives
#   COASTSNAP_MANIFEST_PATH=$HOME/auscin-staging/manifests/<SPOTTERON_ROOT_ID>.json
#   COASTSNAP_DERIVATIVES_INDEX_PATH=$HOME/auscin-derivatives/derivatives-index.json
# (write the absolute paths out in full; the file is not shell-expanded by the validator)

apps/api/.venv/bin/python -m auscin_api.site_config validate --env-file "$HOME/auscin-site/coastsnap-site.env"
```

Continue only when it prints `Configuration is valid`. The validator checks
all of the following:

- nothing is unset, blank or still a `<...>` / `CHANGE_ME` / `TODO`
  placeholder
- the slug and root ID are well formed
- the time zone is a valid IANA name, and the establishment date is not in
  the future
- coordinates are **not** entered: the worker derives them from the source
  observations, and the API publishes the site only once they are confirmed
- publication status and download permission are explicit
- local paths are absolute, outside the repository and not under `/g/data`
- the manifest path is the worker's default

It never contacts Spotteron, Gadi or NCI.

Load the configuration into the shell for the remaining steps. Load the
worker settings **first** and the site file **second**. The worker template
contains an empty `COASTSNAP_STAGING_DIR=` line, so loading it second would
blank out the real staging directory:

```bash
set -a; source "$HOME/auscin-site/worker.env"; source "$HOME/auscin-site/coastsnap-site.env"; set +a
# worker.env holds SPOTTERON_BASE_URL etc. It lives outside the checkout.
# Leave every GADI_* value unset until step 11.
```

## 1. Worker preflight

```bash
cd apps/worker && source .venv/bin/activate
python -m coastsnap_import.cli --preflight
```

Every check must print `[PASS]`. This makes no Gadi connection and downloads
no image.

## 2. Plan only: a small request for the real root ID

```bash
python -m coastsnap_import.cli --plan-only \
  --root-id "$SPOTTERON_ROOT_ID" \
  --date-from <DATE_FROM> --date-to <DATE_TO> \
  --max-images 1
```

This fetches metadata only. It writes no files and makes no Gadi connection.
Confirm that the listed observation(s) belong to the expected site and date
window.

## 3. Capped local import into staging outside the repository

```bash
python -m coastsnap_import.cli --process-local \
  --root-id "$SPOTTERON_ROOT_ID" \
  --date-from <DATE_FROM> --date-to <DATE_TO> \
  --max-images 1 \
  --staging-dir "$COASTSNAP_STAGING_DIR"
```

Repeat with `--max-images 5` only after step 4 looks right. The command
prints `Run complete: processed=... failed=...`, and it must report
`failed=0`. The manifest is written to `$COASTSNAP_MANIFEST_PATH`, which is
the worker's default path. No Gadi connection is made.

## 4. Inspect the manifest and verify Level 0/Level 1 checksums

```bash
python -m json.tool "$COASTSNAP_MANIFEST_PATH" | less
python - <<'EOF'
import hashlib, json, os, pathlib
staging = pathlib.Path(os.environ["COASTSNAP_STAGING_DIR"])
manifest = json.loads(pathlib.Path(os.environ["COASTSNAP_MANIFEST_PATH"]).read_text())
bad = 0
for entry in manifest["entries"]:
    for level in ("level0", "level1"):
        product = entry.get(level)
        if product:
            actual = hashlib.sha256((staging / product["local_relative_path"]).read_bytes()).hexdigest()
            ok = actual == product["checksum"]["sha256"]
            bad += not ok
            print("OK  " if ok else "BAD ", level, entry["observation"]["observation_id"])
raise SystemExit(1 if bad else 0)
EOF
```

Also inspect the embedded XMP on one Level 1 file, as described in
`apps/worker/README.md` → "Embedded XMP metadata". Confirm that no contributor
names, tokens or paths are present.

## 5. Generate derivatives (thumbnails and previews)

```bash
python -m coastsnap_import.derivatives \
  --manifest "$COASTSNAP_MANIFEST_PATH" \
  --input-root "$COASTSNAP_STAGING_DIR" \
  --output-root "$COASTSNAP_DERIVATIVES_ROOT" \
  --index-output "$COASTSNAP_DERIVATIVES_INDEX_PATH"
```

It must report `failed=0`. Running it again must report `processed=0` and
`reused=N`. Level 1 checksums are verified before decoding. Derivatives
carry no embedded metadata.

## 6. Create the reviewed site registry entry

```bash
cd ../api && source .venv/bin/activate
python -m auscin_api.site_config write-registry \
  --env-file "$HOME/auscin-site/coastsnap-site.env" \
  --output "$HOME/auscin-site/site-registry.json"
```

The command validates again, writes a one-site registry with
`is_synthetic: false`, and prints the publication status and download
permission. Review the file. For the staging preview to be visible, a
reviewer must deliberately set `COASTSNAP_SITE_PUBLICATION_STATUS=public` and
re-run this step. The API serves only public sites. The registry stays
outside the repository.

## 7. Start FastAPI against the staged files

On the VM, bound to loopback only (no public access):

```bash
export AUSCIN_API_ENV=development
export COASTSNAP_SITE_REGISTRY_PATH="$HOME/auscin-site/site-registry.json"
export COASTSNAP_MEDIA_ROOT="$COASTSNAP_STAGING_DIR"
export AUSCIN_MEDIA_BASE_URL="http://127.0.0.1:8000"
# COASTSNAP_MANIFEST_PATH, COASTSNAP_DERIVATIVES_INDEX_PATH and
# COASTSNAP_DERIVATIVES_ROOT are already set from the site env file.
python -m uvicorn auscin_api.main:create_app --factory --host 127.0.0.1 --port 8000
curl -s http://127.0.0.1:8000/api/v1/health
```

## 8. Start Next.js with `COASTSNAP_API_BASE_URL`

The frontend needs Node.js on the machine that runs it. Pick one option.

- **A: run on the VM** and browse through an SSH tunnel:
  `ssh -L 3000:127.0.0.1:3000 -L 8000:127.0.0.1:8000 <NECTAR_HOST>`.
  Both ports are needed, because the browser loads media straight from the
  API origin.
- **B: copy the staging, derivatives and registry directories** to a
  workstation (again outside any repository), then run steps 7–8 there with
  local paths.

```bash
cd apps/web
export COASTSNAP_API_BASE_URL="http://127.0.0.1:8000"
npm ci && npm run build && npm run start -- -H 127.0.0.1 -p 3000
```

## 9. Browse the archive and download each permitted level

- Open `http://localhost:3000/coastsnap`, then `/coastsnap/<COASTSNAP_SITE_SLUG>/archive`.
- Check the following:
  - thumbnails load, and a detail page shows the preview
  - capture times display in the site's time zone
  - the credit line shows only the configured attribution text
  - no contributor names, raw Spotteron IDs or file paths appear
- The detail page shows one button per permitted level:
  - **Download original (Level 0)**: the untouched source image
  - **Download provenance copy (Level 1)**: the image with AusCIN
    provenance metadata

  If only one level is permitted, only that button appears, with a line
  explaining that the other isn't offered. If neither is permitted, the page
  shows "Original unavailable".
- Download each permitted level, either from the page or directly:

```bash
curl -s "http://127.0.0.1:8000/api/v1/coastsnap/sites/<COASTSNAP_SITE_SLUG>/observations?pageSize=5" | python -m json.tool
curl -sS -D - -o "$HOME/auscin-site/download-level0.jpg" "http://127.0.0.1:8000/media/coastsnap/<MEDIA_ID>/level0" | grep -i -E "content-disposition|etag"
curl -sS -D - -o "$HOME/auscin-site/download-level1.jpg" "http://127.0.0.1:8000/media/coastsnap/<MEDIA_ID>/level1" | grep -i -E "content-disposition|etag"
```

`/original` still works as a deprecated alias for `/level1`, but don't use it
in new commands.

## 10. Compare each downloaded SHA-256 with the manifest

```bash
for level in level0 level1; do
  HASH=$(sha256sum "$HOME/auscin-site/download-$level.jpg" | cut -d' ' -f1)
  echo "$level $HASH"
  grep -c "\"$HASH\"" "$COASTSNAP_MANIFEST_PATH"   # before any transfer, must print 1 (that level's checksum for the observation)
done
```

This is independent of the API: it hashes the bytes the browser would
receive and looks them up in the worker's own manifest. The two hashes must
differ, because Level 1 carries embedded provenance metadata. After a
transfer, a checksum also appears as the recorded remote checksum, so expect
2 then.

## 11. Only after review: SFTP transfer

Review steps 1–10 with the project owner first. Then:

1. Set the Gadi configuration in `$HOME/auscin-site/worker.env`, outside the
   checkout, and set `NCI_PUBLICATION_ROOT` in `coastsnap-site.env`.
2. Reload both files, in the same order as in step 0.
3. Validate for transfer:

```bash
apps/api/.venv/bin/python -m auscin_api.site_config validate --env-file "$HOME/auscin-site/coastsnap-site.env" --for-transfer
cd apps/worker && source .venv/bin/activate
export GADI_REMOTE_ROOT="$NCI_PUBLICATION_ROOT"     # plus GADI_SFTP_HOST / _USERNAME / _PRIVATE_KEY_PATH
python -m coastsnap_import.cli --transfer \
  --root-id "$SPOTTERON_ROOT_ID" \
  --date-from <DATE_FROM> --date-to <DATE_TO> \
  --max-images 5 \
  --staging-dir "$COASTSNAP_STAGING_DIR" \
  --confirm-production-remote-root    # required only if <NCI_PUBLICATION_ROOT> is under /g/data/qu34
```

Use the same `--date-from`/`--date-to`/`--max-images` as the reviewed local
run. The manifest refuses to continue if `GADI_REMOTE_ROOT` differs from the
remote root it already records. See `apps/worker/README.md` → "Remote root
consistency".

## Serving more than one site

Repeat steps 0–5 for each further root ID, using the **same**
`COASTSNAP_STAGING_DIR` and `COASTSNAP_DERIVATIVES_ROOT`. The worker
already separates sites under `root-<root_id>/`. Give each site its own
manifest (the worker default, `manifests/<root_id>.json`) and its own index
file, e.g. `$COASTSNAP_DERIVATIVES_ROOT/<root_id>-index.json`.

`write-registry` writes a one-site registry. For several sites, combine the
reviewed `sites` entries into one registry file by hand and review it again:
each site keeps its own explicit publication and download decisions.

Then, in step 7, list every manifest and index explicitly in place of the
singular settings. Never point the API at a directory:

```bash
unset COASTSNAP_MANIFEST_PATH COASTSNAP_DERIVATIVES_INDEX_PATH
export COASTSNAP_MANIFEST_PATHS="$COASTSNAP_STAGING_DIR/manifests/<ROOT_A>.json:$COASTSNAP_STAGING_DIR/manifests/<ROOT_B>.json"
export COASTSNAP_DERIVATIVES_INDEX_PATHS="$COASTSNAP_DERIVATIVES_ROOT/<ROOT_A>-index.json:$COASTSNAP_DERIVATIVES_ROOT/<ROOT_B>-index.json"
```

Setting the singular and plural forms together is refused, and so is
listing the same file twice. Indexes are matched to manifests by the root ID
they record. `/api/v1/health` should report one public site for every site
that is public, has a confirmed coordinate and has at least one presentable
image. See `apps/api/README.md` → "One site or several".

## Clean up

Remove local staging only after review, and after the transfer has been
verified if one was done:

```bash
rm -rf "$COASTSNAP_STAGING_DIR" "$COASTSNAP_DERIVATIVES_ROOT" "$HOME/auscin-site/download.jpg"
```

Keep `$HOME/auscin-site/coastsnap-site.env` and `site-registry.json` for the
record. Neither is committed.

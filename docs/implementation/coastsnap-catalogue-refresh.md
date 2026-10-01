# Runbook: refreshing the CoastSnap catalogue

Status: **prepared, not run against real data.** Every value below is a
placeholder. Real env files, registries, manifests, indexes and media live
outside the repository and are never committed.

This runbook refreshes an already configured catalogue of one or more
CoastSnap sites. It covers new observations, a newly added site, and a
reviewed policy change. It uses only the existing commands:

- the worker import, `python -m coastsnap_import.cli`;
- the derivatives command, `python -m coastsnap_import.derivatives`;
- the registry tool, `python -m auscin_api.site_config`;
- the API itself, which is the only validator of the complete catalogue.

It is run by hand. There is deliberately no scheduler, timer, file watcher,
reload endpoint or automatic publication. See "Not covered" at the end.

First-time setup of a site, including its env file, the first capped import
and the review of downloads, is in
[`coastsnap-real-site-staging.md`](coastsnap-real-site-staging.md). Do that
first for any new site.

## Placeholders

| Placeholder | Meaning |
|---|---|
| `<ROOT_A>`, `<ROOT_B>` | Spotteron root IDs of the configured sites |
| `<SITE_CONFIG_DIR>` | Directory holding one reviewed env file per site, e.g. `<SITE_CONFIG_DIR>/<ROOT_A>.env` |
| `<STAGING_DIR>` | The worker staging directory (`COASTSNAP_STAGING_DIR`), shared by every site |
| `<DERIVATIVES_ROOT>` | The derivatives output root (`COASTSNAP_DERIVATIVES_ROOT`), shared by every site |
| `<RELEASE_DIR>` | Where this refresh's registry and API environment are written, e.g. `<CONFIG_ROOT>/releases/<YYYYMMDD-HHMM>` |
| `<PREVIOUS_RELEASE_DIR>` | The release currently in service, kept for rollback |
| `<API_ENV_FILE>` | The environment file the service manager passes to the API |
| `<REGISTRY_IN_SERVICE>` | The registry file the running API was started with (first refresh only) |
| `<API_SERVICE>` | The API's unit or service name in the VM's service manager |
| `<DATE_FROM>` / `<DATE_TO>` | The UTC window to import |
| `<MAX_IMAGES>` | An explicit cap on observations per import (the worker's default is only 5) |
| `<MEDIA_ID>` | An opaque `csm_...` ID read from the API |

## Five separate states

A site moves through these one at a time, and **none implies the next**.

| State | What makes it true | Controlled by |
|---|---|---|
| **Imported** | The worker wrote Level 0/1 files and a manifest | worker run |
| **Has derivatives** | The derivatives command wrote thumbnails, previews and an index | derivatives run |
| **Eligible** | The manifest has a *confirmed* coordinate **and** at least one presentable image (Level 0, Level 1 and a capture time) | worker data, checked by the API |
| **Published** | The reviewed registry says `publication_status: public` **and** the site is eligible **and** its manifest is listed in `COASTSNAP_MANIFEST_PATHS` | human review |
| **Downloadable (per level)** | The registry sets `level0_download_permitted` / `level1_download_permitted` to `true` for that site | human review, per level |

A manifest that exists, or even a fully eligible site, is **never** published
by this workflow. Publication changes only when a person edits a site's
reviewed env file and regenerates the registry (step 4).

## Refresh order

```text
0. snapshot the release in service
1. worker import(s), one site at a time
2. verify each manifest: checksums and coordinate status
3. derivatives for every configured manifest
4. review env files, regenerate the multi-site registry
5. write the new API environment (explicit manifest and index lists)
6. trial-start the API on a spare loopback port and check it
7. switch the service to the new environment and restart it
8. smoke-test health, sites, observations, preview and download
9. if anything is wrong: roll back (restore the previous environment, restart)
```

Never skip a step to get to the restart sooner. Up to step 7, the running
service is untouched.

## 0. Snapshot the release in service

`<PREVIOUS_RELEASE_DIR>` is the release directory from the last refresh. It
already holds the `api.env` and `site-registry.json` in service. On the very
first refresh, create it from the running service:

```bash
# Production VM (POSIX). Copy, never move or delete.
mkdir -p "<PREVIOUS_RELEASE_DIR>"                        # first refresh only
cp -p "<API_ENV_FILE>" "<PREVIOUS_RELEASE_DIR>/api.env"   # first refresh only
cp -p "<REGISTRY_IN_SERVICE>" "<PREVIOUS_RELEASE_DIR>/site-registry.json"   # first refresh only

mkdir -p "<RELEASE_DIR>/snapshot"
cp -p "<STAGING_DIR>/manifests/<ROOT_A>.json" "<STAGING_DIR>/manifests/<ROOT_B>.json" "<RELEASE_DIR>/snapshot/"
cp -p "<DERIVATIVES_ROOT>/<ROOT_A>-index.json" "<DERIVATIVES_ROOT>/<ROOT_B>-index.json" "<RELEASE_DIR>/snapshot/"
```

Name every file explicitly. Don't glob a directory: the configured set is
exactly the sites in service. The worker never deletes media, but it does
update manifests in place, and the derivatives command rewrites its index.
The snapshot copies are what makes a data rollback possible in step 9.

## 1. Worker import, one site at a time

Load each site's own worker environment, then import that root only:

```bash
cd apps/worker && source .venv/bin/activate
python -m coastsnap_import.cli --process-local \
  --root-id <ROOT_A> \
  --date-from <DATE_FROM> --date-to <DATE_TO> \
  --max-images <MAX_IMAGES> \
  --staging-dir "<STAGING_DIR>"
```

- Require exit code 0 and `failed=0` in the `Run complete:` line. A rerun
  over the same window reports `reused_local` instead of `processed`. That's
  expected; it doesn't download anything again.
- Read the `[site]` line. `coordinates confirmed from N observation(s)` is
  what eligibility needs. `missing`, `invalid` or `inconsistent` means this
  site will stay hidden; record why, and don't edit coordinates by hand.
- If the `[site]` line says `--max-images` was reached, the coordinate covers
  only the images imported so far. Raise the cap or import further windows
  before relying on it.
- Use `--transfer` instead of `--process-local` only as described in the
  staging runbook (step 11), after review.

Repeat for `<ROOT_B>`, and so on. Never run imports for two roots in
parallel against the same manifest.

## 2. Verify each manifest

For every configured manifest, check the Level 0/1 checksums against the
staged files, and print the site record the API will read:

```bash
python - "<STAGING_DIR>" "<STAGING_DIR>/manifests/<ROOT_A>.json" "<STAGING_DIR>/manifests/<ROOT_B>.json" <<'EOF'
import hashlib, json, pathlib, sys
staging, manifests = pathlib.Path(sys.argv[1]), sys.argv[2:]
bad = 0
for path in manifests:
    manifest = json.loads(pathlib.Path(path).read_text())
    sites = {json.dumps(e["site"], sort_keys=True) for e in manifest["entries"]}
    site = manifest["entries"][0]["site"] if manifest["entries"] else {}
    presentable = sum(1 for e in manifest["entries"]
                      if e.get("level0") and e.get("level1") and e["observation"].get("spotted_at_utc"))
    print(f"{manifest['root_id']}: coordinate={site.get('coordinate_status')} "
          f"presentable={presentable} site_records_agree={len(sites) <= 1}")
    for entry in manifest["entries"]:
        for level in ("level0", "level1"):
            product = entry.get(level)
            if product:
                file = staging / product["local_relative_path"]
                actual = hashlib.sha256(file.read_bytes()).hexdigest() if file.is_file() else "missing"
                if actual != product["checksum"]["sha256"]:
                    bad += 1
                    print("  BAD" if actual != "missing" else "  MISSING", level, entry["observation"]["observation_id"])
raise SystemExit(1 if bad else 0)
EOF
```

It must exit 0. A site is eligible only with `coordinate=confirmed`,
`presentable` above 0 and `site_records_agree=True`. If they disagree, the
import was interrupted, so rerun step 1 for that root. This script only reads
files; the API applies the same rules again in step 6.

## 3. Derivatives for every configured manifest

One index per root, written to an explicit path:

```bash
python -m coastsnap_import.derivatives \
  --manifest "<STAGING_DIR>/manifests/<ROOT_A>.json" \
  --input-root "<STAGING_DIR>" \
  --output-root "<DERIVATIVES_ROOT>" \
  --index-output "<DERIVATIVES_ROOT>/<ROOT_A>-index.json"
```

Require `failed=0`. Unchanged images are reported as `reused`, and observations
without Level 1 as `skip`. Repeat for each root. An index made from an older
Level 1 is dropped by the API as stale, never served, so a missed run means
missing thumbnails, not wrong ones.

## 4. Review env files and regenerate the registry

Publication and download decisions change **only here**, by editing a site's
reviewed env file in `<SITE_CONFIG_DIR>`: `COASTSNAP_SITE_PUBLICATION_STATUS`,
`COASTSNAP_SITE_LEVEL0_DOWNLOAD_PERMITTED` and
`COASTSNAP_SITE_LEVEL1_DOWNLOAD_PERMITTED`. Record who approved each change.

Write the registry into the **new** release directory, so the one in service
is never overwritten:

```bash
cd apps/api && source .venv/bin/activate
python -m auscin_api.site_config write-registry \
  --env-file "<SITE_CONFIG_DIR>/<ROOT_A>.env" \
  --env-file "<SITE_CONFIG_DIR>/<ROOT_B>.env" \
  --output "<RELEASE_DIR>/site-registry.json"
diff "<PREVIOUS_RELEASE_DIR>/site-registry.json" "<RELEASE_DIR>/site-registry.json"
```

The command validates every file independently and refuses duplicate slugs,
root IDs, manifest paths or index paths. With several files it ignores the
shell environment. Read the printed policy for every site, and the `diff`:
**any change to a publication status or download permission must be one
that was approved.** The registry holds no coordinates; those come from the
manifests.

## 5. Write the new API environment

List every manifest and index explicitly, in the release directory:

```bash
cat > "<RELEASE_DIR>/api.env" <<EOF
AUSCIN_API_ENV=production
COASTSNAP_SITE_REGISTRY_PATH=<RELEASE_DIR>/site-registry.json
COASTSNAP_MANIFEST_PATHS=<STAGING_DIR>/manifests/<ROOT_A>.json:<STAGING_DIR>/manifests/<ROOT_B>.json
COASTSNAP_DERIVATIVES_INDEX_PATHS=<DERIVATIVES_ROOT>/<ROOT_A>-index.json:<DERIVATIVES_ROOT>/<ROOT_B>-index.json
COASTSNAP_MEDIA_ROOT=<STAGING_DIR>
COASTSNAP_DERIVATIVES_ROOT=<DERIVATIVES_ROOT>
AUSCIN_MEDIA_BASE_URL=<PUBLIC_MEDIA_ORIGIN>
EOF
```

Rules the API enforces at startup:
- the separator is `:` on the POSIX VM;
- don't also set the singular `COASTSNAP_MANIFEST_PATH` /
  `COASTSNAP_DERIVATIVES_INDEX_PATH`;
- no file may be listed twice, and no index may name a root that isn't
  listed.

A site whose manifest isn't listed is not served at all, whatever the
registry says. Adding a site therefore means adding it here *and* in step 4.

## 6. Trial-start the API on a spare loopback port

The API's own startup is the complete validator: it loads every listed
manifest, index and the registry with the same code the service uses.
Starting a second instance on a spare loopback port checks the new release
without touching the running service.

Use a **fresh shell**. The site env files sourced in step 1 set the singular
`COASTSNAP_MANIFEST_PATH` / `COASTSNAP_DERIVATIVES_INDEX_PATH`, and the API
refuses those alongside the lists:

```bash
unset COASTSNAP_MANIFEST_PATH COASTSNAP_DERIVATIVES_INDEX_PATH
set -a && . "<RELEASE_DIR>/api.env" && set +a
python -m uvicorn auscin_api.main:create_app --factory --host 127.0.0.1 --port 8099 &
TRIAL=$!; sleep 5
curl -fsS http://127.0.0.1:8099/api/v1/health
curl -fsS http://127.0.0.1:8099/api/v1/coastsnap/sites | python -m json.tool
kill $TRIAL
```

- **If the process exits during startup** (`CatalogueError` or
  `SettingsError`), the input is unsafe or corrupt: a bad path, a checksum
  that isn't SHA-256, a duplicate root, an index for an unlisted root, or a
  contradictory site record. The message names the manifest's root ID. Fix
  it and repeat from the relevant step. Nothing has changed in service.
- **Warnings name every public site that will stay hidden**, and why, for
  example `Public site CS-... not published: no confirmed coordinate in the
  manifest.` Sites that aren't public in the registry are hidden without a
  warning, by design.
- **`publicSiteCount` must equal** the number of sites that are public in the
  registry, confirmed in step 2 and have a presentable image. `/sites` must
  list exactly those site IDs.

## 7. Switch the service to the new release and restart

```bash
cp -p "<RELEASE_DIR>/api.env" "<API_ENV_FILE>"     # or repoint the service manager at it
<restart command for <API_SERVICE> in the VM's service manager>
```

The API builds its catalogue only at startup, so the restart is what makes
the refresh visible. A failed startup leaves the service down: go straight to
step 9.

## 8. Post-restart checks

```bash
API=<PUBLIC_API_ORIGIN>
curl -fsS "$API/api/v1/health"                                   # same counts as the trial
curl -fsS "$API/api/v1/coastsnap/sites" | python -m json.tool     # same site IDs as the trial
curl -fsS "$API/api/v1/coastsnap/sites/<SITE_ID>/observations?pageSize=1" | python -m json.tool   # one archive; note its mediaId
curl -sS -o /dev/null -w "%{http_code}\n" -I "$API/media/coastsnap/<MEDIA_ID>/preview"             # 200, or 404 if no derivative
curl -sS -D - -o /tmp/check-download.jpg "$API/media/coastsnap/<MEDIA_ID>/<PERMITTED_LEVEL>" | grep -i etag
sha256sum /tmp/check-download.jpg                                 # must equal the ETag and the manifest checksum
curl -sS -o /dev/null -w "%{http_code}\n" "$API/media/coastsnap/<MEDIA_ID>/<NOT_PERMITTED_LEVEL>"  # 403
```

Also open `/map` and `/coastsnap` in the frontend: every published site, and
no other, must appear.

## 9. Rollback

Roll back if step 7 fails to start, or step 8 shows anything unexpected: a
wrong site set, a policy that wasn't approved, or broken media.

```bash
cp -p "<PREVIOUS_RELEASE_DIR>/api.env" "<API_ENV_FILE>"
<restart command for <API_SERVICE>>
```

Then repeat step 8 against the previous release's expected counts. This
restores the previous registry and manifest/index lists exactly, because
step 4 never overwrote them.

If the problem is in the data rather than the configuration (a manifest
updated in step 1, or an index rewritten in step 3), also restore those files
from `<RELEASE_DIR>/snapshot/` before restarting. The worker never deletes
media, so a restored manifest still finds its Level 0/1 files. A restored
index whose derivative files were regenerated in the meantime may answer
thumbnail/preview requests with 503 (size mismatch). In that case rerun
step 3 for that root rather than serving it.

Leave the failed release directory in place for diagnosis. Don't delete
media or derivatives as part of a rollback.

## Local dry run (Windows PowerShell)

Rehearse with synthetic data only, never `/g/data`.

The automated end-to-end smoke test covers worker derivatives, the API,
Next.js, preview and checksum-verified downloads for one site:

```powershell
apps\api\.venv\Scripts\python.exe scripts\coastsnap_e2e_smoke.py --skip-build
```

To rehearse steps 5–6 with several sites, trial-start the API on a spare port
against the committed fixtures, plus any further synthetic manifests you
generate outside the repository:

```powershell
cd apps\api
$env:AUSCIN_API_ENV = "development"
$env:COASTSNAP_SITE_REGISTRY_PATH = "tests\fixtures\coastsnap\sites-registry.json"
$env:COASTSNAP_MANIFEST_PATHS = "tests\fixtures\coastsnap\manifest.json"   # ';'-separated for several
$env:COASTSNAP_DERIVATIVES_INDEX_PATHS = "tests\fixtures\coastsnap\derivatives-index.json"
.\.venv\Scripts\python.exe -m uvicorn auscin_api.main:create_app --factory --host 127.0.0.1 --port 8099
# In a second terminal:
Invoke-RestMethod http://127.0.0.1:8099/api/v1/health
(Invoke-RestMethod http://127.0.0.1:8099/api/v1/coastsnap/sites).id
```

Multi-site behaviour is covered by `apps/api/tests/test_multi_manifest.py`:
several sites, hidden ineligible sites, stale and missing derivatives, load
failures, and agreement between health, site, observation and media
responses.

## Not covered; needs separate approval

Each of these changes who or what can alter the public catalogue, so each
needs its own design review before it is built:

- **Scheduling** (cron/timers) of imports, derivatives or restarts. This
  needs a decision on unattended `/g/data` transfers, failure alerting and
  `--max-images` limits.
- **Hot reload or an admin endpoint.** Any endpoint that rebuilds the
  catalogue needs authentication, and a design for atomic swap and rollback.
- **Automatic publication**, or any rule that makes a site public or
  downloadable without a person changing its reviewed env file.
- **A service unit or deployment files**, the service manager configuration,
  and TLS/Nginx in front of the API.
- **Serving media directly from NCI storage** (`<NCI_PUBLICATION_ROOT>`)
  instead of local staging copies.
- **Retention:** deleting old media, derivatives or release directories.

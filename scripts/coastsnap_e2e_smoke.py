"""Local end-to-end smoke test for the CoastSnap publication workflow.

    worker manifest -> worker-generated thumbnails/previews -> FastAPI catalogue
      -> Next.js CoastSnap pages -> preview -> Level 0 and Level 1 downloads (checksum-verified)

Everything is synthetic and local. There are no Spotteron, Nectar, Gadi or
/g/data paths, and nothing from the untracked test-coastsnap.jpg or tools/ is
used. Steps:

1. Create a temporary staging directory OUTSIDE the repository, containing
   synthetic Level 0 JPEGs made with Pillow, and Level 1 copies of them with
   an added provenance segment, so the two levels have different bytes and
   checksums. The manifest is written with the worker's own models. It uses the fixture registry's TEST_ROOT_ID and site
   CS-TEST-SITE.
2. Run the real `python -m coastsnap_import.derivatives` twice. The first run
   processes 4 of 5 images (`--max-images 4`, so the 5th has no derivatives
   and exercises the no-fallback path); the second run must reuse all 4.
3. Start FastAPI with the fixture site registry, the generated manifest, the
   generated derivatives index and both generated media roots.
4. Build Next.js (unless --skip-build) and start it with COASTSNAP_API_BASE_URL.
5. Verify the API and the rendered pages:
   - `/coastsnap`, the archive and a media detail page
   - thumbnail and preview responses
   - both the Level 0 and Level 1 downloads: attachment disposition,
     opaque per-level filename, ETag, Range support, and bytes whose
     SHA-256 matches that level's manifest checksum. The two levels must
     differ.
   - the deprecated /original alias still serves Level 1
   - both download buttons on the detail page
   - a missing derivative never falls back to either level
   - no internal paths or source IDs appear in any public response
6. Restart the API with Level 0 withheld and Level 1 permitted. Verify that
   only the Level 1 action remains, that the page explains why Level 0 is
   unavailable, that /level0 returns 403, and that the deprecated /original
   still follows Level 1.
7. Stop both servers and delete the staging directory.

Run from the repository root with the API virtual environment. It needs
apps/api's dependencies plus the worker's `derivatives` extra, and Node.js/npm:

    apps\\api\\.venv\\Scripts\\python.exe scripts\\coastsnap_e2e_smoke.py

Exit code 0 means every check passed. Any failed check exits 1 and prints the
failing check plus the last lines of each server log.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
API_DIR = REPO_ROOT / "apps" / "api"
WEB_DIR = REPO_ROOT / "apps" / "web"
FIXTURE_REGISTRY = API_DIR / "tests" / "fixtures" / "coastsnap" / "sites-registry.json"

ROOT_ID = "TEST_ROOT_ID"  # must match the fixture registry's public site
SITE_ID = "CS-TEST-SITE"
SITE_NAME = "Test Beach CoastSnap"
UTC = timezone.utc

# (observation id, capture time, Level 1 size). Manifest order is processing order. The last
# entry falls outside --max-images 4, so it deliberately gets no derivatives.
OBSERVATIONS = [
    ("E2E_OBS_0001", datetime(2026, 8, 3, 0, 5, tzinfo=UTC), (2400, 1800)),
    ("E2E_OBS_0002", datetime(2026, 8, 11, 5, 40, tzinfo=UTC), (1800, 2400)),
    ("E2E_OBS_0003", datetime(2026, 8, 19, 22, 15, tzinfo=UTC), (3000, 1000)),
    ("E2E_OBS_0004", datetime(2026, 8, 27, 3, 0, tzinfo=UTC), (1600, 1200)),
    ("E2E_OBS_0005", datetime(2026, 9, 2, 1, 30, tzinfo=UTC), (2000, 1500)),
]
WITH_DERIVATIVES = [obs for obs, _, _ in OBSERVATIONS[:4]]
WITHOUT_DERIVATIVES = OBSERVATIONS[4][0]

# Must never appear in any public API response or rendered page.
FORBIDDEN_PUBLIC = [
    "/g/data", "qu34", "level-0", "level-1", "derivatives/", "source-records",
    "root-TEST_ROOT_ID", "TEST_ROOT_ID", "TEST_PUBLICATION_ROOT", "E2E_OBS_", "example.invalid",
]


# --- Reporting ----------------------------------------------------------------------


@dataclass
class Report:
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    def check(self, name: str, condition: bool, detail: str = "") -> bool:
        if condition:
            self.passed.append(name)
            print(f"  [PASS] {name}")
        else:
            self.failed.append(name)
            print(f"  [FAIL] {name}{f' — {detail}' if detail else ''}")
        return condition


def step(title: str) -> None:
    print(f"\n== {title}")


# --- Synthetic data -----------------------------------------------------------------------


def make_level0_jpeg(width: int, height: int, seed: int) -> bytes:
    """A synthetic stand-in for an untouched Spotteron source image."""
    from PIL import Image

    image = Image.new("RGB", (width, height), (40 + seed * 30, 110, 150 - seed * 10))
    for x in range(0, width, max(1, width // 24)):  # stripes, so resampling does real work
        image.paste((200, 180 - seed * 20, 90), (x, 0, min(width, x + width // 96 + 1), height))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=88)
    return buffer.getvalue()


def make_level1_from_level0(level0: bytes, observation_id: str) -> bytes:
    """A synthetic Level 1: the identical image data with a provenance segment added (a JPEG COM
    segment after SOI), mirroring how the worker embeds metadata without re-encoding the image."""
    payload = f"AusCIN synthetic provenance - {observation_id}".encode("ascii")
    segment = b"\xff\xfe" + (len(payload) + 2).to_bytes(2, "big") + payload
    return level0[:2] + segment + level0[2:]


def build_staging(staging: Path) -> tuple[Path, dict[str, dict]]:
    """Writes synthetic Level 0 and Level 1 files and a worker-format manifest. Returns (manifest path, expected-by-observation)."""
    from coastsnap_import.models import (
        ChecksumInfo, Level0Product, Level1Product, Manifest, ManifestEntry, ProcessingDetails, ProductLevel,
        SourceObservation, SourceSite, build_level_relative_path, build_site_directory_id, build_source_record_paths,
    )

    now = datetime.now(UTC)
    site_dir = build_site_directory_id(ROOT_ID)
    entries, expected = [], {}
    for seed, (obs_id, captured, (width, height)) in enumerate(OBSERVATIONS):
        level0_data = make_level0_jpeg(width, height, seed)
        level1_data = make_level1_from_level0(level0_data, obs_id)
        l1 = build_level_relative_path(ProductLevel.LEVEL_1, site_dir, captured, f"{obs_id}.jpg")
        l0 = build_level_relative_path(ProductLevel.LEVEL_0, site_dir, captured, f"{obs_id}.jpg")
        for relative, data in ((l0, level0_data), (l1, level1_data)):
            target = staging.joinpath(*relative.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        level0_sha = hashlib.sha256(level0_data).hexdigest()
        level1_sha = hashlib.sha256(level1_data).hexdigest()
        entries.append(ManifestEntry(
            site=SourceSite(root_id=ROOT_ID),
            observation=SourceObservation(
                observation_id=obs_id, root_id=ROOT_ID,
                spotted_at_raw=captured.strftime("%Y-%m-%d %H:%M:%S"), spotted_at_utc=captured,
            ),
            source_record_ref=build_source_record_paths(ROOT_ID, obs_id),
            level0=Level0Product(
                product_id=f"{obs_id}-L0", parent_observation_id=obs_id,
                source_url=f"https://example.invalid/e2e/{obs_id}.jpg", local_relative_path=l0,
                remote_relative_path=l0, file_size_bytes=len(level0_data), content_type="image/jpeg",
                checksum=ChecksumInfo(sha256=level0_sha, computed_at_utc=now), downloaded_at_utc=now,
            ),
            level1=Level1Product(
                product_id=f"{obs_id}-L1", parent_product_id=f"{obs_id}-L0", parent_observation_id=obs_id,
                local_relative_path=l1, remote_relative_path=l1, file_size_bytes=len(level1_data),
                checksum=ChecksumInfo(sha256=level1_sha, computed_at_utc=now),
                processing=ProcessingDetails(
                    embedder_backend="exiftool", embedded_metadata_fields=[], processing_software="coastsnap-import",
                    processing_version="0.1.0", processed_at_utc=now,
                ),
            ),
            ingested_at_utc=now,
        ))
        expected[obs_id] = {"level0": level0_sha, "level1": level1_sha, "width": width, "height": height}

    manifest = Manifest(
        run_id=now.strftime("%Y%m%dT%H%M%SZ"), root_id=ROOT_ID, topic_id=37,
        date_from_utc=datetime(2026, 8, 1, tzinfo=UTC), date_to_utc=datetime(2026, 9, 30, tzinfo=UTC),
        generated_at_utc=now, remote_root="TEST_PUBLICATION_ROOT", entries=entries,
    )
    manifest_path = staging / "manifests" / f"{ROOT_ID}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest_path, expected


# --- Processes --------------------------------------------------------------------------------


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_process(cmd: list[str], *, cwd: Path, env: dict[str, str], log: Path) -> subprocess.Popen:
    handle = log.open("wb")
    kwargs: dict = {"cwd": cwd, "env": env, "stdout": handle, "stderr": subprocess.STDOUT}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(cmd, **kwargs)


def stop_process(process: Optional[subprocess.Popen]) -> None:
    """Stops a server and its whole process tree. npm starts node as a child, so killing only the npm PID isn't enough."""
    if process is None or process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        process.kill()


def wait_for(url: str, process: subprocess.Popen, timeout: float, ok: Callable[[int], bool] = lambda s: s == 200) -> bool:
    import httpx

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        try:
            if ok(httpx.get(url, timeout=5).status_code):
                return True
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    return False


def tail(path: Path, lines: int = 25) -> str:
    try:
        return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
    except OSError:
        return "(no log)"


def find_npm(explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    found = shutil.which("npm")
    if not found and os.name == "nt":
        candidate = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "nodejs" / "npm.cmd"
        if candidate.exists():
            found = str(candidate)
    if not found:
        raise SystemExit("npm not found on PATH; pass --npm <path to npm>")
    return found


def node_env(npm: str) -> dict[str, str]:
    env = dict(os.environ)
    env["PATH"] = str(Path(npm).parent) + os.pathsep + env.get("PATH", "")
    env.pop("COASTSNAP_MEDIA_ORIGIN", None)
    env["NEXT_TELEMETRY_DISABLED"] = "1"
    return env


# --- Checks ---------------------------------------------------------------------------------


def media_id(observation_id: str) -> str:
    from auscin_api.catalogue import build_media_id

    return build_media_id(SITE_ID, observation_id)


def scan_public(report: Report, label: str, text: str, staging: Path) -> None:
    forbidden = [*FORBIDDEN_PUBLIC, str(staging), staging.as_posix(), str(REPO_ROOT), REPO_ROOT.as_posix()]
    leaks = [item for item in forbidden if item in text]
    report.check(f"no internal paths or source IDs in {label}", not leaks, f"found {leaks}")


def check_api(report: Report, api: str, staging: Path, expected: dict[str, dict]) -> dict[str, dict]:
    import httpx
    from PIL import Image

    step("API catalogue and media")
    response = httpx.get(f"{api}/api/v1/coastsnap/sites/{SITE_ID}/observations", params={"pageSize": 100}, timeout=10)
    report.check("API lists the site's observations", response.status_code == 200, f"HTTP {response.status_code}")
    scan_public(report, "API observation JSON", response.text, staging)
    items = {item["id"]: item for item in response.json()["items"]}
    report.check("API returns all 5 observations", len(items) == 5, f"got {len(items)}")

    for obs in WITH_DERIVATIVES:
        item = items[media_id(obs)]
        report.check(f"{obs}: thumbnail and preview URLs present", bool(item["thumbnailUrl"] and item["previewUrl"]))
        report.check(
            f"{obs}: trusted dimensions {expected[obs]['width']}x{expected[obs]['height']}",
            (item["width"], item["height"]) == (expected[obs]["width"], expected[obs]["height"]),
            f"got {item['width']}x{item['height']}",
        )
    missing = items[media_id(WITHOUT_DERIVATIVES)]
    report.check(
        f"{WITHOUT_DERIVATIVES}: no derivative URLs or dimensions",
        missing["thumbnailUrl"] is None and missing["previewUrl"] is None and missing["width"] is None,
    )
    report.check(
        "Level 0 and Level 1 download URLs present for every observation (both permitted)",
        all(item["level0DownloadAvailable"] and item["level0DownloadUrl"] and item["level1DownloadAvailable"]
            and item["level1DownloadUrl"] for item in items.values()),
    )

    sample = items[media_id(WITH_DERIVATIVES[0])]
    for kind, limit in (("thumbnail", 400), ("preview", 1600)):
        rendition = httpx.get(sample[f"{kind}Url"], timeout=10)
        ok = rendition.status_code == 200 and rendition.headers.get("content-type") == "image/jpeg"
        size = Image.open(io.BytesIO(rendition.content)).size if ok else (0, 0)
        report.check(f"{kind} response is a JPEG with longest side ≤ {limit} px", ok and max(size) <= limit and max(size) > 0,
                     f"HTTP {rendition.status_code}, size {size}")
        header_text = "\n".join(f"{k}: {v}" for k, v in rendition.headers.items())
        scan_public(report, f"{kind} headers", header_text, staging)

    manifest_sha = expected[WITH_DERIVATIVES[0]]
    downloaded: dict[str, bytes] = {}
    for level, label in (("level0", "Level 0"), ("level1", "Level 1")):
        response = httpx.get(sample[f"{level}DownloadUrl"], timeout=20)
        downloaded[level] = response.content
        disposition = response.headers.get("content-disposition", "")
        report.check(f"{label} download returns HTTP 200", response.status_code == 200, f"HTTP {response.status_code}")
        report.check(
            f"{label} download is an attachment named by the opaque media ID and level",
            disposition == f'attachment; filename="{sample["mediaId"]}_{level}.jpg"', disposition,
        )
        report.check(f"{label} content type is image/jpeg", response.headers.get("content-type") == "image/jpeg")
        digest = hashlib.sha256(response.content).hexdigest()
        report.check(f"{label} downloaded bytes match the manifest's {label} SHA-256", digest == manifest_sha[level],
                     f"{digest} != {manifest_sha[level]}")
        report.check(f"{label} ETag is the manifest {label} checksum", response.headers.get("etag") == f'"{manifest_sha[level]}"')
        report.check(f"{label} published checksum matches the manifest", sample[f"{level}ChecksumSha256"] == manifest_sha[level])
        ranged = httpx.get(sample[f"{level}DownloadUrl"], headers={"Range": "bytes=0-99"}, timeout=10)
        report.check(f"{label} supports HTTP Range requests",
                     ranged.status_code == 206 and ranged.content == response.content[:100])
        scan_public(report, f"{label} download headers", "\n".join(f"{k}: {v}" for k, v in response.headers.items()), staging)
    report.check("Level 0 and Level 1 downloads differ (Level 1 carries provenance)",
                 downloaded["level0"] != downloaded["level1"])

    alias = httpx.get(f"{api}/media/coastsnap/{sample['mediaId']}/original", timeout=20)
    report.check("deprecated /original still serves the Level 1 bytes",
                 alias.status_code == 200 and alias.content == downloaded["level1"])
    report.check("deprecated /original is marked with a Deprecation header", alias.headers.get("deprecation") == "true")

    no_fallback = True
    for kind in ("thumbnail", "preview"):
        url = f"{api}/media/coastsnap/{media_id(WITHOUT_DERIVATIVES)}/{kind}"
        response = httpx.get(url, timeout=10)
        no_fallback &= (
            response.status_code == 404
            and response.headers.get("content-type", "").startswith("application/json")
            and response.json()["error"]["code"] == f"{kind}_not_available"
        )
    report.check("missing derivative returns 404 and never falls back to Level 0 or Level 1", no_fallback)
    return items


def check_frontend(report: Report, web: str, api: str, staging: Path, items: dict[str, dict], *, downloads: bool) -> None:
    import httpx

    def page(path: str) -> str:
        response = httpx.get(f"{web}{path}", timeout=60)
        report.check(f"GET {path} → 200", response.status_code == 200, f"HTTP {response.status_code}")
        scan_public(report, f"rendered {path}", response.text, staging)
        return response.text

    derived, missing = media_id(WITH_DERIVATIVES[0]), media_id(WITHOUT_DERIVATIVES)
    if downloads:
        step("Next.js pages (API-backed)")
        index = page("/coastsnap")
        report.check("/coastsnap lists the API site", SITE_NAME in index and "5 observations" in index)
        report.check("/coastsnap renders an API thumbnail", f"{api}/media/coastsnap/" in index and "/thumbnail" in index)
        report.check("footer describes catalogue-backed CoastSnap observations",
                     "CoastSnap observations are served by the AusCIN catalogue API" in index)
        report.check("no sample-data disclaimer on API-backed pages", "Sample development record" not in index)

        archive = page(f"/coastsnap/{SITE_ID}/archive")
        # React splits "5 observations" into separate text nodes: <span>5</span> observation<!-- -->s
        report.check("archive shows the observation count", re.search(r">5</span>\s*observation", archive) is not None)
        report.check("archive renders API thumbnails", archive.count(f"{api}/media/coastsnap/") >= 3)

        detail = page(f"/coastsnap/{SITE_ID}/archive/{derived}")
        report.check("detail page renders the API preview", f"{api}/media/coastsnap/{derived}/preview" in detail)
        report.check("detail page offers both download buttons",
                     "Download original (Level 0)" in detail and "Download provenance copy (Level 1)" in detail)
        report.check("detail page links both levels at the API origin",
                     f'href="{api}/media/coastsnap/{derived}/level0"' in detail
                     and f'href="{api}/media/coastsnap/{derived}/level1"' in detail)
        report.check("detail page explains Level 0 and Level 1",
                     "untouched source image" in detail and "AusCIN provenance metadata" in detail)
        report.check("detail page shows no prototype wording or deprecated /original link",
                     "prototype demo" not in detail and "/original" not in detail)
        w, h = items[derived]["width"], items[derived]["height"]
        report.check("detail page shows trusted dimensions", f"{w} × {h}" in detail)

        missing_page = page(f"/coastsnap/{SITE_ID}/archive/{missing}")
        report.check("missing-derivative page shows the unavailable preview state", "No preview is available" in missing_page)
        img_srcs = re.findall(r'<img[^>]+src="([^"]+)"', missing_page)
        report.check("missing-derivative page never uses Level 0 or Level 1 as an image",
                     not any(re.search(r"/(level0|level1|original)$", src) for src in img_srcs), f"img srcs {img_srcs}")
    else:
        step("Next.js pages (Level 0 withheld, Level 1 permitted)")
        detail = page(f"/coastsnap/{SITE_ID}/archive/{derived}")
        report.check("partial: only the Level 1 button is rendered",
                     "Download provenance copy (Level 1)" in detail and "Download original (Level 0)" not in detail)
        report.check("partial: no Level 0 link on the page", f"{api}/media/coastsnap/{derived}/level0" not in detail)
        report.check("partial: page explains why Level 0 is unavailable",
                     "Level 0 (untouched source image) is not offered for download" in detail)
        report.check("partial: preview still rendered", f"{api}/media/coastsnap/{derived}/preview" in detail)


def check_partial_policy_api(report: Report, api: str, expected: dict[str, dict]) -> None:
    import httpx

    step("API with Level 0 withheld and Level 1 permitted")
    mid = media_id(WITH_DERIVATIVES[0])
    item = httpx.get(f"{api}/api/v1/coastsnap/sites/{SITE_ID}/observations/{mid}", timeout=10).json()
    report.check("partial: Level 0 URL, availability and checksum are withheld",
                 item["level0DownloadUrl"] is None and item["level0DownloadAvailable"] is False
                 and item["level0ChecksumSha256"] is None)
    report.check("partial: Level 1 remains available", item["level1DownloadAvailable"] is True and item["level1DownloadUrl"])
    level0 = httpx.get(f"{api}/media/coastsnap/{mid}/level0", timeout=10)
    report.check("partial: /level0 returns 403 download_not_permitted",
                 level0.status_code == 403 and level0.json()["error"]["code"] == "download_not_permitted")
    level1 = httpx.get(f"{api}/media/coastsnap/{mid}/level1", timeout=20)
    report.check("partial: /level1 still serves the Level 1 bytes",
                 level1.status_code == 200 and hashlib.sha256(level1.content).hexdigest() == expected[WITH_DERIVATIVES[0]]["level1"])
    alias = httpx.get(f"{api}/media/coastsnap/{mid}/original", timeout=20)
    report.check("partial: deprecated /original follows Level 1", alias.status_code == 200)


# --- Main ------------------------------------------------------------------------------------


def run_derivatives(staging: Path, manifest: Path, output_root: Path, index: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "coastsnap_import.derivatives", "--manifest", str(manifest), "--input-root", str(staging),
         "--output-root", str(output_root), "--index-output", str(index), "--max-images", "4"],
        capture_output=True, text=True, check=False,
    )


def api_env(staging: Path, manifest: Path, output_root: Path, index: Path, registry: Path, api: str) -> dict[str, str]:
    env = dict(os.environ)
    env.update({
        "AUSCIN_API_ENV": "development",
        "COASTSNAP_SITE_REGISTRY_PATH": str(registry),
        "COASTSNAP_MANIFEST_PATH": str(manifest),
        "COASTSNAP_DERIVATIVES_INDEX_PATH": str(index),
        "COASTSNAP_MEDIA_ROOT": str(staging),
        "COASTSNAP_DERIVATIVES_ROOT": str(output_root),
        "AUSCIN_MEDIA_BASE_URL": api,
    })
    return env


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skip-build", action="store_true", help="Reuse an existing apps/web production build (.next).")
    parser.add_argument("--keep-staging", action="store_true", help="Don't delete the temporary staging directory (for debugging).")
    parser.add_argument("--staging-parent", default=None, help="Parent for the temporary staging directory (default: system temp).")
    parser.add_argument("--npm", default=None, help="Path to npm (default: found on PATH).")
    args = parser.parse_args()

    try:
        import coastsnap_import.derivatives  # noqa: F401
        import auscin_api  # noqa: F401
        import httpx  # noqa: F401
        import PIL  # noqa: F401
    except ImportError as exc:
        raise SystemExit(f"Missing dependency ({exc.name}). Run with apps/api/.venv, which has the API and the worker[derivatives] extra.")

    npm = find_npm(args.npm)
    staging = Path(tempfile.mkdtemp(prefix="auscin-coastsnap-e2e-", dir=args.staging_parent)).resolve()
    if staging.is_relative_to(REPO_ROOT):
        shutil.rmtree(staging, ignore_errors=True)
        raise SystemExit("The staging directory must be outside the repository; pass a different --staging-parent.")

    report = Report()
    api_process: Optional[subprocess.Popen] = None
    web_process: Optional[subprocess.Popen] = None
    logs = staging / "logs"
    logs.mkdir()
    api_port, web_port = free_port(), free_port()
    api, web = f"http://127.0.0.1:{api_port}", f"http://127.0.0.1:{web_port}"
    print(f"Staging (outside the repository): {staging}")

    try:
        step("Synthetic worker manifest and Level 0/Level 1 files")
        manifest, expected = build_staging(staging)
        report.check("synthetic manifest written with the worker's models", manifest.exists())

        step("Worker derivatives command (real, run twice)")
        output_root, index = staging / "derivatives-out", staging / "derivatives-out" / "derivatives-index.json"
        first = run_derivatives(staging, manifest, output_root, index)
        print("   " + first.stdout.strip().splitlines()[-1] if first.stdout.strip() else "   (no output)")
        report.check("first run exits 0", first.returncode == 0, first.stderr.strip())
        report.check("first run processed 4 images", "processed=4 reused=0 skipped=0 failed=0" in first.stdout)
        second = run_derivatives(staging, manifest, output_root, index)
        print("   " + second.stdout.strip().splitlines()[-1] if second.stdout.strip() else "   (no output)")
        report.check("second run exits 0", second.returncode == 0, second.stderr.strip())
        report.check("second run reused all 4 derivatives", "processed=0 reused=4 skipped=0 failed=0" in second.stdout)
        # The index is an internal worker-to-API file, not a public response. By contract it holds
        # relative derivative paths and catalogue observation IDs, but never absolute, staging,
        # /g/data or source paths.
        index_text = index.read_text(encoding="utf-8")
        index_leaks = [s for s in ("/g/data", "qu34", str(staging), staging.as_posix(), json.dumps(str(staging))[1:-1],
                                   "level-1/", "example.invalid", "source-records") if s in index_text]
        report.check("derivatives index holds only relative paths and catalogue identifiers", not index_leaks,
                     f"found {index_leaks}")

        step("Start FastAPI (downloads permitted)")
        api_process = start_process(
            [sys.executable, "-m", "uvicorn", "auscin_api.main:create_app", "--factory", "--host", "127.0.0.1", "--port", str(api_port)],
            cwd=API_DIR, env=api_env(staging, manifest, output_root, index, FIXTURE_REGISTRY, api), log=logs / "api.log",
        )
        if not report.check("API healthy", wait_for(f"{api}/api/v1/health", api_process, 60)):
            raise RuntimeError("API did not start")
        items = check_api(report, api, staging, expected)

        env = node_env(npm)
        env["COASTSNAP_API_BASE_URL"] = api
        if not args.skip_build:
            step("next build")
            build = subprocess.run([npm, "run", "build"], cwd=WEB_DIR, env=env, capture_output=True, text=True, check=False)
            (logs / "web-build.log").write_text(build.stdout + build.stderr, encoding="utf-8")
            if not report.check("next build succeeded", build.returncode == 0, tail(logs / "web-build.log", 15)):
                raise RuntimeError("next build failed")

        step("Start Next.js (next start, COASTSNAP_API_BASE_URL set)")
        web_process = start_process([npm, "run", "start", "--", "-p", str(web_port), "-H", "127.0.0.1"],
                                    cwd=WEB_DIR, env=env, log=logs / "web.log")
        if not report.check("Next.js serving", wait_for(f"{web}/coastsnap", web_process, 120)):
            raise RuntimeError("Next.js did not start")
        check_frontend(report, web, api, staging, items, downloads=True)

        step("Restart FastAPI with Level 0 withheld and Level 1 permitted")
        stop_process(api_process)
        registry = json.loads(FIXTURE_REGISTRY.read_text(encoding="utf-8"))
        for site in registry["sites"]:
            site["level0_download_permitted"] = False
            site["level1_download_permitted"] = site["publication_status"] == "public"
        partial_registry = staging / "sites-registry-level1-only.json"
        partial_registry.write_text(json.dumps(registry), encoding="utf-8")
        api_process = start_process(
            [sys.executable, "-m", "uvicorn", "auscin_api.main:create_app", "--factory", "--host", "127.0.0.1", "--port", str(api_port)],
            cwd=API_DIR, env=api_env(staging, manifest, output_root, index, partial_registry, api), log=logs / "api-level1-only.log",
        )
        if not report.check("Level-1-only API healthy", wait_for(f"{api}/api/v1/health", api_process, 60)):
            raise RuntimeError("Level-1-only API did not start")
        check_partial_policy_api(report, api, expected)
        check_frontend(report, web, api, staging, items, downloads=False)
    except Exception as exc:  # noqa: BLE001 — report and fall through to cleanup
        report.check("workflow completed without an unexpected error", False, f"{type(exc).__name__}: {exc}")
        for log in sorted(logs.glob("*.log")):
            print(f"\n--- last lines of {log.name} ---\n{tail(log)}")
    finally:
        step("Cleanup")
        stop_process(web_process)
        stop_process(api_process)
        if args.keep_staging:
            print(f"  kept staging directory: {staging}")
        else:
            for _ in range(10):  # Windows can hold file handles briefly after a process exits
                shutil.rmtree(staging, ignore_errors=True)
                if not staging.exists():
                    break
                time.sleep(0.5)
            report.check("temporary staging directory removed", not staging.exists())

    print(f"\nSmoke result: {len(report.passed)} passed, {len(report.failed)} failed")
    for name in report.failed:
        print(f"  FAILED: {name}")
    return 0 if not report.failed else 1


if __name__ == "__main__":
    sys.exit(main())

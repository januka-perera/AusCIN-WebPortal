"""Environment/connectivity preflight checks for the CoastSnap importer.

Every check here is read-only and bounded: at most one lightweight
Spotteron metadata request (page=1, limit=1) to prove the API host is
reachable, no image download, and no Gadi/SFTP connection of any kind.
See cli.py's ``--preflight`` flag.

Each check function is independent and side-effect-bounded, so it can
be unit tested without a real ExifTool binary, a real Spotteron host,
or real network access — see tests/test_preflight.py.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Optional

import requests

from .metadata_embedder import EXIFTOOL_CONFIG_PATH

MIN_PYTHON_VERSION = (3, 11)
REQUIRED_PACKAGES = ("pydantic", "requests", "paramiko")
# Informational floor for the staging disk-space check, not a hard
# project requirement — a single CoastSnap image is a few MB at most.
MIN_FREE_STAGING_BYTES = 100 * 1024 * 1024


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    ok: bool
    detail: str


def check_python_version(minimum: tuple[int, int] = MIN_PYTHON_VERSION) -> PreflightCheck:
    current = sys.version_info[:2]
    ok = current >= minimum
    detail = f"{sys.version.split()[0]} (requires >= {minimum[0]}.{minimum[1]})"
    return PreflightCheck("Python version", ok, detail)


def check_python_dependencies(packages: tuple[str, ...] = REQUIRED_PACKAGES) -> list[PreflightCheck]:
    checks = []
    for package in packages:
        try:
            version = importlib_metadata.version(package)
            checks.append(PreflightCheck(f"Python package: {package}", True, f"installed ({version})"))
        except importlib_metadata.PackageNotFoundError:
            checks.append(PreflightCheck(f"Python package: {package}", False, "not installed"))
    return checks


def check_exiftool_available(exiftool_path: str) -> PreflightCheck:
    resolved = shutil.which(exiftool_path)
    if not resolved and Path(exiftool_path).exists():
        resolved = exiftool_path
    if not resolved:
        return PreflightCheck("ExifTool available", False, f"{exiftool_path!r} not found on PATH")
    return PreflightCheck("ExifTool available", True, resolved)


def check_exiftool_version(exiftool_path: str) -> PreflightCheck:
    try:
        result = subprocess.run([exiftool_path, "-ver"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as exc:
        return PreflightCheck("ExifTool version", False, f"could not run {exiftool_path!r}: {exc}")
    if result.returncode != 0:
        return PreflightCheck("ExifTool version", False, f"exit {result.returncode}: {result.stderr.strip()}")
    return PreflightCheck("ExifTool version", True, result.stdout.strip())


def check_exiftool_namespace_config(exiftool_path: str, config_path: Path = EXIFTOOL_CONFIG_PATH) -> PreflightCheck:
    """Forces exiftool to parse exiftool_config/auscin.config (any Perl
    syntax error in it surfaces immediately on ``-config``, even for an
    otherwise no-op command like ``-ver``) without touching any file."""
    if not config_path.exists():
        return PreflightCheck("ExifTool auscin namespace config", False, f"config file not found: {config_path}")
    try:
        result = subprocess.run(
            [exiftool_path, "-config", str(config_path), "-ver"], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return PreflightCheck("ExifTool auscin namespace config", False, f"could not load config: {exc}")
    if result.returncode != 0:
        return PreflightCheck(
            "ExifTool auscin namespace config", False, f"config failed to load: {result.stderr.strip()}"
        )
    return PreflightCheck("ExifTool auscin namespace config", True, f"loaded OK from {config_path}")


def check_staging_dir_writable(staging_dir: Path) -> PreflightCheck:
    try:
        staging_dir.mkdir(parents=True, exist_ok=True)
        probe = staging_dir / ".preflight-write-check"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return PreflightCheck("Staging directory writable", False, f"{staging_dir}: {exc}")
    return PreflightCheck("Staging directory writable", True, str(staging_dir))


def check_staging_dir_disk_space(staging_dir: Path, minimum_free_bytes: int = MIN_FREE_STAGING_BYTES) -> PreflightCheck:
    probe_path = staging_dir if staging_dir.exists() else staging_dir.parent
    try:
        usage = shutil.disk_usage(probe_path)
    except OSError as exc:
        return PreflightCheck("Staging directory disk space", False, f"could not stat {probe_path}: {exc}")
    free_mb = usage.free / (1024 * 1024)
    ok = usage.free >= minimum_free_bytes
    return PreflightCheck("Staging directory disk space", ok, f"{free_mb:.0f} MB free at {probe_path}")


def check_spotteron_reachable(
    base_url: str,
    api_version: str,
    topic_id: int,
    bearer_token: Optional[str],
    timeout_seconds: float = 10.0,
    session: Optional[requests.Session] = None,
) -> PreflightCheck:
    """Exactly one bounded metadata request (limit=1, page=1). Never
    downloads an image and never contacts Gadi."""
    url = f"{base_url.rstrip('/')}/api/{api_version}/spots"
    headers = {"Accept": "application/json"}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    sess = session or requests.Session()
    try:
        response = sess.get(
            url,
            params={"filter[topic_id]": topic_id, "limit": 1, "page": 1},
            headers=headers,
            timeout=timeout_seconds,
        )
    except requests.RequestException as exc:
        return PreflightCheck("Spotteron API reachable", False, f"{url}: {exc}")
    # A 4xx still proves the host answers as an API (e.g. an auth or
    # not-found response); only a network failure or a server error
    # fails this check.
    ok = response.status_code < 500
    return PreflightCheck("Spotteron API reachable", ok, f"{url} -> HTTP {response.status_code}")


def check_bearer_token_configured(bearer_token: Optional[str]) -> PreflightCheck:
    # Never print the token value itself, only whether one is set.
    if bearer_token:
        return PreflightCheck("Spotteron bearer token", True, "configured (value not shown)")
    return PreflightCheck("Spotteron bearer token", True, "not set (optional; public GET will be used)")

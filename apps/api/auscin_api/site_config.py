"""Validate the configuration for one real CoastSnap test site, and write its
reviewed registry entry. Entirely offline.

    python -m auscin_api.site_config validate --env-file <path/to/coastsnap-site.env> [--for-transfer]
    python -m auscin_api.site_config write-registry --env-file <...> --output <outside-repo>/site-registry.json

This command never contacts Spotteron, Gadi or NCI, and never reads or writes
any staged media. It checks only the values in the environment, or in an
env file overlaid on the environment, and the local path layout they imply.
The template is `apps/api/config/coastsnap-site.env.example`. Copy it
**outside** the repository before filling it in.

Rules:
- **Required and filled in:** every required value must be set and non-blank.
  Anything that still looks like a template placeholder (`<...>`,
  `CHANGE_ME`, `TODO`, `REPLACE`) is refused.
- **Site metadata:**
  - the slug must match the registry's `CS-...` pattern
  - the root ID must be a plain identifier
  - the name, region, description and attribution must be real text
  - the state must be an Australian state or territory
  - latitude and longitude must be in range
  - the time zone must be a valid IANA name
  - the establishment date must not be in the future
- **Explicit decisions:** publication status and the download permission for
  each product level must be set explicitly:
  - `COASTSNAP_SITE_LEVEL0_DOWNLOAD_PERMITTED`: the untouched source image
  - `COASTSNAP_SITE_LEVEL1_DOWNLOAD_PERMITTED`: the AusCIN provenance copy

  Each must be exactly `true` or `false`. Nothing defaults to public or
  downloadable, so no site or level is published or made downloadable
  automatically. The retired single `COASTSNAP_SITE_DOWNLOAD_PERMITTED` is
  refused with a pointer to the two replacements.
- **Local paths:** staging directory, derivatives root, manifest and
  derivatives index must be absolute, outside this repository and never
  under `/g/data`, because they are always local. The manifest must be the
  worker's default `<staging>/manifests/<root_id>.json`, so the worker and
  the API read the same file.
- **Remote publication root:** `NCI_PUBLICATION_ROOT` is the *remote* SFTP
  destination (the worker's `GADI_REMOTE_ROOT`), so it may legitimately be
  under `/g/data`. It is checked for syntax only and never accessed. It is
  required only with `--for-transfer`.

The exit code is 0 only when every check passes. No value is ever treated
as secret: this configuration holds no credentials (SFTP key settings stay
in the worker's own environment).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Optional, get_args
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ValidationError

from .schemas import SITE_ID_PATTERN, SOURCE_ID_PATTERN, PublicationStatus, SiteRegistry, StateOrTerritory

SITE_FIELDS = (
    "SPOTTERON_ROOT_ID",
    "COASTSNAP_SITE_SLUG",
    "COASTSNAP_SITE_NAME",
    "COASTSNAP_SITE_STATE",
    "COASTSNAP_SITE_REGION",
    "COASTSNAP_SITE_DESCRIPTION",
    "COASTSNAP_SITE_LATITUDE",
    "COASTSNAP_SITE_LONGITUDE",
    "COASTSNAP_SITE_TIME_ZONE",
    "COASTSNAP_SITE_ESTABLISHED_SINCE",
    "COASTSNAP_SITE_ATTRIBUTION_TEXT",
    "COASTSNAP_SITE_PUBLICATION_STATUS",
    "COASTSNAP_SITE_LEVEL0_DOWNLOAD_PERMITTED",
    "COASTSNAP_SITE_LEVEL1_DOWNLOAD_PERMITTED",
)
RETIRED_FIELDS = {
    "COASTSNAP_SITE_DOWNLOAD_PERMITTED": (
        "has been replaced by COASTSNAP_SITE_LEVEL0_DOWNLOAD_PERMITTED and COASTSNAP_SITE_LEVEL1_DOWNLOAD_PERMITTED; "
        "remove it and set both levels explicitly"
    ),
}
PATH_FIELDS = (
    "COASTSNAP_STAGING_DIR",
    "COASTSNAP_DERIVATIVES_ROOT",
    "COASTSNAP_MANIFEST_PATH",
    "COASTSNAP_DERIVATIVES_INDEX_PATH",
)
TRANSFER_FIELDS = ("NCI_PUBLICATION_ROOT",)
REQUIRED_FIELDS = SITE_FIELDS + PATH_FIELDS
ALL_FIELDS = REQUIRED_FIELDS + TRANSFER_FIELDS

PRODUCTION_STORAGE_PREFIX = "/g/data"

# Template markers only: anything in angle brackets, or an uppercase marker token.
# Deliberately case-sensitive, so ordinary prose ("installed to replace the old mark") is fine.
_PLACEHOLDER_RE = re.compile(r"<[^<>]*>|\bCHANGE_?ME\b|\bREPLACE_ME\b|\bTODO\b|\bPLACEHOLDER\b|\bTBC\b")
_SITE_ID_RE = re.compile(SITE_ID_PATTERN)
_SOURCE_ID_RE = re.compile(SOURCE_ID_PATTERN)

TEXT_LIMITS = {
    "COASTSNAP_SITE_NAME": (3, 120),
    "COASTSNAP_SITE_REGION": (2, 120),
    "COASTSNAP_SITE_DESCRIPTION": (20, 2000),
    "COASTSNAP_SITE_ATTRIBUTION_TEXT": (3, 300),
}


# --- Env file ------------------------------------------------------------------------------


class EnvFileError(Exception):
    pass


def read_env_file(path: Path) -> dict[str, str]:
    """Minimal KEY=VALUE parser: `#` comments, optional `export `, and matching single or double quotes. No interpolation."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EnvFileError(f"cannot read env file: {exc.strerror or exc}") from exc
    values: dict[str, str] = {}
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or not re.fullmatch(r"[A-Z_][A-Z0-9_]*", key):
            raise EnvFileError(f"line {number}: expected KEY=VALUE")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        values[key] = value
    return values


# --- Validation ------------------------------------------------------------------------------


@dataclass
class ValidationReport:
    errors: dict[str, list[str]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def fail(self, name: str, message: str) -> None:
        self.errors.setdefault(name, []).append(message)

    @property
    def ok(self) -> bool:
        return not self.errors


def find_repository_roots(extra: Optional[list[Path]] = None) -> list[Path]:
    """Every git work tree containing this module or the current directory (plus any explicitly given)."""
    roots: set[Path] = set()
    for start in (Path(__file__).resolve(), Path.cwd().resolve()):
        for candidate in (start, *start.parents):
            if (candidate / ".git").exists():
                roots.add(candidate)
                break
    for path in extra or []:
        roots.add(path.resolve())
    return sorted(roots)


def _is_production_storage(raw: str) -> bool:
    posix = raw.replace("\\", "/")
    return posix == PRODUCTION_STORAGE_PREFIX or posix.startswith(PRODUCTION_STORAGE_PREFIX + "/")


def _is_absolute_anywhere(raw: str) -> bool:
    return PurePosixPath(raw).is_absolute() or PureWindowsPath(raw).is_absolute()


def validate_site_config(
    env: Mapping[str, str],
    *,
    for_transfer: bool = False,
    repository_roots: Optional[list[Path]] = None,
    today: Optional[date] = None,
) -> ValidationReport:
    report = ValidationReport()
    repo_roots = repository_roots if repository_roots is not None else find_repository_roots()
    required = REQUIRED_FIELDS + (TRANSFER_FIELDS if for_transfer else ())

    for name, message in RETIRED_FIELDS.items():
        if isinstance(env.get(name), str) and env[name].strip():
            report.fail(name, message)

    values: dict[str, str] = {}
    for name in ALL_FIELDS:
        raw = env.get(name)
        value = raw.strip() if isinstance(raw, str) else ""
        if not value:
            if name in required:
                report.fail(name, "is required and must not be empty")
            continue
        if _PLACEHOLDER_RE.search(value):
            report.fail(name, "still contains a template placeholder; replace it with the real, reviewed value")
            continue
        values[name] = value

    _validate_identifiers(values, report)
    _validate_text(values, report)
    _validate_location(values, report)
    _validate_dates_and_zone(values, report, today or date.today())
    _validate_policy(values, report)
    _validate_local_paths(values, report, repo_roots)
    _validate_publication_root(values, report)
    if not for_transfer:
        report.notes.append("NCI_PUBLICATION_ROOT is only required with --for-transfer; it is never accessed by this command.")
    return report


def _validate_identifiers(values: dict[str, str], report: ValidationReport) -> None:
    root_id = values.get("SPOTTERON_ROOT_ID")
    if root_id is not None and not _SOURCE_ID_RE.fullmatch(root_id):
        report.fail("SPOTTERON_ROOT_ID", "must be a plain identifier (letters, digits, '_' or '-', at most 64 characters)")
    slug = values.get("COASTSNAP_SITE_SLUG")
    if slug is not None:
        if not slug.startswith("CS-"):
            report.fail("COASTSNAP_SITE_SLUG", "must start with 'CS-' (the CoastSnap site ID convention)")
        elif not _SITE_ID_RE.fullmatch(slug) or "--" in slug:
            report.fail(
                "COASTSNAP_SITE_SLUG",
                "must be uppercase letters, digits and single hyphens, e.g. CS-EXAMPLE-BEACH (at most 64 characters)",
            )


def _validate_text(values: dict[str, str], report: ValidationReport) -> None:
    for name, (minimum, maximum) in TEXT_LIMITS.items():
        value = values.get(name)
        if value is None:
            continue
        if not (minimum <= len(value) <= maximum):
            report.fail(name, f"must be between {minimum} and {maximum} characters")
        if any(ord(ch) < 32 for ch in value):
            report.fail(name, "must not contain control characters")
    state = values.get("COASTSNAP_SITE_STATE")
    if state is not None and state not in get_args(StateOrTerritory):
        report.fail("COASTSNAP_SITE_STATE", f"must be one of {', '.join(get_args(StateOrTerritory))}")


def _parse_float(values: dict[str, str], name: str, report: ValidationReport) -> Optional[float]:
    value = values.get(name)
    if value is None:
        return None
    try:
        number = float(value)
    except ValueError:
        report.fail(name, "must be a decimal number")
        return None
    if not math.isfinite(number):
        report.fail(name, "must be a finite number")
        return None
    return number


def _validate_location(values: dict[str, str], report: ValidationReport) -> None:
    latitude = _parse_float(values, "COASTSNAP_SITE_LATITUDE", report)
    longitude = _parse_float(values, "COASTSNAP_SITE_LONGITUDE", report)
    if latitude is not None and not -90 <= latitude <= 90:
        report.fail("COASTSNAP_SITE_LATITUDE", "must be between -90 and 90")
    if longitude is not None and not -180 <= longitude <= 180:
        report.fail("COASTSNAP_SITE_LONGITUDE", "must be between -180 and 180")
    if latitude == 0 and longitude == 0:
        report.fail("COASTSNAP_SITE_LATITUDE", "0,0 is not a plausible site location; check the coordinates")
    if latitude is not None and latitude > 0:
        report.notes.append("COASTSNAP_SITE_LATITUDE is positive (northern hemisphere); Australian sites are negative.")


def _validate_dates_and_zone(values: dict[str, str], report: ValidationReport, today: date) -> None:
    zone = values.get("COASTSNAP_SITE_TIME_ZONE")
    if zone is not None:
        try:
            ZoneInfo(zone)
        except (ZoneInfoNotFoundError, ValueError):
            report.fail("COASTSNAP_SITE_TIME_ZONE", "must be a valid IANA time zone name, e.g. Australia/Sydney")
    established = values.get("COASTSNAP_SITE_ESTABLISHED_SINCE")
    if established is not None:
        try:
            parsed = date.fromisoformat(established)
        except ValueError:
            report.fail("COASTSNAP_SITE_ESTABLISHED_SINCE", "must be an ISO date, YYYY-MM-DD")
        else:
            if parsed > today:
                report.fail("COASTSNAP_SITE_ESTABLISHED_SINCE", "must not be in the future")


def _validate_policy(values: dict[str, str], report: ValidationReport) -> None:
    status = values.get("COASTSNAP_SITE_PUBLICATION_STATUS")
    if status is not None and status not in get_args(PublicationStatus):
        report.fail("COASTSNAP_SITE_PUBLICATION_STATUS", f"must be one of {', '.join(get_args(PublicationStatus))}")
    for name in ("COASTSNAP_SITE_LEVEL0_DOWNLOAD_PERMITTED", "COASTSNAP_SITE_LEVEL1_DOWNLOAD_PERMITTED"):
        permitted = values.get(name)
        if permitted is not None and permitted not in ("true", "false"):
            report.fail(name, "must be exactly 'true' or 'false' (an explicit, reviewed decision for this product level)")


def _validate_local_paths(values: dict[str, str], report: ValidationReport, repo_roots: list[Path]) -> None:
    resolved: dict[str, Path] = {}
    for name in PATH_FIELDS:
        raw = values.get(name)
        if raw is None:
            continue
        if _is_production_storage(raw):
            report.fail(name, f"is under {PRODUCTION_STORAGE_PREFIX}; local staging must never read or write NCI project storage")
            continue
        if not _is_absolute_anywhere(raw) or not Path(raw).is_absolute():
            report.fail(name, "must be an absolute path on this machine")
            continue
        path = Path(raw).resolve()
        inside = [root for root in repo_roots if path == root or path.is_relative_to(root)]
        if inside:
            report.fail(name, "must be outside the git repository (staged media, manifests and indexes are never committed)")
            continue
        resolved[name] = path

    staging = resolved.get("COASTSNAP_STAGING_DIR")
    if staging is not None and staging.exists() and not staging.is_dir():
        report.fail("COASTSNAP_STAGING_DIR", "exists but is not a directory")
    manifest = resolved.get("COASTSNAP_MANIFEST_PATH")
    root_id = values.get("SPOTTERON_ROOT_ID")
    if manifest is not None and staging is not None and root_id is not None:
        expected = (staging / "manifests" / f"{root_id}.json").resolve()
        if manifest != expected:
            report.fail(
                "COASTSNAP_MANIFEST_PATH",
                "must be the worker's default manifest, <COASTSNAP_STAGING_DIR>/manifests/<SPOTTERON_ROOT_ID>.json",
            )
    index = resolved.get("COASTSNAP_DERIVATIVES_INDEX_PATH")
    if index is not None and index.suffix.lower() != ".json":
        report.fail("COASTSNAP_DERIVATIVES_INDEX_PATH", "must be a .json file")
    derivatives = resolved.get("COASTSNAP_DERIVATIVES_ROOT")
    if derivatives is not None and staging is not None and derivatives == staging:
        report.fail("COASTSNAP_DERIVATIVES_ROOT", "must differ from COASTSNAP_STAGING_DIR (keep derivatives separate from Level 0/1)")


def _validate_publication_root(values: dict[str, str], report: ValidationReport) -> None:
    raw = values.get("NCI_PUBLICATION_ROOT")
    if raw is None:
        return
    path = PurePosixPath(raw)
    if "\\" in raw or not path.is_absolute():
        report.fail("NCI_PUBLICATION_ROOT", "must be an absolute POSIX path on the remote (NCI) side")
    elif any(part in (".", "..") for part in raw.split("/")) or "//" in raw or raw.endswith("/"):
        report.fail("NCI_PUBLICATION_ROOT", "must not contain '.', '..', empty segments or a trailing slash")
    elif any(ch.isspace() for ch in raw):
        report.fail("NCI_PUBLICATION_ROOT", "must not contain whitespace")
    elif raw in ("/", PRODUCTION_STORAGE_PREFIX, f"{PRODUCTION_STORAGE_PREFIX}/qu34"):
        report.fail("NCI_PUBLICATION_ROOT", "must be a dedicated subdirectory, not a storage or project root")


# --- Registry --------------------------------------------------------------------------------


def build_registry(values: Mapping[str, str]) -> SiteRegistry:
    """The reviewed single-site registry, built only from validated values. Validated again by the API's own model."""
    return SiteRegistry.model_validate(
        {
            "schema_version": 1,
            "sites": [
                {
                    "site_id": values["COASTSNAP_SITE_SLUG"].strip(),
                    "spotteron_root_id": values["SPOTTERON_ROOT_ID"].strip(),
                    "name": values["COASTSNAP_SITE_NAME"].strip(),
                    "state": values["COASTSNAP_SITE_STATE"].strip(),
                    "region": values["COASTSNAP_SITE_REGION"].strip(),
                    "description": values["COASTSNAP_SITE_DESCRIPTION"].strip(),
                    "latitude": float(values["COASTSNAP_SITE_LATITUDE"]),
                    "longitude": float(values["COASTSNAP_SITE_LONGITUDE"]),
                    "display_time_zone": values["COASTSNAP_SITE_TIME_ZONE"].strip(),
                    "status": "active",
                    "established_since": values["COASTSNAP_SITE_ESTABLISHED_SINCE"].strip(),
                    "publication_status": values["COASTSNAP_SITE_PUBLICATION_STATUS"].strip(),
                    "level0_download_permitted": values["COASTSNAP_SITE_LEVEL0_DOWNLOAD_PERMITTED"].strip() == "true",
                    "level1_download_permitted": values["COASTSNAP_SITE_LEVEL1_DOWNLOAD_PERMITTED"].strip() == "true",
                    "attribution_text": values["COASTSNAP_SITE_ATTRIBUTION_TEXT"].strip(),
                    "is_synthetic": False,
                }
            ],
        }
    )


# --- CLI ---------------------------------------------------------------------------------------


def _load(args: argparse.Namespace, environ: Mapping[str, str]) -> dict[str, str]:
    values = dict(environ)
    if args.env_file:
        env_path = Path(args.env_file)
        roots = find_repository_roots()
        if any(env_path.resolve().is_relative_to(root) for root in roots) and not env_path.name.endswith(".example"):
            raise EnvFileError("the filled-in env file must live outside the repository (only *.example templates belong in git)")
        values.update(read_env_file(env_path))
    return values


def _print_report(report: ValidationReport, out) -> None:
    for name in ALL_FIELDS:
        messages = report.errors.get(name)
        if messages:
            for message in messages:
                print(f"[FAIL] {name} {message}", file=out)
        else:
            print(f"[ OK ] {name}", file=out)
    for name in RETIRED_FIELDS:
        for message in report.errors.get(name, []):
            print(f"[FAIL] {name} {message}", file=out)
    for note in report.notes:
        print(f"[NOTE] {note}", file=out)
    print(
        f"\nConfiguration {'is valid' if report.ok else 'is NOT valid'}: "
        f"{sum(len(m) for m in report.errors.values())} problem(s). No network or storage was accessed.",
        file=out,
    )


def main(argv: Optional[list[str]] = None, environ: Optional[Mapping[str, str]] = None, out=sys.stdout) -> int:
    import os

    parser = argparse.ArgumentParser(prog="python -m auscin_api.site_config", description="Offline validation of one real CoastSnap site's configuration.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("validate", "Check every value and exit 0 only if all pass."),
        ("write-registry", "Validate, then write the reviewed single-site registry JSON (outside the repository)."),
    ):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("--env-file", help="KEY=VALUE file overlaid on the environment (keep it outside the repository).")
        command.add_argument("--for-transfer", action="store_true", help="Also require NCI_PUBLICATION_ROOT (for the later SFTP transfer step).")
        if name == "write-registry":
            command.add_argument("--output", required=True, help="Registry JSON to write, outside the repository.")
    args = parser.parse_args(argv)

    try:
        values = _load(args, environ if environ is not None else os.environ)
    except EnvFileError as exc:
        print(f"[FAIL] {exc}", file=out)
        return 2

    report = validate_site_config(values, for_transfer=args.for_transfer)
    _print_report(report, out)
    if not report.ok:
        return 1
    if args.command == "validate":
        return 0

    output = Path(args.output)
    if _is_production_storage(args.output) or not output.is_absolute():
        print("[FAIL] --output must be an absolute local path, not under /g/data", file=out)
        return 2
    if any(output.resolve().is_relative_to(root) for root in find_repository_roots()):
        print("[FAIL] --output must be outside the repository (a real registry is never committed)", file=out)
        return 2
    try:
        registry = build_registry(values)
    except ValidationError as exc:  # pragma: no cover - validate_site_config already covers these rules
        print(f"[FAIL] registry rejected by the API model: {exc}", file=out)
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(registry.model_dump_json(indent=2) + "\n", encoding="utf-8")
    site = registry.sites[0]
    print(
        f"\nWrote {output.name} for {site.site_id}. Review it before starting the API:\n"
        f"  publication_status          = {site.publication_status}\n"
        f"  level0_download_permitted   = {str(site.level0_download_permitted).lower()}  (untouched source image)\n"
        f"  level1_download_permitted   = {str(site.level1_download_permitted).lower()}  (AusCIN provenance copy)\n"
        "All three come only from your explicit settings; nothing is published or made downloadable by default.",
        file=out,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Settings loaded from environment variables (names in apps/api/.env.example).

Validated eagerly so a missing or unsafe value fails at startup rather
than on the first request.

Catalogue inputs are explicit file lists, never discovered by scanning:

- one manifest: COASTSNAP_MANIFEST_PATH (and optionally COASTSNAP_DERIVATIVES_INDEX_PATH);
- several manifests: COASTSNAP_MANIFEST_PATHS (and optionally
  COASTSNAP_DERIVATIVES_INDEX_PATHS), each a list separated by os.pathsep
  (";" on Windows, ":" on POSIX). Indexes are paired with manifests by the
  root_id each records, so their order doesn't matter.

Setting both the singular and plural form of either is refused, so a
leftover value can never be silently ignored.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional, get_args
from urllib.parse import urlparse

ApiEnvironment = Literal["development", "test", "production"]

PRODUCTION_STORAGE_PREFIX = "/g/data"
"""NCI project storage. Never read outside production (see AGENTS.md)."""


class SettingsError(Exception):
    """Raised for missing or invalid configuration."""


def _same_path_key(path: Path) -> str:
    """Comparison key for duplicate detection: absolute, normalised and case-folded where the OS is.
    Purely lexical, so it never touches the filesystem."""
    return os.path.normcase(os.path.abspath(path))


def _is_under_production_storage(path: Path) -> bool:
    # Compare on a POSIX-style string so "/g/data/..." is caught on Windows too,
    # where Path("/g/data/x") renders as "\\g\\data\\x".
    posix = str(path).replace("\\", "/")
    return posix == PRODUCTION_STORAGE_PREFIX or posix.startswith(PRODUCTION_STORAGE_PREFIX + "/")


@dataclass(frozen=True)
class Settings:
    environment: ApiEnvironment
    site_registry_path: Path
    manifest_paths: tuple[Path, ...]
    """One or more worker manifests, one per site/root. Exactly these files are loaded."""
    derivatives_index_paths: tuple[Path, ...] = ()
    """Optional thumbnail/preview indexes, at most one per manifest root. A manifest without one offers no
    derivative URLs."""
    media_root: Optional[Path] = None
    """Local directory that the manifest's Level 1 paths resolve beneath. Without it, no media is served."""
    derivatives_root: Optional[Path] = None
    """Local directory that the derivatives index's paths resolve beneath (the worker's --output-root).
    Defaults to media_root."""
    media_base_url: str = ""
    """Prefix for media URLs in JSON, e.g. "http://localhost:8000". Empty means root-relative URLs."""

    def __post_init__(self) -> None:
        if self.environment not in get_args(ApiEnvironment):
            raise SettingsError(
                f"AUSCIN_API_ENV must be one of {', '.join(get_args(ApiEnvironment))}; got {self.environment!r}."
            )
        object.__setattr__(self, "manifest_paths", tuple(self.manifest_paths))
        object.__setattr__(self, "derivatives_index_paths", tuple(self.derivatives_index_paths))
        if not self.manifest_paths:
            raise SettingsError("COASTSNAP_MANIFEST_PATH or COASTSNAP_MANIFEST_PATHS is required.")
        for name, paths in (
            ("COASTSNAP_MANIFEST_PATHS", self.manifest_paths),
            ("COASTSNAP_DERIVATIVES_INDEX_PATHS", self.derivatives_index_paths),
        ):
            keys = [_same_path_key(path) for path in paths]
            if len(set(keys)) != len(keys):
                raise SettingsError(f"{name} lists the same file more than once.")
        for name, path in (
            ("COASTSNAP_SITE_REGISTRY_PATH", self.site_registry_path),
            *(("COASTSNAP_MANIFEST_PATH(S)", path) for path in self.manifest_paths),
            *(("COASTSNAP_DERIVATIVES_INDEX_PATH(S)", path) for path in self.derivatives_index_paths),
            ("COASTSNAP_MEDIA_ROOT", self.media_root),
            ("COASTSNAP_DERIVATIVES_ROOT", self.derivatives_root),
        ):
            if path is not None and self.environment != "production" and _is_under_production_storage(path):
                raise SettingsError(
                    f"{name} points under {PRODUCTION_STORAGE_PREFIX}, which is never read outside production."
                )
        if self.derivatives_root is not None and self.media_root is None:
            raise SettingsError("COASTSNAP_DERIVATIVES_ROOT requires COASTSNAP_MEDIA_ROOT to be set as well.")
        if self.media_base_url:
            parsed = urlparse(self.media_base_url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.path not in ("", "/") \
                    or parsed.query or parsed.fragment:
                raise SettingsError("AUSCIN_MEDIA_BASE_URL must be an http(s) origin such as http://localhost:8000.")
            object.__setattr__(self, "media_base_url", self.media_base_url.rstrip("/"))

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "Settings":
        source = env if env is not None else os.environ

        def _optional_path(name: str) -> Optional[Path]:
            value = (source.get(name) or "").strip()
            return Path(value) if value else None

        def _required_path(name: str) -> Path:
            path = _optional_path(name)
            if path is None:
                raise SettingsError(f"{name} is required.")
            return path

        def _path_list(single: str, plural: str) -> tuple[Path, ...]:
            single_path = _optional_path(single)
            plural_value = (source.get(plural) or "").strip()
            if single_path is not None and plural_value:
                raise SettingsError(f"Set either {single} or {plural}, not both.")
            if not plural_value:
                return (single_path,) if single_path is not None else ()
            entries = [entry.strip() for entry in plural_value.split(os.pathsep)]
            if any(not entry for entry in entries):
                raise SettingsError(f"{plural} has an empty entry; separate paths with {os.pathsep!r}.")
            return tuple(Path(entry) for entry in entries)

        return cls(
            environment=(source.get("AUSCIN_API_ENV") or "development").strip(),  # type: ignore[arg-type]
            site_registry_path=_required_path("COASTSNAP_SITE_REGISTRY_PATH"),
            manifest_paths=_path_list("COASTSNAP_MANIFEST_PATH", "COASTSNAP_MANIFEST_PATHS"),
            derivatives_index_paths=_path_list("COASTSNAP_DERIVATIVES_INDEX_PATH", "COASTSNAP_DERIVATIVES_INDEX_PATHS"),
            media_root=_optional_path("COASTSNAP_MEDIA_ROOT"),
            derivatives_root=_optional_path("COASTSNAP_DERIVATIVES_ROOT"),
            media_base_url=(source.get("AUSCIN_MEDIA_BASE_URL") or "").strip(),
        )

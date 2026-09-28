"""Settings loaded from environment variables (names in apps/api/.env.example).

Validated eagerly so a missing or unsafe value fails at startup rather
than on the first request.
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


def _is_under_production_storage(path: Path) -> bool:
    # Compare on a POSIX-style string so "/g/data/..." is caught on Windows too,
    # where Path("/g/data/x") renders as "\\g\\data\\x".
    posix = str(path).replace("\\", "/")
    return posix == PRODUCTION_STORAGE_PREFIX or posix.startswith(PRODUCTION_STORAGE_PREFIX + "/")


@dataclass(frozen=True)
class Settings:
    environment: ApiEnvironment
    site_registry_path: Path
    manifest_path: Path
    derivatives_index_path: Optional[Path] = None
    """Optional thumbnail/preview index. Without it, no derivative URLs are offered."""
    media_root: Optional[Path] = None
    """Local directory that the manifest's and index's relative paths resolve beneath. Without it, no media is served."""
    media_base_url: str = ""
    """Prefix for media URLs in JSON, e.g. "http://localhost:8000". Empty means root-relative URLs."""

    def __post_init__(self) -> None:
        if self.environment not in get_args(ApiEnvironment):
            raise SettingsError(
                f"AUSCIN_API_ENV must be one of {', '.join(get_args(ApiEnvironment))}; got {self.environment!r}."
            )
        for name, path in (
            ("COASTSNAP_SITE_REGISTRY_PATH", self.site_registry_path),
            ("COASTSNAP_MANIFEST_PATH", self.manifest_path),
            ("COASTSNAP_DERIVATIVES_INDEX_PATH", self.derivatives_index_path),
            ("COASTSNAP_MEDIA_ROOT", self.media_root),
        ):
            if path is not None and self.environment != "production" and _is_under_production_storage(path):
                raise SettingsError(
                    f"{name} points under {PRODUCTION_STORAGE_PREFIX}, which is never read outside production."
                )
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

        return cls(
            environment=(source.get("AUSCIN_API_ENV") or "development").strip(),  # type: ignore[arg-type]
            site_registry_path=_required_path("COASTSNAP_SITE_REGISTRY_PATH"),
            manifest_path=_required_path("COASTSNAP_MANIFEST_PATH"),
            derivatives_index_path=_optional_path("COASTSNAP_DERIVATIVES_INDEX_PATH"),
            media_root=_optional_path("COASTSNAP_MEDIA_ROOT"),
            media_base_url=(source.get("AUSCIN_MEDIA_BASE_URL") or "").strip(),
        )

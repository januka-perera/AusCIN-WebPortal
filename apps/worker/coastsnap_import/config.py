"""Configuration model for the CoastSnap importer.

Loaded from environment variables (names documented in
apps/worker/.env.example) with CLI arguments taking precedence where
both are given. Validated eagerly, before any network call, so a
missing/malformed value fails fast rather than mid-run.

Never logs or reprs a secret value in full — see __repr__ below.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, field_validator

DEFAULT_SPOTTERON_API_VERSION = "v2.4"
DEFAULT_SPOTTERON_TOPIC_ID = 37
DEFAULT_SPOTTERON_PAGE_LIMIT = 50
DEFAULT_REMOTE_ROOT = "/g/data/qu34/AusCIN/coastsnap-test"
DEFAULT_MAX_IMAGES = 5

MetadataBackendName = Literal["exiftool", "argus"]


class ConfigError(Exception):
    """Raised for missing or invalid configuration. Never wraps a secret value into the message."""


def _redact(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    return "<redacted>"


class WorkerConfig(BaseModel):
    # Spotteron
    spotteron_base_url: str
    spotteron_api_version: str = DEFAULT_SPOTTERON_API_VERSION
    spotteron_topic_id: int = DEFAULT_SPOTTERON_TOPIC_ID
    spotteron_bearer_token: Optional[str] = None
    spotteron_page_limit: int = DEFAULT_SPOTTERON_PAGE_LIMIT

    # Local processing
    staging_dir: Path
    metadata_backend: MetadataBackendName = "exiftool"
    exiftool_path: str = "exiftool"

    # Gadi SFTP (only required when an actual transfer is attempted — see require_transfer_fields)
    gadi_sftp_host: Optional[str] = None
    gadi_sftp_port: int = 22
    gadi_sftp_username: Optional[str] = None
    gadi_sftp_private_key_path: Optional[Path] = None
    remote_root: str = DEFAULT_REMOTE_ROOT

    @field_validator("spotteron_base_url")
    @classmethod
    def _base_url_must_be_http(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("spotteron_base_url must start with http:// or https://")
        return value.rstrip("/")

    @field_validator("spotteron_topic_id", "spotteron_page_limit", "gadi_sftp_port")
    @classmethod
    def _must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be a positive integer")
        return value

    def require_transfer_fields(self) -> None:
        """Called only when an actual SFTP transfer is about to be attempted (not for --dry-run)."""
        missing = [
            name
            for name, value in (
                ("gadi_sftp_host", self.gadi_sftp_host),
                ("gadi_sftp_username", self.gadi_sftp_username),
                ("gadi_sftp_private_key_path", self.gadi_sftp_private_key_path),
            )
            if not value
        ]
        if missing:
            raise ConfigError(
                "Missing required configuration for SFTP transfer: " + ", ".join(missing)
            )
        if self.gadi_sftp_private_key_path and not self.gadi_sftp_private_key_path.exists():
            raise ConfigError(
                f"gadi_sftp_private_key_path does not exist: {self.gadi_sftp_private_key_path}"
            )

    def __repr__(self) -> str:  # never leak the bearer token or key path contents
        return (
            f"WorkerConfig(spotteron_base_url={self.spotteron_base_url!r}, "
            f"spotteron_api_version={self.spotteron_api_version!r}, "
            f"spotteron_topic_id={self.spotteron_topic_id!r}, "
            f"spotteron_bearer_token={_redact(self.spotteron_bearer_token)!r}, "
            f"staging_dir={str(self.staging_dir)!r}, "
            f"metadata_backend={self.metadata_backend!r}, "
            f"gadi_sftp_host={self.gadi_sftp_host!r}, "
            f"gadi_sftp_username={self.gadi_sftp_username!r}, "
            f"gadi_sftp_private_key_path={str(self.gadi_sftp_private_key_path) if self.gadi_sftp_private_key_path else None!r}, "
            f"remote_root={self.remote_root!r})"
        )

    __str__ = __repr__

    @classmethod
    def from_env(cls, env: Optional[dict] = None, **overrides) -> "WorkerConfig":
        """Builds config from environment variables, then applies any keyword overrides (e.g. from CLI args)."""
        source = env if env is not None else os.environ

        def _int_or(name: str, default: int) -> int:
            raw = source.get(name)
            return int(raw) if raw else default

        base_url = overrides.pop("spotteron_base_url", None) or source.get("SPOTTERON_BASE_URL")
        if not base_url:
            raise ConfigError("SPOTTERON_BASE_URL is required (env var or --spotteron-base-url).")

        staging_dir = overrides.pop("staging_dir", None) or source.get("COASTSNAP_STAGING_DIR")
        if not staging_dir:
            raise ConfigError("COASTSNAP_STAGING_DIR is required (env var or --staging-dir).")

        key_path = overrides.pop("gadi_sftp_private_key_path", None) or source.get(
            "GADI_SFTP_PRIVATE_KEY_PATH"
        )

        values = dict(
            spotteron_base_url=base_url,
            spotteron_api_version=source.get("SPOTTERON_API_VERSION", DEFAULT_SPOTTERON_API_VERSION),
            spotteron_topic_id=_int_or("SPOTTERON_TOPIC_ID", DEFAULT_SPOTTERON_TOPIC_ID),
            spotteron_bearer_token=source.get("SPOTTERON_BEARER_TOKEN") or None,
            spotteron_page_limit=_int_or("SPOTTERON_PAGE_LIMIT", DEFAULT_SPOTTERON_PAGE_LIMIT),
            staging_dir=Path(staging_dir),
            metadata_backend=source.get("COASTSNAP_METADATA_BACKEND", "exiftool") or "exiftool",
            exiftool_path=source.get("EXIFTOOL_PATH", "exiftool") or "exiftool",
            gadi_sftp_host=source.get("GADI_SFTP_HOST") or None,
            gadi_sftp_port=_int_or("GADI_SFTP_PORT", 22),
            gadi_sftp_username=source.get("GADI_SFTP_USERNAME") or None,
            gadi_sftp_private_key_path=Path(key_path) if key_path else None,
            remote_root=source.get("GADI_REMOTE_ROOT") or DEFAULT_REMOTE_ROOT,
        )
        values.update(overrides)
        try:
            return cls(**values)
        except ValueError as exc:  # pydantic ValidationError subclasses ValueError
            raise ConfigError(str(exc)) from exc

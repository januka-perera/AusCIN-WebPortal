"""Metadata embedding backends.

``MetadataFields`` is a deliberately narrow, whitelist-only model: it
has a field for every *approved* item (source platform, Spotteron
root/observation/media IDs, capture timestamp, latitude, longitude,
contributor attribution, processing software+version) and nothing
else. There is no field for a token, password, private key, or
filesystem path, so an embedder physically cannot leak one — the
"never embed" list is enforced by the model's shape, not by a runtime
check that could be forgotten.

Per the brief: prefer an Argus XMP Embedder if its interface is
available; it is not available anywhere in this repository or its
dependencies, so ``ArgusXmpEmbedder`` below is a named seam that
raises ``NotImplementedError`` rather than guessing an API. ExifTool
is the working, XMP-capable implementation used by default. This
module never falls back to an EXIF-only backend (e.g. piexif) when XMP
is required — there is no such backend defined here at all.
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Protocol

from pydantic import BaseModel

_CONFIG_PATH = Path(__file__).parent / "exiftool_config" / "auscin.config"


class MetadataEmbeddingError(Exception):
    """Raised when embedding fails or the requested backend cannot run."""


class MetadataFields(BaseModel):
    """The complete, approved set of fields a backend may embed. See module docstring."""

    source_platform: str = "spotteron"
    root_id: str
    observation_id: str
    media_reference: Optional[str] = None
    captured_at_utc: Optional[datetime] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    contributor_attribution: Optional[str] = None
    """Set only when the source record's attribution-permitted signal was truthy — see image_resolver.resolve_attribution_permitted. Never a contributor's private contact details, only a display credit."""
    processing_software: str
    processing_version: str


class MetadataEmbedder(Protocol):
    def embed(self, file_path: Path, fields: MetadataFields) -> list[str]:
        """Embeds ``fields`` into the file at ``file_path`` in place.
        Returns the list of field names actually written (a backend may
        not support every field). Raises MetadataEmbeddingError on
        failure — never partially embeds and reports success."""
        ...


class ArgusXmpEmbedder:
    """Placeholder seam for the "Argus XMP Embedder" named in the brief.

    Its invocation interface (library import, CLI, or service call) is
    not documented anywhere in this repository or its dependencies, so
    it cannot be implemented without inventing an API. This raises
    NotImplementedError rather than guessing — see the implementation
    report's "unresolved assumptions" section.
    """

    def embed(self, file_path: Path, fields: MetadataFields) -> list[str]:
        raise NotImplementedError(
            "ArgusXmpEmbedder is not implemented: no Argus XMP Embedder interface or "
            "documentation is available in this repository. Set "
            "COASTSNAP_METADATA_BACKEND=exiftool, or supply the real Argus invocation "
            "details so this class can be completed."
        )


class ExifToolXmpEmbedder:
    """Embeds approved metadata as XMP (plus mirrored standard EXIF/GPS
    tags where a natural tag exists) using the ``exiftool`` CLI.
    Requires the ``exiftool`` binary to be installed and reachable at
    ``exiftool_path`` (default: found on PATH).

    Custom Spotteron-ID fields are written into a project-defined
    ``XMP-auscin`` namespace, registered via
    ``exiftool_config/auscin.config`` (loaded with ``-config``) — see
    that file's own docstring for the (unregistered, PoC-only)
    namespace URI.
    """

    def __init__(self, exiftool_path: str = "exiftool", config_path: Path = _CONFIG_PATH):
        self._exiftool_path = exiftool_path
        self._config_path = config_path

    def _build_args(self, file_path: Path, fields: MetadataFields) -> tuple[list[str], list[str]]:
        args: list[str] = [
            self._exiftool_path,
            "-config",
            str(self._config_path),
            "-overwrite_original",
            "-charset",
            "utf8",
        ]
        written: list[str] = []

        def add(tag: str, value: object) -> None:
            if value is None or value == "":
                return
            args.append(f"-{tag}={value}")
            written.append(tag)

        add("XMP-dc:Source", fields.source_platform)
        add("XMP-auscin:SourcePlatform", fields.source_platform)
        add("XMP-auscin:SpotteronRootId", str(fields.root_id))
        add("XMP-auscin:SpotteronObservationId", str(fields.observation_id))
        if fields.media_reference:
            add("XMP-auscin:SpotteronMediaReference", fields.media_reference)

        if fields.captured_at_utc:
            add("XMP-photoshop:DateCreated", fields.captured_at_utc.isoformat())
            add("EXIF:DateTimeOriginal", fields.captured_at_utc.strftime("%Y:%m:%d %H:%M:%S"))

        if fields.latitude is not None:
            add("EXIF:GPSLatitude", abs(fields.latitude))
            add("EXIF:GPSLatitudeRef", "N" if fields.latitude >= 0 else "S")
        if fields.longitude is not None:
            add("EXIF:GPSLongitude", abs(fields.longitude))
            add("EXIF:GPSLongitudeRef", "E" if fields.longitude >= 0 else "W")

        if fields.contributor_attribution:
            add("XMP-dc:Creator", fields.contributor_attribution)

        add("XMP-xmp:CreatorTool", f"{fields.processing_software}/{fields.processing_version}")

        args.append(str(file_path))
        return args, written

    def embed(self, file_path: Path, fields: MetadataFields) -> list[str]:
        if not self._config_path.exists():
            raise MetadataEmbeddingError(f"ExifTool config not found at {self._config_path}")

        args, written = self._build_args(file_path, fields)
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as exc:
            raise MetadataEmbeddingError(
                f"Failed to invoke exiftool at {self._exiftool_path!r}: {exc}. "
                "Is exiftool installed and on PATH (or EXIFTOOL_PATH set)?"
            ) from exc

        if result.returncode != 0:
            raise MetadataEmbeddingError(
                f"exiftool failed for {file_path.name} (exit {result.returncode}): {result.stderr.strip()}"
            )
        return written


def build_embedder(backend: str, exiftool_path: str = "exiftool") -> MetadataEmbedder:
    if backend == "exiftool":
        return ExifToolXmpEmbedder(exiftool_path=exiftool_path)
    if backend == "argus":
        return ArgusXmpEmbedder()
    raise MetadataEmbeddingError(f"Unknown metadata backend: {backend!r}")

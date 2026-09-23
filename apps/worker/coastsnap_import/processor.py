"""Level 0 download and Level 0 -> Level 1 copy.

Hard requirement: Level 0 must remain byte-for-byte unchanged, and
Level 1 must be a plain copy of Level 0 with metadata embedded into
the copy only — no decode, resize, recompress or re-encode. This
module therefore never opens the image with an image-decoding library;
it only streams bytes to disk and copies bytes on disk.
"""

from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

from .models import ChecksumInfo, Level0Product, Level1Product, ProcessingDetails, ProductLevel

CHUNK_SIZE = 1024 * 1024


class ProcessingError(Exception):
    """Raised when a Level 0 download or Level 0 -> Level 1 copy fails."""


def infer_extension(url: str, content_type: Optional[str]) -> str:
    """Best-effort file extension, preferring the URL's own suffix (so
    Level 0 is stored under its real format rather than an assumed
    ``.jpg`` — Spotteron originals are not confirmed to always be
    JPEG). Falls back to a small content-type map, then ``.bin``.
    """
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix and len(suffix) <= 5:
        return suffix
    content_type_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/heic": ".heic",
        "image/webp": ".webp",
    }
    if content_type:
        for key, ext in content_type_map.items():
            if key in content_type:
                return ext
    return ".bin"


def compute_sha256(path: Path) -> ChecksumInfo:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return ChecksumInfo(sha256=digest.hexdigest(), computed_at_utc=datetime.now(timezone.utc))


class Level0Level1Processor:
    def __init__(self, staging_dir: Path, session: Optional[requests.Session] = None, timeout_seconds: float = 60.0):
        self._staging_dir = staging_dir
        self._session = session or requests.Session()
        self._timeout_seconds = timeout_seconds

    def download_level0(
        self,
        product_id: str,
        observation_id: str,
        image_url: str,
        remote_relative_path: str,
    ) -> Level0Product:
        """Streams ``image_url`` to the Level 0 staging path in one pass,
        computing the checksum as it downloads. Never re-reads the URL
        and never rewrites the file afterwards — Level 0 is immutable
        from this point on.
        """
        local_path = self._staging_dir / remote_relative_path
        local_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            response = self._session.get(image_url, stream=True, timeout=self._timeout_seconds)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ProcessingError(f"Failed to download Level 0 image from {image_url}: {exc}") from exc

        digest = hashlib.sha256()
        size = 0
        tmp_path = local_path.with_suffix(local_path.suffix + ".downloading")
        try:
            with tmp_path.open("wb") as file:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if not chunk:
                        continue
                    file.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
        except OSError as exc:
            raise ProcessingError(f"Failed to write Level 0 file for {observation_id}: {exc}") from exc
        finally:
            response.close()

        if size == 0:
            tmp_path.unlink(missing_ok=True)
            raise ProcessingError(f"Downloaded Level 0 image for {observation_id} was empty: {image_url}")

        tmp_path.replace(local_path)  # atomic on the same filesystem

        return Level0Product(
            product_id=product_id,
            parent_observation_id=observation_id,
            source_url=image_url,
            local_relative_path=str(remote_relative_path),
            remote_relative_path=str(remote_relative_path),
            file_size_bytes=size,
            content_type=response.headers.get("Content-Type"),
            checksum=ChecksumInfo(sha256=digest.hexdigest(), computed_at_utc=datetime.now(timezone.utc)),
            downloaded_at_utc=datetime.now(timezone.utc),
        )

    def copy_level0_to_level1_path(self, level0: Level0Product, level1_remote_relative_path: str) -> Path:
        """Byte-for-byte copy (no decode/re-encode) of the Level 0 file to
        the Level 1 staging path. Returns the local path so the caller
        can embed metadata into it and then compute its final checksum
        (see finalize_level1)."""
        source_path = self._staging_dir / level0.local_relative_path
        destination_path = self._staging_dir / level1_remote_relative_path
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(source_path, destination_path)  # copy2 preserves bytes + mtime; no re-encode
        except OSError as exc:
            raise ProcessingError(f"Failed to copy Level 0 to Level 1 path: {exc}") from exc
        return destination_path

    def finalize_level1(
        self,
        level0: Level0Product,
        level1_local_path: Path,
        level1_remote_relative_path: str,
        embedded_metadata_fields: list[str],
        embedder_backend: str,
        processing_software: str,
        processing_version: str,
    ) -> Level1Product:
        """Computes the Level 1 checksum AFTER metadata embedding (the
        checksum must reflect what will actually be transferred) and
        builds the Level1Product record."""
        checksum = compute_sha256(level1_local_path)
        return Level1Product(
            product_id=f"{level0.parent_observation_id}-L1",
            parent_product_id=level0.product_id,
            parent_observation_id=level0.parent_observation_id,
            local_relative_path=str(level1_remote_relative_path),
            remote_relative_path=str(level1_remote_relative_path),
            file_size_bytes=level1_local_path.stat().st_size,
            checksum=checksum,
            processing=ProcessingDetails(
                embedder_backend=embedder_backend,
                embedded_metadata_fields=embedded_metadata_fields,
                processing_software=processing_software,
                processing_version=processing_version,
                processed_at_utc=datetime.now(timezone.utc),
            ),
        )

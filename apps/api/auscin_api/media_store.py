"""Media storage abstraction.

A `MediaStore` turns a *trusted* relative path, which only ever comes from
catalogue records validated at load time, into a readable local file. It is
never given a value taken from a request. Paths are validated again here as
defence in depth, and the fully resolved path, with symlinks followed, must
stay inside the configured root.

Only `LocalMediaStore` exists in this milestone. Production storage routing,
such as NCI redirects or read-only mounts, is out of scope. See
docs/implementation/coastsnap-single-site-publication.md, section 5.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

from .paths import UnsafePathError, safe_path_segments

logger = logging.getLogger(__name__)


class MediaUnavailableError(Exception):
    """The file cannot be served: it is missing, unreadable, or its path was rejected.

    Callers map this to a controlled response. The message is for server logs only.
    """


class MediaStore(Protocol):
    def resolve(self, relative_path: str) -> Path:
        """Returns a readable local file for a trusted relative path, or raises MediaUnavailableError."""
        ...


class LocalMediaStore:
    def __init__(self, root: Path):
        try:
            resolved = root.resolve(strict=True)
        except OSError as exc:
            raise ValueError("media root does not exist or is not accessible") from exc
        if not resolved.is_dir():
            raise ValueError("media root is not a directory")
        self._root = resolved

    def resolve(self, relative_path: str) -> Path:
        try:
            segments = safe_path_segments(relative_path)
        except UnsafePathError as exc:
            logger.warning("Rejected unsafe media path: %s", exc)
            raise MediaUnavailableError("unsafe path") from exc

        candidate = self._root.joinpath(*segments)
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as exc:  # FileNotFoundError, PermissionError, symlink loops, ...
            raise MediaUnavailableError("file missing or unreadable") from exc

        # Catches symlinks and junctions that point outside the root.
        if not resolved.is_relative_to(self._root):
            logger.warning("Rejected media path that resolves outside the media root")
            raise MediaUnavailableError("resolved path escapes media root")
        if not resolved.is_file():
            raise MediaUnavailableError("not a regular file")
        return resolved

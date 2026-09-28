"""Relative-path safety rules shared by the catalogue loader and the media store.

A trusted relative path is a plain, forward-slash, relative POSIX path whose
segments are ordinary file or directory names. Anything else is rejected
rather than normalised: normalising a suspicious path hides the fact that the
input was wrong.
"""

from __future__ import annotations

import re
from typing import Optional

_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")


class UnsafePathError(ValueError):
    """Raised for a relative path that fails the safety rules. The message never includes the path itself."""


def safe_path_segments(value: str, *, required_prefix: Optional[str] = None) -> list[str]:
    """Validates ``value`` and returns its segments.

    Rejects:
    - empty paths and NUL bytes
    - backslashes, which also covers Windows and UNC forms such as ``\\\\server\\share``
    - absolute POSIX paths and Windows drive paths (``C:/``, ``c:x``)
    - ``:`` anywhere, which blocks drive letters and NTFS alternate data streams
    - empty, ``.`` and ``..`` segments
    - segments ending in a dot or space, which Windows silently strips
    - paths outside ``required_prefix``, when one is given
    """
    if not value:
        raise UnsafePathError("empty path")
    if "\x00" in value:
        raise UnsafePathError("path contains a NUL byte")
    if "\\" in value:
        raise UnsafePathError("path contains a backslash")
    if value.startswith("/") or _WINDOWS_DRIVE_RE.match(value):
        raise UnsafePathError("absolute paths are not allowed")
    if ":" in value:
        raise UnsafePathError("path contains a colon")
    segments = value.split("/")
    if any(segment in ("", ".", "..") for segment in segments):
        raise UnsafePathError("path traversal or empty segments are not allowed")
    if any(segment.endswith((".", " ")) for segment in segments):
        raise UnsafePathError("path segment ends with a dot or space")
    if required_prefix is not None and not value.startswith(required_prefix):
        raise UnsafePathError(f"path is outside the expected {required_prefix!r} tree")
    return segments

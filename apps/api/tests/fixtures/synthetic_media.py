"""Synthetic JPEG media for tests and local development — never real photos.

Every file is the same 8x6 flat-colour JPEG with a distinguishing JPEG
comment (COM) segment inserted after the SOI marker, so each file is a
valid, unique, deterministic image. The committed fixture manifest's Level 1
checksums and sizes are computed from these bytes, so the ETag served by the
API can be checked against the served content.

Generate a local media root for `uvicorn` (git-ignored location):

    .venv\\Scripts\\python.exe tests\\fixtures\\synthetic_media.py .local-media
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path

# 8x6 flat grey-blue JPEG (631 bytes), generated once with Pillow.
_BASE_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDABALDA4MChAODQ4SERATGCgaGBYWGDEjJR0oOjM9PDkzODdASFxOQERXRTc4UG1RV19iZ2hnPk1x"
    "eXBkeFxlZ2P/2wBDARESEhgVGC8aGi9jQjhCY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2P/wAAR"
    "CAAGAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEG"
    "E1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWG"
    "h4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEB"
    "AQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYk"
    "NOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0"
    "tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwCOiiitjnP/2Q=="
)


def synthetic_jpeg(label: str) -> bytes:
    """A valid JPEG whose COM segment carries ``label`` (ASCII)."""
    payload = f"AusCIN synthetic test media - {label}".encode("ascii")
    segment = b"\xff\xfe" + (len(payload) + 2).to_bytes(2, "big") + payload
    return _BASE_JPEG[:2] + segment + _BASE_JPEG[2:]


def level_bytes(observation_id: str, level: int) -> bytes:
    return synthetic_jpeg(f"{observation_id} level{level}")


def derivative_bytes(observation_id: str, kind: str) -> bytes:
    return synthetic_jpeg(f"{observation_id} {kind}")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(root: Path, relative_path: str, data: bytes) -> None:
    target = root.joinpath(*relative_path.split("/"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def build_media_root(
    root: Path, manifest_path: Path, derivatives_index_path: Path, derivatives_root: Path | None = None
) -> Path:
    """Writes every Level 1 file referenced by the fixture manifest under ``root``, and every
    derivative in the (schema_version 2) fixture index under ``derivatives_root`` (default: ``root``)."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["entries"]:
        level1 = entry.get("level1")
        if level1:
            _write(root, level1["local_relative_path"], level_bytes(entry["observation"]["observation_id"], 1))
    index = json.loads(derivatives_index_path.read_text(encoding="utf-8"))
    for item in index["derivatives"]:
        for kind in ("thumbnail", "preview"):
            rendition = item.get(kind)
            if rendition:
                _write(derivatives_root or root, rendition["relative_path"], derivative_bytes(item["observation_id"], kind))
    return root


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: synthetic_media.py <output-media-root>")
    fixtures = Path(__file__).parent / "coastsnap"
    out = build_media_root(Path(sys.argv[1]), fixtures / "manifest.json", fixtures / "derivatives-index.json")
    print(f"Synthetic media written under {out.resolve()}")

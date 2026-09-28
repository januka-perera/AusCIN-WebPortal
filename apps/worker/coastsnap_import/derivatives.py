"""Thumbnail and preview generation from Level 1 files.

A separate, explicit command. It never runs as part of --plan-only,
--process-local or --transfer, and it makes no Spotteron or Gadi
connection at all:

    python -m coastsnap_import.derivatives \\
        --manifest <staging>/manifests/<root_id>.json \\
        --input-root <staging> \\
        --output-root <derivatives-root> \\
        --index-output <derivatives-root>/derivatives-index.json \\
        [--max-images N]

For every manifest entry with a Level 1 product, the command does the following:

1. Resolves the entry's Level 1 path, but only from the manifest's trusted
   relative path. The path must be a plain relative path inside
   ``level-1/root-<root_id>/``, and the resolved file must stay inside
   ``--input-root``.
2. Checks that the file exists and that its size and SHA-256 match the
   manifest *before* it is decoded.
3. Writes a thumbnail with a longest side of at most 400 px and a preview with
   a longest side of at most 1600 px. Aspect ratio is preserved, images are
   never upscaled, and EXIF orientation is applied so browsers show the
   image upright. The output is a baseline RGB JPEG with **no embedded
   metadata**, so GPS and other EXIF/XMP data never reach a public
   rendition.
4. Reuses an existing derivative instead of regenerating it when the
   previous index recorded it for the same source checksum and the same
   derivative spec, and the file on disk still matches the recorded
   checksum and size.

Output paths are deterministic and relative to ``--output-root``:

    derivatives/thumbnails/root-<root_id>/<yyyy>/<mm>/<dd>/<observation_id>.jpg
    derivatives/previews/root-<root_id>/<yyyy>/<mm>/<dd>/<observation_id>.jpg

The index lists only relative paths, catalogue identifiers (observation ID,
Level 1 product ID), checksums, sizes, dimensions and content types. It never
contains an absolute path, a /g/data path, a credential or a raw Spotteron
record. It describes the observations handled in *this* run. With
``--max-images``, observations beyond the limit are not listed.

Level 0 and Level 1 files are only ever read, never modified.

Pillow is needed only by this command. Install it with the worker's
``derivatives`` extra (``pip install -e ".[derivatives]"``).

Exit codes: 0 when every attempted image succeeded, 1 when any required
source failed (missing, checksum mismatch, undecodable or unsupported), and
2 for configuration errors.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from . import __version__
from .models import LEVEL1_DIR, Manifest, ManifestEntry, build_site_directory_id
from .processor import compute_sha256

DERIVATIVES_DIR = "derivatives"
THUMBNAILS_DIR = f"{DERIVATIVES_DIR}/thumbnails"
PREVIEWS_DIR = f"{DERIVATIVES_DIR}/previews"
DERIVATIVE_CONTENT_TYPE = "image/jpeg"
INDEX_SCHEMA_VERSION = 2
PRODUCTION_STORAGE_PREFIX = "/g/data"

DerivativeKind = Literal["thumbnail", "preview"]

SUPPORTED_SOURCE_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})
"""Pillow format names accepted as Level 1 sources. Anything else fails explicitly, including formats Pillow can't open at all, such as HEIC."""

MAX_SOURCE_PIXELS = 100_000_000
"""Refuse to decode absurdly large images (roughly 5x a 20 MP phone photo) instead of risking memory exhaustion."""


class DerivativeSpec(BaseModel):
    """Everything that determines a derivative's bytes. A change here invalidates reuse."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_dimension: int
    jpeg_quality: int


SPECS: dict[DerivativeKind, DerivativeSpec] = {
    "thumbnail": DerivativeSpec(max_dimension=400, jpeg_quality=80),
    "preview": DerivativeSpec(max_dimension=1600, jpeg_quality=85),
}


# --- Index models (the contract apps/api consumes) -----------------------------


class DerivativeFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relative_path: str
    content_type: Literal["image/jpeg"] = DERIVATIVE_CONTENT_TYPE
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    file_size_bytes: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class DerivativeIndexEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_id: str
    level1_product_id: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    """Level 1 checksum the derivatives were made from. The API drops derivatives whose source checksum no longer matches the manifest."""
    source_width: int = Field(ge=1)
    """Level 1 pixel dimensions after EXIF orientation is applied, i.e. as displayed."""
    source_height: int = Field(ge=1)
    thumbnail: Optional[DerivativeFile] = None
    preview: Optional[DerivativeFile] = None


class DerivativesIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2] = INDEX_SCHEMA_VERSION
    root_id: str
    generated_at_utc: datetime
    generator: str
    specs: dict[DerivativeKind, DerivativeSpec]
    derivatives: list[DerivativeIndexEntry] = Field(default_factory=list)


# --- Errors and path safety ------------------------------------------------------


class DerivativeError(Exception):
    """Raised for one observation's failure. The message is safe to print, and never contains a host path."""


class DerivativeConfigError(Exception):
    """Raised for invalid command-line configuration."""


_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
"""Root and observation IDs become path segments, so they must be plain tokens."""


def safe_relative_segments(value: str, *, required_prefix: str) -> list[str]:
    """The same rules apps/api applies to manifest paths. They are duplicated
    rather than shared because the two packages are deployed independently.

    Rejects empty paths, NUL bytes, backslashes (and therefore UNC paths),
    absolute POSIX and drive paths, colons, empty, ``.`` and ``..`` segments,
    segments ending in a dot or space, and paths outside ``required_prefix``."""
    if not value:
        raise DerivativeError("empty Level 1 path")
    if "\x00" in value or "\\" in value or ":" in value:
        raise DerivativeError("Level 1 path contains a forbidden character")
    if value.startswith("/") or _WINDOWS_DRIVE_RE.match(value):
        raise DerivativeError("Level 1 path is absolute")
    segments = value.split("/")
    if any(segment in ("", ".", "..") for segment in segments):
        raise DerivativeError("Level 1 path contains traversal or empty segments")
    if any(segment.endswith((".", " ")) for segment in segments):
        raise DerivativeError("Level 1 path segment ends with a dot or space")
    if not value.startswith(required_prefix):
        raise DerivativeError("Level 1 path is outside the expected level-1/root-<root_id>/ tree")
    return segments


def _resolve_within(root: Path, segments: list[str]) -> Path:
    """Joins ``segments`` under an already-resolved ``root``, follows any links, and requires the result to stay inside ``root``."""
    candidate = root.joinpath(*segments).resolve(strict=False)
    if not candidate.is_relative_to(root):
        raise DerivativeError("path resolves outside its configured root")
    return candidate


def _is_under_production_storage(path: Path) -> bool:
    posix = str(path).replace("\\", "/")
    return posix == PRODUCTION_STORAGE_PREFIX or posix.startswith(PRODUCTION_STORAGE_PREFIX + "/")


def build_derivative_relative_path(kind: DerivativeKind, root_id: str, captured_at_utc: datetime, observation_id: str) -> str:
    base = THUMBNAILS_DIR if kind == "thumbnail" else PREVIEWS_DIR
    return str(
        PurePosixPath(
            base, build_site_directory_id(root_id),
            f"{captured_at_utc:%Y}", f"{captured_at_utc:%m}", f"{captured_at_utc:%d}", f"{observation_id}.jpg",
        )
    )


# --- Image work ---------------------------------------------------------------------


def _import_pillow():
    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
    except ImportError as exc:  # pragma: no cover - exercised only without the extra installed
        raise DerivativeConfigError(
            "Pillow is required for derivative generation. Install the worker's derivatives extra: "
            'pip install -e ".[derivatives]"'
        ) from exc
    return Image, ImageOps, UnidentifiedImageError


def _open_source(path: Path):
    """Decodes a verified Level 1 file into an upright RGB image."""
    Image, ImageOps, UnidentifiedImageError = _import_pillow()
    try:
        with Image.open(path) as opened:
            if opened.format not in SUPPORTED_SOURCE_FORMATS:
                raise DerivativeError(f"unsupported source image format {opened.format!r}")
            if opened.width * opened.height > MAX_SOURCE_PIXELS:
                raise DerivativeError("source image is too large to process")
            opened.load()
            image = ImageOps.exif_transpose(opened)
    except DerivativeError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, SyntaxError) as exc:
        raise DerivativeError(f"source is not a readable image ({type(exc).__name__})") from exc

    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB") if image.mode != "RGB" else image


def render_jpeg(image, spec: DerivativeSpec) -> tuple[bytes, int, int]:
    """Downscales a copy of ``image`` to fit ``spec`` and returns (JPEG bytes, width, height).

    The result is deterministic for the same input and Pillow version.
    """
    Image, _, _ = _import_pillow()
    copy = image.copy()
    copy.thumbnail((spec.max_dimension, spec.max_dimension), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    # No exif/icc_profile/comment arguments are passed, so the output carries no metadata.
    copy.save(buffer, format="JPEG", quality=spec.jpeg_quality, optimize=True, progressive=False)
    return buffer.getvalue(), copy.width, copy.height


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _file_matches(path: Path, expected: DerivativeFile) -> bool:
    try:
        if not path.is_file() or path.stat().st_size != expected.file_size_bytes:
            return False
        return compute_sha256(path).sha256 == expected.sha256
    except OSError:
        return False


# --- Run ----------------------------------------------------------------------------


@dataclass
class RunSummary:
    processed: int = 0
    reused: int = 0
    skipped: int = 0
    failed: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        return 1 if self.failed else 0


def _load_manifest(path: Path) -> Manifest:
    try:
        return Manifest.model_validate_json(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise DerivativeConfigError(f"cannot read manifest: {exc.strerror or exc}") from exc
    except ValidationError as exc:
        raise DerivativeConfigError(f"invalid manifest: {exc}") from exc


def _load_previous_index(path: Path, root_id: str) -> dict[str, DerivativeIndexEntry]:
    """The previous run's entries, used only as reuse hints. Every hint is re-verified against disk before it is trusted."""
    if not path.exists():
        return {}
    try:
        previous = DerivativesIndex.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError):
        return {}  # An unreadable or old-format index just means nothing is reused.
    if previous.root_id != root_id or previous.specs != SPECS:
        return {}
    return {entry.observation_id: entry for entry in previous.derivatives}


def _process_entry(
    entry: ManifestEntry,
    root_id: str,
    input_root: Path,
    output_root: Path,
    previous: Optional[DerivativeIndexEntry],
) -> tuple[DerivativeIndexEntry, bool]:
    """Returns (index entry, reused). Raises DerivativeError on failure."""
    obs = entry.observation
    level1 = entry.level1
    assert level1 is not None and obs.spotted_at_utc is not None

    if not _SAFE_ID_RE.match(obs.observation_id):
        raise DerivativeError("observation_id is not a plain identifier")
    prefix = f"{LEVEL1_DIR}/{build_site_directory_id(root_id)}/"
    source_path = _resolve_within(input_root, safe_relative_segments(level1.local_relative_path, required_prefix=prefix))
    if not source_path.is_file():
        raise DerivativeError("Level 1 source file is missing")
    if source_path.stat().st_size != level1.file_size_bytes:
        raise DerivativeError("Level 1 source size does not match the manifest")
    if compute_sha256(source_path).sha256 != level1.checksum.sha256:
        raise DerivativeError("Level 1 source checksum does not match the manifest")

    targets: dict[DerivativeKind, tuple[str, Path]] = {}
    for kind in ("thumbnail", "preview"):
        relative = build_derivative_relative_path(kind, root_id, obs.spotted_at_utc, obs.observation_id)
        targets[kind] = (relative, _resolve_within(output_root, relative.split("/")))

    # Reuse only when the source checksum, the spec and the on-disk files all still agree with the previous index.
    if (
        previous is not None
        and previous.source_sha256 == level1.checksum.sha256
        and previous.level1_product_id == level1.product_id
        and all(
            (recorded := getattr(previous, kind)) is not None
            and recorded.relative_path == targets[kind][0]
            and _file_matches(targets[kind][1], recorded)
            for kind in targets
        )
    ):
        return previous, True

    image = _open_source(source_path)
    files: dict[str, DerivativeFile] = {}
    for kind, (relative, target) in targets.items():
        data, width, height = render_jpeg(image, SPECS[kind])
        _write_atomic(target, data)
        files[kind] = DerivativeFile(
            relative_path=relative, width=width, height=height,
            file_size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
        )
    return (
        DerivativeIndexEntry(
            observation_id=obs.observation_id,
            level1_product_id=level1.product_id,
            source_sha256=level1.checksum.sha256,
            source_width=image.width,
            source_height=image.height,
            **files,
        ),
        False,
    )


def run(
    *, manifest_path: Path, input_root: Path, output_root: Path, index_output: Path,
    max_images: Optional[int] = None, out=sys.stdout, err=sys.stderr,
) -> RunSummary:
    for name, path in (("--manifest", manifest_path), ("--input-root", input_root),
                       ("--output-root", output_root), ("--index-output", index_output)):
        if _is_under_production_storage(path):
            raise DerivativeConfigError(f"{name} points under {PRODUCTION_STORAGE_PREFIX}; derivatives are generated from local staging only")
    if max_images is not None and max_images < 1:
        raise DerivativeConfigError("--max-images must be a positive integer")
    if not input_root.is_dir():
        raise DerivativeConfigError("--input-root does not exist or is not a directory")
    _import_pillow()

    manifest = _load_manifest(manifest_path)
    root_id = manifest.root_id
    if not _SAFE_ID_RE.match(root_id):
        raise DerivativeConfigError("manifest root_id is not a plain identifier")
    input_root = input_root.resolve(strict=True)
    output_root.mkdir(parents=True, exist_ok=True)
    output_root = output_root.resolve(strict=True)
    previous = _load_previous_index(index_output, root_id)

    summary = RunSummary()
    entries: list[DerivativeIndexEntry] = []
    attempted = 0
    for entry in manifest.entries:
        obs_id = entry.observation.observation_id
        if entry.level1 is None or entry.observation.spotted_at_utc is None:
            summary.skipped += 1
            print(f"[skip] {obs_id}: no Level 1 product or capture time in the manifest", file=out)
            continue
        if max_images is not None and attempted >= max_images:
            break
        attempted += 1
        try:
            index_entry, reused = _process_entry(entry, root_id, input_root, output_root, previous.get(obs_id))
        except DerivativeError as exc:
            summary.failed += 1
            summary.failures.append((obs_id, str(exc)))
            print(f"[error] {obs_id}: {exc}", file=err)
            continue
        entries.append(index_entry)
        if reused:
            summary.reused += 1
            print(f"[reused] {obs_id}", file=out)
        else:
            summary.processed += 1
            print(f"[processed] {obs_id}", file=out)

    index = DerivativesIndex(
        root_id=root_id,
        generated_at_utc=datetime.now(timezone.utc),
        generator=f"coastsnap-import/{__version__}",
        specs=SPECS,
        derivatives=entries,
    )
    _write_atomic(index_output, (index.model_dump_json(indent=2) + "\n").encode("utf-8"))
    print(
        f"Derivatives complete: processed={summary.processed} reused={summary.reused} "
        f"skipped={summary.skipped} failed={summary.failed} index={index_output.name}",
        file=out,
    )
    return summary


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m coastsnap_import.derivatives",
        description="Generate CoastSnap thumbnails and previews from verified Level 1 files. No network access.",
    )
    parser.add_argument("--manifest", required=True, help="Worker manifest JSON (manifests/<root_id>.json).")
    parser.add_argument("--input-root", required=True, help="Staging directory that the manifest's Level 1 paths are relative to.")
    parser.add_argument("--output-root", required=True, help="Directory that derivative paths are written beneath.")
    parser.add_argument("--index-output", required=True, help="Path of the derivatives index JSON to write.")
    parser.add_argument("--max-images", type=int, default=None, help="Process at most this many Level 1 images (for testing).")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    try:
        summary = run(
            manifest_path=Path(args.manifest),
            input_root=Path(args.input_root),
            output_root=Path(args.output_root),
            index_output=Path(args.index_output),
            max_images=args.max_images,
        )
    except DerivativeConfigError as exc:
        print(f"[config error] {exc}", file=sys.stderr)
        return 2
    return summary.exit_code


if __name__ == "__main__":
    sys.exit(main())

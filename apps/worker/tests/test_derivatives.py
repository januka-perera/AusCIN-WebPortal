"""Tests for the separate derivative command (python -m coastsnap_import.derivatives).

Every source image is generated at runtime with Pillow, so no photos are
committed. No test touches the network, Gadi or /g/data.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pytest

PIL = pytest.importorskip("PIL", reason="Pillow is required for derivative tests (worker 'dev'/'derivatives' extra)")
from PIL import Image  # noqa: E402

from coastsnap_import import derivatives  # noqa: E402
from coastsnap_import.derivatives import (  # noqa: E402
    DerivativeConfigError,
    DerivativesIndex,
    main,
    run,
)
from coastsnap_import.models import (  # noqa: E402
    ChecksumInfo,
    Level0Product,
    Level1Product,
    Manifest,
    ManifestEntry,
    ProcessingDetails,
    ProductLevel,
    SourceObservation,
    SourceSite,
    build_level_relative_path,
    build_site_directory_id,
    build_source_record_paths,
)

ROOT_ID = "TEST_ROOT_ID"
T0 = datetime(2026, 9, 2, 1, 0, tzinfo=timezone.utc)


# --- Helpers -------------------------------------------------------------------------


def jpeg_bytes(width: int, height: int, color=(90, 130, 150), exif: Optional[bytes] = None) -> bytes:
    buffer = io.BytesIO()
    image = Image.new("RGB", (width, height), color)
    # A gradient stripe so the image isn't flat, and resampling does real work.
    for x in range(0, width, max(1, width // 16)):
        image.paste((x % 255, 40, 200), (x, 0, min(width, x + 2), height))
    kwargs = {"exif": exif} if exif else {}
    image.save(buffer, format="JPEG", quality=90, **kwargs)
    return buffer.getvalue()


def png_rgba_bytes(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", (width, height), (10, 20, 30, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


class Workspace:
    """A staging directory with Level 1 files and a manifest built with the worker's own models."""

    def __init__(self, tmp_path: Path):
        self.staging = tmp_path / "staging"
        self.staging.mkdir()
        self.output = tmp_path / "derivatives-out"
        self.index = tmp_path / "derivatives-out" / "derivatives-index.json"
        self.manifest_path = self.staging / "manifests" / f"{ROOT_ID}.json"
        self.entries: list[ManifestEntry] = []

    def add(
        self, observation_id: str, data: Optional[bytes], *, day: int = 1, suffix: str = ".jpg",
        write: bool = True, level1: bool = True, level1_path: Optional[str] = None,
    ) -> str:
        captured = datetime(2026, 8, day, 3, 0, tzinfo=timezone.utc)
        relative = level1_path or build_level_relative_path(
            ProductLevel.LEVEL_1, build_site_directory_id(ROOT_ID), captured, f"{observation_id}{suffix}"
        )
        payload = data or b""
        if write and data is not None and level1_path is None:
            target = self.staging.joinpath(*relative.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        checksum = ChecksumInfo(sha256=hashlib.sha256(payload).hexdigest(), computed_at_utc=T0)
        l0_path = relative.replace("level-1/", "level-0/", 1) if relative.startswith("level-1/") else "level-0/x"
        self.entries.append(
            ManifestEntry(
                site=SourceSite(root_id=ROOT_ID),
                observation=SourceObservation(
                    observation_id=observation_id, root_id=ROOT_ID,
                    spotted_at_raw=captured.strftime("%Y-%m-%d %H:%M:%S"), spotted_at_utc=captured,
                ),
                source_record_ref=build_source_record_paths(ROOT_ID, observation_id),
                level0=Level0Product(
                    product_id=f"{observation_id}-L0", parent_observation_id=observation_id,
                    source_url="https://example.invalid/x.jpg", local_relative_path=l0_path,
                    remote_relative_path=l0_path, file_size_bytes=max(1, len(payload)), checksum=checksum,
                    downloaded_at_utc=T0,
                ),
                level1=Level1Product(
                    product_id=f"{observation_id}-L1", parent_product_id=f"{observation_id}-L0",
                    parent_observation_id=observation_id, local_relative_path=relative,
                    remote_relative_path=relative, file_size_bytes=len(payload), checksum=checksum,
                    processing=ProcessingDetails(
                        embedder_backend="exiftool", embedded_metadata_fields=[],
                        processing_software="coastsnap-import", processing_version="0.1.0", processed_at_utc=T0,
                    ),
                ) if level1 else None,
                ingested_at_utc=T0,
            )
        )
        return relative

    def write_manifest(self) -> Path:
        manifest = Manifest(
            run_id="20260902T010000Z", root_id=ROOT_ID, topic_id=37,
            date_from_utc=datetime(2026, 8, 1, tzinfo=timezone.utc), date_to_utc=datetime(2026, 9, 1, tzinfo=timezone.utc),
            generated_at_utc=T0, remote_root="TEST_PUBLICATION_ROOT", entries=self.entries,
        )
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        return self.manifest_path

    def run(self, **kwargs):
        self.write_manifest()
        out, err = io.StringIO(), io.StringIO()
        summary = run(
            manifest_path=self.manifest_path, input_root=self.staging, output_root=self.output,
            index_output=self.index, out=out, err=err, **kwargs,
        )
        return summary, out.getvalue(), err.getvalue()

    def load_index(self) -> DerivativesIndex:
        return DerivativesIndex.model_validate_json(self.index.read_text(encoding="utf-8"))

    def output_file(self, relative: str) -> Path:
        return self.output.joinpath(*relative.split("/"))


@pytest.fixture
def ws(tmp_path: Path) -> Workspace:
    return Workspace(tmp_path)


def entry_for(index: DerivativesIndex, observation_id: str):
    return next(e for e in index.derivatives if e.observation_id == observation_id)


# --- Dimensions, aspect ratio and format -------------------------------------------------


def test_landscape_thumbnail_and_preview_dimensions(ws):
    ws.add("OBS_LANDSCAPE", jpeg_bytes(4000, 3000))
    summary, _, _ = ws.run()
    assert (summary.processed, summary.failed) == (1, 0)
    entry = entry_for(ws.load_index(), "OBS_LANDSCAPE")
    assert (entry.source_width, entry.source_height) == (4000, 3000)
    assert (entry.thumbnail.width, entry.thumbnail.height) == (400, 300)
    assert (entry.preview.width, entry.preview.height) == (1600, 1200)
    with Image.open(ws.output_file(entry.thumbnail.relative_path)) as thumb:
        assert thumb.size == (400, 300)
    with Image.open(ws.output_file(entry.preview.relative_path)) as preview:
        assert preview.size == (1600, 1200)


def test_portrait_aspect_ratio_is_preserved(ws):
    ws.add("OBS_PORTRAIT", jpeg_bytes(1000, 3000))
    ws.run()
    entry = entry_for(ws.load_index(), "OBS_PORTRAIT")
    assert entry.thumbnail.height == 400 and entry.preview.height == 1600
    for rendition in (entry.thumbnail, entry.preview):
        assert rendition.width / rendition.height == pytest.approx(1000 / 3000, abs=0.01)


def test_odd_aspect_ratio_is_preserved(ws):
    ws.add("OBS_PANORAMA", jpeg_bytes(3001, 997))
    ws.run()
    entry = entry_for(ws.load_index(), "OBS_PANORAMA")
    assert max(entry.thumbnail.width, entry.thumbnail.height) == 400
    assert max(entry.preview.width, entry.preview.height) == 1600
    for rendition in (entry.thumbnail, entry.preview):
        assert rendition.width / rendition.height == pytest.approx(3001 / 997, rel=0.01)


def test_small_source_is_never_upscaled(ws):
    ws.add("OBS_SMALL", jpeg_bytes(320, 240))
    ws.run()
    entry = entry_for(ws.load_index(), "OBS_SMALL")
    assert (entry.thumbnail.width, entry.thumbnail.height) == (320, 240)
    assert (entry.preview.width, entry.preview.height) == (320, 240)


def test_outputs_are_metadata_free_rgb_jpegs(ws):
    exif = Image.Exif()
    exif[0x010F] = "SyntheticCameraMaker"  # Make
    ws.add("OBS_EXIF", jpeg_bytes(800, 600, exif=exif.tobytes()))
    ws.run()
    entry = entry_for(ws.load_index(), "OBS_EXIF")
    for rendition in (entry.thumbnail, entry.preview):
        path = ws.output_file(rendition.relative_path)
        assert path.suffix == ".jpg"
        assert path.read_bytes()[:3] == b"\xff\xd8\xff"
        assert rendition.content_type == "image/jpeg"
        with Image.open(path) as image:
            assert image.format == "JPEG"
            assert image.mode == "RGB"
            assert len(image.getexif()) == 0
        assert b"SyntheticCameraMaker" not in path.read_bytes()


def test_exif_orientation_is_applied(ws):
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation: rotate 90 CW when displaying
    ws.add("OBS_ROTATED", jpeg_bytes(800, 600, exif=exif.tobytes()))
    ws.run()
    entry = entry_for(ws.load_index(), "OBS_ROTATED")
    assert (entry.source_width, entry.source_height) == (600, 800)
    assert (entry.thumbnail.width, entry.thumbnail.height) == (300, 400)


def test_png_with_transparency_is_flattened_to_jpeg(ws):
    ws.add("OBS_PNG", png_rgba_bytes(500, 250), suffix=".png")
    summary, _, _ = ws.run()
    assert summary.failed == 0
    entry = entry_for(ws.load_index(), "OBS_PNG")
    assert entry.thumbnail.relative_path.endswith("/OBS_PNG.jpg")
    with Image.open(ws.output_file(entry.thumbnail.relative_path)) as image:
        assert (image.format, image.mode, image.size) == ("JPEG", "RGB", (400, 200))


# --- Source verification failures ----------------------------------------------------------


def test_source_checksum_mismatch_fails_before_decoding(ws, monkeypatch):
    relative = ws.add("OBS_TAMPERED", jpeg_bytes(800, 600))
    path = ws.staging.joinpath(*relative.split("/"))
    data = bytearray(path.read_bytes())
    data[-10] ^= 0xFF  # same size, different bytes
    path.write_bytes(bytes(data))
    decoded = []
    monkeypatch.setattr(derivatives, "_open_source", lambda p: decoded.append(p))

    summary, _, err = ws.run()
    assert (summary.failed, summary.processed) == (1, 0)
    assert summary.exit_code == 1
    assert "checksum does not match" in err
    assert decoded == []
    assert ws.load_index().derivatives == []
    assert not (ws.output / "derivatives").exists()


def test_source_size_mismatch_fails(ws):
    relative = ws.add("OBS_TRUNCATED", jpeg_bytes(800, 600))
    path = ws.staging.joinpath(*relative.split("/"))
    path.write_bytes(path.read_bytes()[:-100])
    summary, _, err = ws.run()
    assert summary.failed == 1
    assert "size does not match" in err


def test_missing_source_file_fails_with_nonzero_exit(ws):
    ws.add("OBS_PRESENT", jpeg_bytes(800, 600), day=1)
    ws.add("OBS_MISSING", jpeg_bytes(800, 600), day=2, write=False)
    summary, _, err = ws.run()
    assert (summary.processed, summary.failed, summary.exit_code) == (1, 1, 1)
    assert "OBS_MISSING: Level 1 source file is missing" in err
    assert [e.observation_id for e in ws.load_index().derivatives] == ["OBS_PRESENT"]


@pytest.mark.parametrize(
    ("observation_id", "data", "suffix", "expected"),
    [
        ("OBS_TEXT", b"this is not an image at all", ".jpg", "not a readable image"),
        ("OBS_GIF", None, ".gif", "unsupported source image format 'GIF'"),
        ("OBS_BMP", None, ".bmp", "unsupported source image format 'BMP'"),
        ("OBS_HEIC", b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic", ".heic", "not a readable image"),
    ],
)
def test_non_image_or_unsupported_format_fails(ws, observation_id, data, suffix, expected):
    if data is None:
        buffer = io.BytesIO()
        Image.new("RGB", (64, 48), (1, 2, 3)).save(buffer, format=suffix.lstrip(".").upper())
        data = buffer.getvalue()
    ws.add(observation_id, data, suffix=suffix)
    summary, _, err = ws.run()
    assert (summary.failed, summary.exit_code) == (1, 1)
    assert expected in err


def test_main_returns_nonzero_when_a_source_fails(ws):
    ws.add("OBS_MISSING", jpeg_bytes(100, 100), write=False)
    ws.write_manifest()
    code = main([
        "--manifest", str(ws.manifest_path), "--input-root", str(ws.staging),
        "--output-root", str(ws.output), "--index-output", str(ws.index),
    ])
    assert code == 1


def test_main_returns_zero_on_success(ws):
    ws.add("OBS_OK", jpeg_bytes(100, 100))
    ws.write_manifest()
    code = main([
        "--manifest", str(ws.manifest_path), "--input-root", str(ws.staging),
        "--output-root", str(ws.output), "--index-output", str(ws.index), "--max-images", "1",
    ])
    assert code == 0


# --- Reuse and determinism -----------------------------------------------------------------


def test_rerun_reuses_valid_derivatives_without_rewriting(ws):
    ws.add("OBS_A", jpeg_bytes(2000, 1500), day=1)
    ws.add("OBS_B", jpeg_bytes(1500, 2000), day=2)
    first, _, _ = ws.run()
    assert (first.processed, first.reused) == (2, 0)
    first_index = ws.load_index()
    paths = [ws.output_file(e.thumbnail.relative_path) for e in first_index.derivatives]
    mtimes = [p.stat().st_mtime_ns for p in paths]

    second, out, _ = ws.run()
    assert (second.processed, second.reused, second.failed) == (0, 2, 0)
    assert "[reused] OBS_A" in out
    assert [p.stat().st_mtime_ns for p in paths] == mtimes
    assert ws.load_index().derivatives == first_index.derivatives


def test_regeneration_is_deterministic(ws):
    ws.add("OBS_A", jpeg_bytes(2000, 1500))
    ws.run()
    before = entry_for(ws.load_index(), "OBS_A")
    ws.index.unlink()  # no reuse hints: force regeneration
    summary, _, _ = ws.run()
    assert summary.processed == 1
    assert entry_for(ws.load_index(), "OBS_A") == before


def test_corrupted_derivative_is_regenerated(ws):
    ws.add("OBS_A", jpeg_bytes(2000, 1500))
    ws.run()
    entry = entry_for(ws.load_index(), "OBS_A")
    ws.output_file(entry.preview.relative_path).write_bytes(b"corrupted")
    summary, _, _ = ws.run()
    assert (summary.processed, summary.reused) == (1, 0)
    assert hashlib.sha256(ws.output_file(entry.preview.relative_path).read_bytes()).hexdigest() == entry.preview.sha256


def test_changed_source_is_not_reused(ws):
    ws.add("OBS_A", jpeg_bytes(2000, 1500))
    ws.run()
    old = entry_for(ws.load_index(), "OBS_A")
    ws.entries.clear()
    ws.add("OBS_A", jpeg_bytes(1200, 1200, color=(200, 10, 10)))  # reprocessed Level 1, new checksum
    summary, _, _ = ws.run()
    assert (summary.processed, summary.reused) == (1, 0)
    new = entry_for(ws.load_index(), "OBS_A")
    assert new.source_sha256 != old.source_sha256
    assert (new.thumbnail.width, new.thumbnail.height) == (400, 400)


def test_changed_spec_is_not_reused(ws, monkeypatch):
    ws.add("OBS_A", jpeg_bytes(2000, 1500))
    ws.run()
    monkeypatch.setitem(derivatives.SPECS, "thumbnail", derivatives.DerivativeSpec(max_dimension=200, jpeg_quality=80))
    summary, _, _ = ws.run()
    assert (summary.processed, summary.reused) == (1, 0)
    assert entry_for(ws.load_index(), "OBS_A").thumbnail.width == 200


# --- Index contents ------------------------------------------------------------------------


def test_index_contents_are_relative_and_catalogue_safe(ws, tmp_path):
    ws.add("OBS_A", jpeg_bytes(2000, 1500), day=1)
    ws.add("OBS_NO_L1", None, day=2, level1=False)
    ws.run()
    raw = json.loads(ws.index.read_text(encoding="utf-8"))

    assert set(raw) == {"schema_version", "root_id", "generated_at_utc", "generator", "specs", "derivatives"}
    assert raw["schema_version"] == 2
    assert raw["root_id"] == ROOT_ID
    assert raw["specs"] == {
        "thumbnail": {"max_dimension": 400, "jpeg_quality": 80},
        "preview": {"max_dimension": 1600, "jpeg_quality": 85},
    }
    (entry,) = raw["derivatives"]
    assert set(entry) == {
        "observation_id", "level1_product_id", "source_sha256", "source_width", "source_height", "thumbnail", "preview",
    }
    assert entry["observation_id"] == "OBS_A"
    assert entry["level1_product_id"] == "OBS_A-L1"
    assert entry["thumbnail"]["relative_path"] == "derivatives/thumbnails/root-TEST_ROOT_ID/2026/08/01/OBS_A.jpg"
    assert entry["preview"]["relative_path"] == "derivatives/previews/root-TEST_ROOT_ID/2026/08/01/OBS_A.jpg"
    for kind in ("thumbnail", "preview"):
        rendition = entry[kind]
        assert set(rendition) == {"relative_path", "content_type", "width", "height", "file_size_bytes", "sha256"}
        data = ws.output_file(rendition["relative_path"]).read_bytes()
        assert rendition["file_size_bytes"] == len(data)
        assert rendition["sha256"] == hashlib.sha256(data).hexdigest()

    text = ws.index.read_text(encoding="utf-8")
    for forbidden in (str(tmp_path), tmp_path.as_posix(), "\\\\", "/g/data", "TEST_PUBLICATION_ROOT",
                      "example.invalid", "source-records", "level-1/", "bearer", "token", "spotted_at"):
        assert forbidden not in text, forbidden
    assert not any(value.startswith("/") for value in _all_strings(raw))


def _all_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _all_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _all_strings(item)


def test_skipped_entries_are_counted(ws):
    ws.add("OBS_A", jpeg_bytes(300, 200), day=1)
    ws.add("OBS_NO_L1", None, day=2, level1=False)
    summary, out, _ = ws.run()
    assert (summary.processed, summary.skipped, summary.failed) == (1, 1, 0)
    assert "processed=1 reused=0 skipped=1 failed=0" in out


# --- Path safety -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_path",
    [
        "level-1/root-TEST_ROOT_ID/../../../outside.jpg",
        "level-1/root-TEST_ROOT_ID/2026/./08/x.jpg",
        "level-1/root-TEST_ROOT_ID//x.jpg",
        "/etc/passwd",
        "C:/Windows/win.ini",
        "c:outside.jpg",
        "level-1\\root-TEST_ROOT_ID\\x.jpg",
        "\\\\server\\share\\x.jpg",
        "level-1/root-OTHER_ROOT/2026/08/01/images/x.jpg",
        "level-0/root-TEST_ROOT_ID/2026/08/01/images/x.jpg",
        "level-1/root-TEST_ROOT_ID/x.jpg:stream",
    ],
)
def test_unsafe_level1_paths_are_rejected(ws, tmp_path, bad_path):
    (tmp_path / "outside.jpg").write_bytes(jpeg_bytes(100, 100))
    ws.add("OBS_EVIL", jpeg_bytes(100, 100), level1_path=bad_path)
    summary, _, err = ws.run()
    assert (summary.failed, summary.processed) == (1, 0)
    assert "OBS_EVIL" in err
    assert str(tmp_path) not in err
    assert not (ws.output / "derivatives").exists()


def test_unsafe_observation_id_is_rejected(ws):
    ws.add("OBS_OK", jpeg_bytes(100, 100))
    ws.entries[0] = ws.entries[0].model_copy(
        update={"observation": ws.entries[0].observation.model_copy(update={"observation_id": "..\\..\\evil"})}
    )
    summary, _, err = ws.run()
    assert summary.failed == 1
    assert "not a plain identifier" in err


def test_level1_symlink_escaping_input_root_is_rejected(ws, tmp_path):
    outside = tmp_path / "outside.jpg"
    data = jpeg_bytes(100, 100)
    outside.write_bytes(data)
    relative = ws.add("OBS_LINK", data, write=False)
    link = ws.staging.joinpath(*relative.split("/"))
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlinks cannot be created on this platform/account: {exc}")
    summary, _, err = ws.run()
    assert summary.failed == 1
    assert "outside its configured root" in err


@pytest.mark.skipif(sys.platform != "win32", reason="NTFS directory junctions are Windows-only")
def test_level1_directory_junction_escaping_input_root_is_rejected(ws, tmp_path):
    # Junctions need no special privilege on Windows, so this escape case always runs there.
    import _winapi

    data = jpeg_bytes(100, 100)
    outside_dir = tmp_path / "outside-dir"
    outside_dir.mkdir()
    (outside_dir / "OBS_JUNCTION.jpg").write_bytes(data)
    relative = ws.add("OBS_JUNCTION", data, write=False)
    images_dir = ws.staging.joinpath(*relative.split("/")).parent
    images_dir.parent.mkdir(parents=True, exist_ok=True)
    _winapi.CreateJunction(str(outside_dir), str(images_dir))
    try:
        assert (images_dir / "OBS_JUNCTION.jpg").read_bytes() == data  # the escape route really exists
        summary, _, err = ws.run()
        assert (summary.failed, summary.processed) == (1, 0)
        assert "outside its configured root" in err
    finally:
        os.rmdir(images_dir)  # removes the junction only


def test_output_paths_stay_beneath_derivatives_root(ws):
    for n, day in enumerate((1, 15, 28)):
        ws.add(f"OBS_{n}", jpeg_bytes(900, 600), day=day)
    ws.run()
    root = ws.output.resolve()
    written = [p for p in root.rglob("*") if p.is_file()]
    assert written, "expected derivatives to be written"
    for path in written:
        assert path.resolve().is_relative_to(root)
    for entry in ws.load_index().derivatives:
        for rendition in (entry.thumbnail, entry.preview):
            assert ws.output_file(rendition.relative_path).resolve().is_relative_to(root)
    # Nothing was written into the staging area, and the Level 1 inputs are untouched.
    assert not (ws.staging / "derivatives").exists()


def test_level1_sources_are_never_modified(ws):
    relative = ws.add("OBS_A", jpeg_bytes(900, 600))
    source = ws.staging.joinpath(*relative.split("/"))
    before = (source.read_bytes(), source.stat().st_mtime_ns)
    ws.run()
    assert (source.read_bytes(), source.stat().st_mtime_ns) == before


# --- Limits and configuration ----------------------------------------------------------------


def test_max_images_limits_processing(ws):
    for n in range(5):
        ws.add(f"OBS_{n}", jpeg_bytes(300, 200), day=n + 1)
    summary, _, _ = ws.run(max_images=2)
    assert (summary.processed, summary.failed) == (2, 0)
    assert [e.observation_id for e in ws.load_index().derivatives] == ["OBS_0", "OBS_1"]
    assert len(list((ws.output / "derivatives" / "thumbnails").rglob("*.jpg"))) == 2


def test_max_images_counts_failures_as_attempts(ws):
    ws.add("OBS_MISSING", jpeg_bytes(300, 200), day=1, write=False)
    ws.add("OBS_OK", jpeg_bytes(300, 200), day=2)
    summary, _, _ = ws.run(max_images=1)
    assert (summary.processed, summary.failed) == (0, 1)


@pytest.mark.parametrize("value", [0, -1])
def test_max_images_must_be_positive(ws, value):
    ws.add("OBS_A", jpeg_bytes(100, 100))
    with pytest.raises(DerivativeConfigError):
        ws.run(max_images=value)


@pytest.mark.parametrize("argument", ["--input-root", "--output-root", "--index-output", "--manifest"])
def test_production_storage_paths_are_refused(ws, argument):
    ws.add("OBS_A", jpeg_bytes(100, 100))
    ws.write_manifest()
    args = {
        "--manifest": str(ws.manifest_path), "--input-root": str(ws.staging),
        "--output-root": str(ws.output), "--index-output": str(ws.index),
    }
    args[argument] = "/g/data/qu34/AusCIN/anything"
    assert main([item for pair in args.items() for item in pair]) == 2


def test_invalid_manifest_is_a_config_error(ws, tmp_path):
    bad = tmp_path / "bad-manifest.json"
    bad.write_text('{"entries": []}', encoding="utf-8")
    assert main([
        "--manifest", str(bad), "--input-root", str(ws.staging),
        "--output-root", str(ws.output), "--index-output", str(ws.index),
    ]) == 2


def test_missing_input_root_is_a_config_error(ws, tmp_path):
    ws.add("OBS_A", jpeg_bytes(100, 100))
    ws.write_manifest()
    assert main([
        "--manifest", str(ws.manifest_path), "--input-root", str(tmp_path / "nope"),
        "--output-root", str(ws.output), "--index-output", str(ws.index),
    ]) == 2

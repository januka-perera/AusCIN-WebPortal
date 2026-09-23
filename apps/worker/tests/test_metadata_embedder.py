from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from coastsnap_import.metadata_embedder import (
    ArgusXmpEmbedder,
    ExifToolXmpEmbedder,
    MetadataEmbeddingError,
    MetadataFields,
    build_embedder,
)

FORBIDDEN_FIELD_NAMES = {
    "password",
    "bearer_token",
    "token",
    "private_key",
    "ssh_key",
    "file_path",
    "local_path",
    "contributor_email",
    "contributor_contact",
}


def _sample_fields(**overrides) -> MetadataFields:
    base = dict(
        root_id="37",
        observation_id="1001",
        media_reference="img-123",
        captured_at_utc=datetime(2026, 8, 1, 2, 15, tzinfo=timezone.utc),
        latitude=-33.45,
        longitude=151.4,
        contributor_attribution=None,
        processing_software="coastsnap-import",
        processing_version="0.1.0",
    )
    base.update(overrides)
    return MetadataFields(**base)


def test_metadata_fields_model_has_no_forbidden_field_names():
    """Structural safety net for the 'never embed' list: these field
    names must never exist on the model at all, so an embedder cannot
    accidentally read/write one."""
    assert set(MetadataFields.model_fields).isdisjoint(FORBIDDEN_FIELD_NAMES)


def test_argus_embedder_raises_not_implemented(tmp_path: Path):
    embedder = ArgusXmpEmbedder()
    with pytest.raises(NotImplementedError, match="Argus"):
        embedder.embed(tmp_path / "image.jpg", _sample_fields())


def test_build_embedder_selects_backend(tmp_path: Path):
    assert isinstance(build_embedder("exiftool"), ExifToolXmpEmbedder)
    assert isinstance(build_embedder("argus"), ArgusXmpEmbedder)
    with pytest.raises(MetadataEmbeddingError):
        build_embedder("piexif")  # explicitly not a supported backend — see module docstring


def test_exiftool_embedder_builds_expected_args(tmp_path: Path):
    image_path = tmp_path / "1001.jpg"
    image_path.write_bytes(b"fake")
    embedder = ExifToolXmpEmbedder(exiftool_path="exiftool")

    fields = _sample_fields(contributor_attribution="Test Contributor A")
    args, written = embedder._build_args(image_path, fields)

    joined = " ".join(args)
    assert "-config" in args
    assert "-overwrite_original" in args
    assert "-XMP-auscin:SpotteronRootId=37" in args
    assert "-XMP-auscin:SpotteronObservationId=1001" in args
    assert "-XMP-auscin:SpotteronMediaReference=img-123" in args
    assert "-EXIF:GPSLatitudeRef=S" in args
    assert "-EXIF:GPSLongitudeRef=E" in args
    assert "-XMP-dc:Creator=Test Contributor A" in args
    assert any(a.startswith("-XMP-xmp:CreatorTool=coastsnap-import/") for a in args)
    assert str(image_path) in args
    assert "XMP-auscin:SpotteronRootId" in written
    # Never embed anything from a forbidden category:
    assert not any("password" in a.lower() or "token" in a.lower() or "private_key" in a.lower() for a in args)


def test_exiftool_embedder_omits_unset_optional_fields(tmp_path: Path):
    embedder = ExifToolXmpEmbedder()
    fields = _sample_fields(media_reference=None, contributor_attribution=None, latitude=None, longitude=None)
    args, _written = embedder._build_args(tmp_path / "x.jpg", fields)
    joined = " ".join(args)
    assert "SpotteronMediaReference" not in joined
    assert "XMP-dc:Creator" not in joined
    assert "GPSLatitude" not in joined


@patch("coastsnap_import.metadata_embedder.subprocess.run")
def test_exiftool_embed_success(mock_run: MagicMock, tmp_path: Path):
    image_path = tmp_path / "1001.jpg"
    image_path.write_bytes(b"fake")
    mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="1 image files updated", stderr="")

    embedder = ExifToolXmpEmbedder()
    written = embedder.embed(image_path, _sample_fields())

    assert "XMP-auscin:SpotteronObservationId" in written
    mock_run.assert_called_once()


@patch("coastsnap_import.metadata_embedder.subprocess.run")
def test_exiftool_embed_raises_on_nonzero_exit(mock_run: MagicMock, tmp_path: Path):
    image_path = tmp_path / "1001.jpg"
    image_path.write_bytes(b"fake")
    mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="Error: bad file")

    embedder = ExifToolXmpEmbedder()
    with pytest.raises(MetadataEmbeddingError, match="bad file"):
        embedder.embed(image_path, _sample_fields())


@patch("coastsnap_import.metadata_embedder.subprocess.run", side_effect=FileNotFoundError("no such file"))
def test_exiftool_embed_raises_when_binary_missing(_mock_run: MagicMock, tmp_path: Path):
    image_path = tmp_path / "1001.jpg"
    image_path.write_bytes(b"fake")
    embedder = ExifToolXmpEmbedder(exiftool_path="exiftool-does-not-exist")
    with pytest.raises(MetadataEmbeddingError, match="exiftool"):
        embedder.embed(image_path, _sample_fields())


def test_exiftool_embed_raises_when_config_missing(tmp_path: Path):
    image_path = tmp_path / "1001.jpg"
    image_path.write_bytes(b"fake")
    embedder = ExifToolXmpEmbedder(config_path=tmp_path / "does-not-exist.config")
    with pytest.raises(MetadataEmbeddingError, match="config"):
        embedder.embed(image_path, _sample_fields())

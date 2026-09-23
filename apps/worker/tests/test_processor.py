from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import responses

from coastsnap_import.processor import (
    Level0Level1Processor,
    ProcessingError,
    compute_sha256,
    infer_extension,
)

IMAGE_URL = "https://cdn.example-spotteron.test/images/1001.jpg"
SAMPLE_BYTES = b"\xff\xd8\xff\xe0synthetic-not-a-real-jpeg-just-test-bytes" * 10


@responses.activate
def test_download_level0_preserves_bytes_exactly(staging_dir: Path):
    responses.add(responses.GET, IMAGE_URL, body=SAMPLE_BYTES, status=200, content_type="image/jpeg")
    processor = Level0Level1Processor(staging_dir=staging_dir)

    level0 = processor.download_level0(
        product_id="1001-L0",
        observation_id="1001",
        image_url=IMAGE_URL,
        remote_relative_path="level-0/SITE/2026/08/01/images/1001.jpg",
    )

    written_bytes = (staging_dir / level0.local_relative_path).read_bytes()
    assert written_bytes == SAMPLE_BYTES  # byte-for-byte, per requirement 1
    assert level0.file_size_bytes == len(SAMPLE_BYTES)
    assert level0.checksum.sha256 == hashlib.sha256(SAMPLE_BYTES).hexdigest()
    assert level0.content_type == "image/jpeg"


@responses.activate
def test_download_level0_raises_on_empty_body(staging_dir: Path):
    responses.add(responses.GET, IMAGE_URL, body=b"", status=200)
    processor = Level0Level1Processor(staging_dir=staging_dir)
    with pytest.raises(ProcessingError, match="empty"):
        processor.download_level0(
            product_id="1001-L0",
            observation_id="1001",
            image_url=IMAGE_URL,
            remote_relative_path="level-0/SITE/2026/08/01/images/1001.jpg",
        )


@responses.activate
def test_download_level0_raises_on_http_error(staging_dir: Path):
    responses.add(responses.GET, IMAGE_URL, status=404)
    processor = Level0Level1Processor(staging_dir=staging_dir)
    with pytest.raises(ProcessingError):
        processor.download_level0(
            product_id="1001-L0",
            observation_id="1001",
            image_url=IMAGE_URL,
            remote_relative_path="level-0/SITE/2026/08/01/images/1001.jpg",
        )


@responses.activate
def test_copy_level0_to_level1_is_byte_identical_before_embedding(staging_dir: Path):
    responses.add(responses.GET, IMAGE_URL, body=SAMPLE_BYTES, status=200)
    processor = Level0Level1Processor(staging_dir=staging_dir)
    level0 = processor.download_level0(
        product_id="1001-L0",
        observation_id="1001",
        image_url=IMAGE_URL,
        remote_relative_path="level-0/SITE/2026/08/01/images/1001.jpg",
    )

    level1_path = processor.copy_level0_to_level1_path(level0, "level-1/SITE/2026/08/01/images/1001.jpg")

    assert level1_path.read_bytes() == SAMPLE_BYTES
    # Level 0 itself must remain untouched by the copy.
    assert (staging_dir / level0.local_relative_path).read_bytes() == SAMPLE_BYTES


@responses.activate
def test_finalize_level1_checksum_reflects_post_embedding_bytes(staging_dir: Path):
    responses.add(responses.GET, IMAGE_URL, body=SAMPLE_BYTES, status=200)
    processor = Level0Level1Processor(staging_dir=staging_dir)
    level0 = processor.download_level0(
        product_id="1001-L0",
        observation_id="1001",
        image_url=IMAGE_URL,
        remote_relative_path="level-0/SITE/2026/08/01/images/1001.jpg",
    )
    level1_path = processor.copy_level0_to_level1_path(level0, "level-1/SITE/2026/08/01/images/1001.jpg")

    # Simulate metadata embedding modifying the file in place.
    level1_path.write_bytes(SAMPLE_BYTES + b"-with-embedded-metadata")

    level1 = processor.finalize_level1(
        level0=level0,
        level1_local_path=level1_path,
        level1_remote_relative_path="level-1/SITE/2026/08/01/images/1001.jpg",
        embedded_metadata_fields=["XMP-dc:Source"],
        embedder_backend="exiftool",
        processing_software="coastsnap-import",
        processing_version="0.1.0",
    )

    assert level1.checksum.sha256 != level0.checksum.sha256  # post-embedding bytes differ from Level 0
    assert level1.checksum.sha256 == hashlib.sha256(SAMPLE_BYTES + b"-with-embedded-metadata").hexdigest()
    assert level1.parent_product_id == level0.product_id


def test_compute_sha256_matches_hashlib(tmp_path: Path):
    path = tmp_path / "data.bin"
    path.write_bytes(SAMPLE_BYTES)
    assert compute_sha256(path).sha256 == hashlib.sha256(SAMPLE_BYTES).hexdigest()


@pytest.mark.parametrize(
    "url,content_type,expected",
    [
        ("https://cdn.test/images/1001.jpg", None, ".jpg"),
        ("https://cdn.test/images/1001.PNG", None, ".png"),
        ("https://cdn.test/images/1001", "image/jpeg", ".jpg"),
        ("https://cdn.test/images/1001", "image/png", ".png"),
        ("https://cdn.test/images/1001", None, ".bin"),
    ],
)
def test_infer_extension(url, content_type, expected):
    assert infer_extension(url, content_type) == expected

from __future__ import annotations

import copy

import pytest

from auscin_api.catalogue import CatalogueError, build_media_id, load_catalogue, validate_relative_path
from conftest import MANIFEST_PATH, PUBLIC_SITE_ID, REGISTRY_PATH

PREFIX = "level-1/root-TEST_ROOT_ID/"


# --- Relative path validation ------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "/etc/passwd",
        "/level-1/root-TEST_ROOT_ID/2026/08/01/images/x.jpg",
        "C:/data/x.jpg",
        "c:x.jpg",
        "\\\\server\\share\\x.jpg",
        "TEST_PUBLICATION_ROOT/level-1/x.jpg",
    ],
)
def test_absolute_or_foreign_paths_are_rejected(value):
    with pytest.raises(CatalogueError):
        validate_relative_path(value, field="f", required_prefix=PREFIX)


@pytest.mark.parametrize(
    "value",
    [
        "level-1/root-TEST_ROOT_ID/../../../etc/passwd",
        "level-1/root-TEST_ROOT_ID/2026/./x.jpg",
        "level-1/root-TEST_ROOT_ID//x.jpg",
        "level-1/root-TEST_ROOT_ID/2026\\..\\x.jpg",
        "level-1/root-TEST_ROOT_ID/x.jpg\x00.txt",
        "",
    ],
)
def test_traversal_and_malformed_paths_are_rejected(value):
    with pytest.raises(CatalogueError):
        validate_relative_path(value, field="f", required_prefix=PREFIX)


def test_valid_relative_path_is_accepted():
    validate_relative_path(f"{PREFIX}2026/08/01/images/TEST_OBS_0001.jpg", field="f", required_prefix=PREFIX)


# --- Whole-manifest rejection ---------------------------------------------------------


@pytest.mark.parametrize(
    ("product", "field", "bad_value"),
    [
        ("level1", "local_relative_path", "/srv/staging/level-1/root-TEST_ROOT_ID/x.jpg"),
        ("level1", "remote_relative_path", "C:/Users/someone/level-1/x.jpg"),
        ("level0", "local_relative_path", "level-0/root-TEST_ROOT_ID/../../../../etc/passwd"),
        ("level0", "remote_relative_path", "level-0/root-OTHER_ROOT/2026/08/01/images/x.jpg"),
    ],
)
def test_manifest_with_unsafe_product_path_is_rejected(manifest_data, write_json, product, field, bad_value):
    data = copy.deepcopy(manifest_data)
    data["entries"][0][product][field] = bad_value
    with pytest.raises(CatalogueError):
        load_catalogue(REGISTRY_PATH, write_json("manifest.json", data))


def test_manifest_with_unsafe_source_record_path_is_rejected(manifest_data, write_json):
    data = copy.deepcopy(manifest_data)
    data["entries"][1]["source_record_ref"]["observation_record_relative_path"] = "../outside.json"
    with pytest.raises(CatalogueError):
        load_catalogue(REGISTRY_PATH, write_json("manifest.json", data))


def test_manifest_with_unsafe_transfer_path_is_rejected(manifest_data, write_json):
    data = copy.deepcopy(manifest_data)
    entry = next(e for e in data["entries"] if e["level1_transfer"] is not None)
    entry["level1_transfer"]["remote_part_relative_path"] = "/g/data/qu34/x.jpg.part"
    with pytest.raises(CatalogueError):
        load_catalogue(REGISTRY_PATH, write_json("manifest.json", data))


def test_manifest_entry_from_another_root_is_rejected(manifest_data, write_json):
    data = copy.deepcopy(manifest_data)
    data["entries"][0]["observation"]["root_id"] = "OTHER_ROOT"
    with pytest.raises(CatalogueError):
        load_catalogue(REGISTRY_PATH, write_json("manifest.json", data))


def test_duplicate_observation_is_rejected(manifest_data, write_json):
    data = copy.deepcopy(manifest_data)
    data["entries"].append(copy.deepcopy(data["entries"][0]))
    with pytest.raises(CatalogueError):
        load_catalogue(REGISTRY_PATH, write_json("manifest.json", data))


def test_manifest_not_matching_worker_schema_is_rejected(write_json):
    with pytest.raises(CatalogueError, match="Invalid manifest"):
        load_catalogue(REGISTRY_PATH, write_json("manifest.json", {"entries": []}))


def test_missing_manifest_file_is_reported(tmp_path):
    with pytest.raises(CatalogueError, match="Cannot read manifest"):
        load_catalogue(REGISTRY_PATH, tmp_path / "missing.json")


# --- Registry validation --------------------------------------------------------------


def test_registry_with_duplicate_root_id_is_rejected(registry_data, write_json):
    data = copy.deepcopy(registry_data)
    data["sites"][1]["spotteron_root_id"] = data["sites"][0]["spotteron_root_id"]
    with pytest.raises(CatalogueError, match="Invalid site registry"):
        load_catalogue(write_json("registry.json", data), MANIFEST_PATH)


def test_registry_with_unknown_publication_status_is_rejected(registry_data, write_json):
    data = copy.deepcopy(registry_data)
    data["sites"][0]["publication_status"] = "published"
    with pytest.raises(CatalogueError):
        load_catalogue(write_json("registry.json", data), MANIFEST_PATH)


def test_registry_with_unexpected_field_is_rejected(registry_data, write_json):
    data = copy.deepcopy(registry_data)
    data["sites"][0]["media_root"] = "/srv/media"
    with pytest.raises(CatalogueError):
        load_catalogue(write_json("registry.json", data), MANIFEST_PATH)


# --- Catalogue contents ---------------------------------------------------------------


def test_incomplete_entries_are_not_presented():
    catalogue = load_catalogue(REGISTRY_PATH, MANIFEST_PATH)
    # 6 manifest entries; TEST_OBS_0006 has no Level 1 product.
    assert catalogue.public_observation_count == 5
    assert catalogue.get_observation(PUBLIC_SITE_ID, build_media_id(PUBLIC_SITE_ID, "TEST_OBS_0006")) is None


def test_media_ids_are_opaque_and_stable():
    first = build_media_id(PUBLIC_SITE_ID, "TEST_OBS_0001")
    assert first == build_media_id(PUBLIC_SITE_ID, "TEST_OBS_0001")
    assert first != build_media_id("CS-OTHER", "TEST_OBS_0001")
    assert "TEST_OBS" not in first
    assert first.startswith("csm_")


# --- Derivatives index and media metadata ---------------------------------------------

from conftest import DERIVATIVES_INDEX_PATH  # noqa: E402


@pytest.mark.parametrize(
    "bad_value",
    [
        "/srv/derivatives/thumbnails/root-TEST_ROOT_ID/x.jpg",
        "C:/derivatives/thumbnails/root-TEST_ROOT_ID/x.jpg",
        r"\\server\share\x.jpg",
        "derivatives/thumbnails/root-TEST_ROOT_ID/../../../level-1/root-TEST_ROOT_ID/x.jpg",
        "derivatives/previews/root-TEST_ROOT_ID/2026/08/01/TEST_OBS_0001.jpg",  # preview tree used for a thumbnail
        "level-1/root-TEST_ROOT_ID/2026/08/01/images/TEST_OBS_0001.jpg",  # original used as a "thumbnail"
        "derivatives/thumbnails/root-TEST_ROOT_ID/2026/08/01/TEST_OBS_0001.png",
    ],
)
def test_derivatives_index_with_unsafe_or_misplaced_path_is_rejected(derivatives_data, write_json, bad_value):
    data = copy.deepcopy(derivatives_data)
    data["derivatives"][0]["thumbnail_relative_path"] = bad_value
    with pytest.raises(CatalogueError):
        load_catalogue(REGISTRY_PATH, MANIFEST_PATH, write_json("derivatives.json", data))


def test_derivatives_index_for_another_root_is_rejected(derivatives_data, write_json):
    data = copy.deepcopy(derivatives_data)
    data["root_id"] = "OTHER_ROOT"
    with pytest.raises(CatalogueError, match="root_id"):
        load_catalogue(REGISTRY_PATH, MANIFEST_PATH, write_json("derivatives.json", data))


def test_derivatives_index_for_unknown_observation_is_rejected(derivatives_data, write_json):
    data = copy.deepcopy(derivatives_data)
    data["derivatives"][0]["observation_id"] = "TEST_OBS_9999"
    with pytest.raises(CatalogueError, match="unknown observation"):
        load_catalogue(REGISTRY_PATH, MANIFEST_PATH, write_json("derivatives.json", data))


def test_derivatives_index_with_unexpected_field_is_rejected(derivatives_data, write_json):
    data = copy.deepcopy(derivatives_data)
    data["derivatives"][0]["absolute_path"] = "/srv/x.jpg"
    with pytest.raises(CatalogueError, match="Invalid derivatives index"):
        load_catalogue(REGISTRY_PATH, MANIFEST_PATH, write_json("derivatives.json", data))


def test_level1_checksum_must_be_sha256(manifest_data, write_json):
    data = copy.deepcopy(manifest_data)
    data["entries"][0]["level1"]["checksum"]["sha256"] = "not-a-checksum"
    with pytest.raises(CatalogueError, match="SHA-256"):
        load_catalogue(REGISTRY_PATH, write_json("manifest.json", data))


def test_catalogue_retains_trusted_internal_media_metadata():
    catalogue = load_catalogue(REGISTRY_PATH, MANIFEST_PATH, DERIVATIVES_INDEX_PATH, media_enabled=True)
    first = catalogue.get_media(build_media_id(PUBLIC_SITE_ID, "TEST_OBS_0001"))
    assert first is not None
    media = first.media
    assert media.level1_relative_path == "level-1/root-TEST_ROOT_ID/2026/08/01/images/TEST_OBS_0001.jpg"
    assert media.level1_content_type == "image/jpeg"
    assert media.level1_file_size > 0
    assert len(media.level1_sha256) == 64
    assert (media.width, media.height) == (4032, 3024)
    assert media.thumbnail_relative_path == "derivatives/thumbnails/root-TEST_ROOT_ID/2026/08/01/TEST_OBS_0001.jpg"
    assert media.preview_relative_path == "derivatives/previews/root-TEST_ROOT_ID/2026/08/01/TEST_OBS_0001.jpg"
    assert media.original_download_permitted is True

    fifth = catalogue.get_media(build_media_id(PUBLIC_SITE_ID, "TEST_OBS_0005"))
    assert fifth.media.thumbnail_relative_path is None and fifth.media.width is None

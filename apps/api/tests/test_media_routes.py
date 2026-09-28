from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from auscin_api.catalogue import build_media_id
from auscin_api.main import create_app
from conftest import (
    DERIVATIVES_INDEX_PATH,
    FIXTURES,
    HIDDEN_SITE_ID,
    MANIFEST_PATH,
    PUBLIC_SITE_ID,
    fixture_settings,
)
from synthetic_media import build_media_root, derivative_bytes, level_bytes

MEDIA = "/media/coastsnap"
LEVELS = ["level0", "level1"]
LEVEL_NUMBER = {"level0": 0, "level1": 1}


def media_id(observation_id: str, site_id: str = PUBLIC_SITE_ID) -> str:
    return build_media_id(site_id, observation_id)


def manifest_entry(observation_id: str) -> dict:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return next(e for e in manifest["entries"] if e["observation"]["observation_id"] == observation_id)


def media_file(media_root: Path, relative_path: str) -> Path:
    return media_root.joinpath(*relative_path.split("/"))


def client_with_policy(registry_data, write_json, media_root, *, level0: bool, level1: bool) -> TestClient:
    data = copy.deepcopy(registry_data)
    data["sites"][0]["level0_download_permitted"] = level0
    data["sites"][0]["level1_download_permitted"] = level1
    return TestClient(create_app(fixture_settings(registry=write_json("registry.json", data), media_root=media_root)))


def observation_json(client: TestClient, observation_id: str) -> dict:
    return client.get(f"/api/v1/coastsnap/sites/{PUBLIC_SITE_ID}/observations/{media_id(observation_id)}").json()


# --- Level 0 and Level 1 downloads ------------------------------------------------------------


@pytest.mark.parametrize("level", LEVELS)
def test_level_download_bytes_match_that_levels_manifest_checksum(client, level):
    response = client.get(f"{MEDIA}/{media_id('TEST_OBS_0001')}/{level}")
    assert response.status_code == 200
    assert response.content == level_bytes("TEST_OBS_0001", LEVEL_NUMBER[level])
    assert hashlib.sha256(response.content).hexdigest() == manifest_entry("TEST_OBS_0001")[level]["checksum"]["sha256"]


def test_level0_and_level1_downloads_differ(client):
    level0 = client.get(f"{MEDIA}/{media_id('TEST_OBS_0001')}/level0")
    level1 = client.get(f"{MEDIA}/{media_id('TEST_OBS_0001')}/level1")
    assert level0.content != level1.content
    assert level0.headers["etag"] != level1.headers["etag"]


@pytest.mark.parametrize("level", LEVELS)
def test_level_etag_is_that_levels_catalogue_checksum(client, level):
    response = client.get(f"{MEDIA}/{media_id('TEST_OBS_0003')}/{level}")
    entry = manifest_entry("TEST_OBS_0003")[level]
    assert response.headers["etag"] == f'"{entry["checksum"]["sha256"]}"'
    assert int(response.headers["content-length"]) == entry["file_size_bytes"]


@pytest.mark.parametrize("level", LEVELS)
def test_level_filename_and_content_type(client, level):
    mid = media_id("TEST_OBS_0002")
    response = client.get(f"{MEDIA}/{mid}/{level}")
    assert response.headers["content-disposition"] == f'attachment; filename="{mid}_{level}.jpg"'
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize("level", LEVELS)
def test_level_supports_range_requests(client, level):
    full = level_bytes("TEST_OBS_0001", LEVEL_NUMBER[level])
    url = f"{MEDIA}/{media_id('TEST_OBS_0001')}/{level}"
    response = client.get(url, headers={"Range": "bytes=0-9"})
    assert response.status_code == 206
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-range"] == f"bytes 0-9/{len(full)}"
    assert response.content == full[:10]
    etag = client.get(url).headers["etag"]
    assert client.get(url, headers={"Range": "bytes=10-19", "If-Range": etag}).content == full[10:20]
    assert client.get(url, headers={"Range": "bytes=10-19", "If-Range": '"stale"'}).status_code == 200
    assert client.get(url, headers={"Range": "bytes=999999-"}).status_code == 416


@pytest.mark.parametrize("level", LEVELS)
def test_head_returns_headers_only(client, level):
    response = client.head(f"{MEDIA}/{media_id('TEST_OBS_0001')}/{level}")
    assert response.status_code == 200
    assert response.content == b""
    assert response.headers["content-disposition"].startswith("attachment;")


@pytest.mark.parametrize("level", LEVELS)
def test_missing_level_file_is_503(client, media_root, level):
    media_file(media_root, manifest_entry("TEST_OBS_0002")[level]["local_relative_path"]).unlink()
    response = client.get(f"{MEDIA}/{media_id('TEST_OBS_0002')}/{level}")
    assert response.status_code == 503
    assert response.json() == {
        "error": {"code": "media_unavailable", "message": "This media file is temporarily unavailable."}
    }
    other = "level1" if level == "level0" else "level0"
    assert client.get(f"{MEDIA}/{media_id('TEST_OBS_0002')}/{other}").status_code == 200  # the other level is unaffected


@pytest.mark.parametrize("level", LEVELS)
def test_level_size_mismatch_is_not_served_under_catalogue_etag(client, media_root, level):
    media_file(media_root, manifest_entry("TEST_OBS_0002")[level]["local_relative_path"]).write_bytes(b"tampered")
    response = client.get(f"{MEDIA}/{media_id('TEST_OBS_0002')}/{level}")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "media_unavailable"


# --- Independent per-level permissions -----------------------------------------------------------


@pytest.mark.parametrize(("level0", "level1"), [(True, True), (True, False), (False, True), (False, False)])
def test_each_level_permission_is_independent(registry_data, write_json, media_root, level0, level1):
    app_client = client_with_policy(registry_data, write_json, media_root, level0=level0, level1=level1)
    mid = media_id("TEST_OBS_0001")
    item = observation_json(app_client, "TEST_OBS_0001")
    entry = manifest_entry("TEST_OBS_0001")
    for level, permitted in (("level0", level0), ("level1", level1)):
        response = app_client.get(f"{MEDIA}/{mid}/{level}")
        if permitted:
            assert response.status_code == 200
            assert item[f"{level}DownloadAvailable"] is True
            assert item[f"{level}DownloadUrl"] == f"{MEDIA}/{mid}/{level}"
            assert item[f"{level}ChecksumSha256"] == entry[level]["checksum"]["sha256"]
        else:
            assert response.status_code == 403
            assert response.json()["error"]["code"] == "download_not_permitted"
            assert item[f"{level}DownloadAvailable"] is False
            assert item[f"{level}DownloadUrl"] is None
            # A checksum is only published alongside a downloadable file.
            assert item[f"{level}ChecksumSha256"] is None
    # Previews stay available whatever the download policy is.
    assert item["previewUrl"] == f"{MEDIA}/{mid}/preview"
    assert app_client.get(f"{MEDIA}/{mid}/preview").status_code == 200


@pytest.mark.parametrize("level", LEVELS)
def test_not_permitted_message_names_the_level(registry_data, write_json, media_root, level):
    app_client = client_with_policy(registry_data, write_json, media_root, level0=False, level1=False)
    message = app_client.get(f"{MEDIA}/{media_id('TEST_OBS_0001')}/{level}").json()["error"]["message"]
    assert ("Level 0" in message) == (level == "level0")
    assert ("Level 1" in message) == (level == "level1")


def test_download_permissions_default_to_false(registry_data, write_json, media_root):
    data = copy.deepcopy(registry_data)
    del data["sites"][0]["level0_download_permitted"]
    del data["sites"][0]["level1_download_permitted"]
    default = TestClient(create_app(fixture_settings(registry=write_json("registry.json", data), media_root=media_root)))
    for level in LEVELS:
        assert default.get(f"{MEDIA}/{media_id('TEST_OBS_0001')}/{level}").status_code == 403
    item = observation_json(default, "TEST_OBS_0001")
    assert item["level0DownloadAvailable"] is False and item["level1DownloadAvailable"] is False


def test_unsupported_level_type_is_not_offered(manifest_data, write_json, tmp_path):
    data = copy.deepcopy(manifest_data)
    entry = next(e for e in data["entries"] if e["observation"]["observation_id"] == "TEST_OBS_0001")
    for key in ("local_relative_path", "remote_relative_path"):
        entry["level0"][key] = entry["level0"][key].replace(".jpg", ".heic")
    root = tmp_path / "media-heic"
    root.mkdir()
    app_client = TestClient(create_app(fixture_settings(manifest=write_json("manifest.json", data), media_root=root)))
    mid = media_id("TEST_OBS_0001")
    item = observation_json(app_client, "TEST_OBS_0001")
    assert item["level0DownloadUrl"] is None and item["level0DownloadAvailable"] is False
    assert item["level1DownloadAvailable"] is True  # the other level is judged on its own
    response = app_client.get(f"{MEDIA}/{mid}/level0")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "level0_not_available"


# --- Deprecated /original alias ----------------------------------------------------------------


def test_deprecated_original_endpoint_still_serves_level1(client):
    mid = media_id("TEST_OBS_0001")
    original = client.get(f"{MEDIA}/{mid}/original")
    level1 = client.get(f"{MEDIA}/{mid}/level1")
    assert original.status_code == 200
    assert original.content == level1.content == level_bytes("TEST_OBS_0001", 1)
    assert original.headers["etag"] == level1.headers["etag"]
    assert original.headers["content-disposition"] == level1.headers["content-disposition"]
    assert original.headers["deprecation"] == "true"
    assert original.headers["link"] == f'<{MEDIA}/{mid}/level1>; rel="successor-version"'
    assert "deprecation" not in level1.headers


def test_deprecated_original_endpoint_follows_level1_permission(registry_data, write_json, media_root):
    only_level0 = client_with_policy(registry_data, write_json, media_root, level0=True, level1=False)
    assert only_level0.get(f"{MEDIA}/{media_id('TEST_OBS_0001')}/original").status_code == 403
    only_level1 = client_with_policy(registry_data, write_json, media_root, level0=False, level1=True)
    assert only_level1.get(f"{MEDIA}/{media_id('TEST_OBS_0001')}/original").status_code == 200


def test_deprecated_original_fields_mirror_level1(registry_data, write_json, media_root):
    only_level0 = client_with_policy(registry_data, write_json, media_root, level0=True, level1=False)
    item = observation_json(only_level0, "TEST_OBS_0001")
    assert item["isOriginalAvailable"] is False and item["originalUrl"] is None
    both = client_with_policy(registry_data, write_json, media_root, level0=True, level1=True)
    item = observation_json(both, "TEST_OBS_0001")
    assert item["isOriginalAvailable"] is True
    assert item["originalUrl"] == item["level1DownloadUrl"]


def test_openapi_operation_ids_are_unique_and_head_still_works(client):
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)  # FastAPI warns on duplicate operation IDs
        paths = client.get("/openapi.json").json()["paths"]
    ids = [operation["operationId"] for path in paths.values() for operation in path.values()]
    assert len(ids) == len(set(ids))
    for kind in ("level0", "level1", "original", "preview", "thumbnail"):
        assert "head" not in paths[f"/media/coastsnap/{{media_id}}/{kind}"]  # HEAD is served but not documented
        assert client.head(f"{MEDIA}/{media_id('TEST_OBS_0001')}/{kind}").status_code == 200


def test_deprecated_original_endpoint_is_marked_in_openapi(client):
    operations = client.get("/openapi.json").json()["paths"]
    assert operations["/media/coastsnap/{media_id}/original"]["get"].get("deprecated") is True
    assert not operations["/media/coastsnap/{media_id}/level1"]["get"].get("deprecated", False)


# --- Preview and thumbnail -------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["preview", "thumbnail"])
def test_derivative_is_served_inline(client, kind):
    response = client.get(f"{MEDIA}/{media_id('TEST_OBS_0001')}/{kind}")
    assert response.status_code == 200
    assert response.content == derivative_bytes("TEST_OBS_0001", kind)
    assert response.headers["content-type"] == "image/jpeg"
    assert "content-disposition" not in response.headers


@pytest.mark.parametrize(
    ("observation_id", "kind"),
    [("TEST_OBS_0004", "preview"), ("TEST_OBS_0005", "preview"), ("TEST_OBS_0005", "thumbnail")],
)
def test_missing_derivative_is_404_and_never_falls_back_to_an_original(client, observation_id, kind):
    response = client.get(f"{MEDIA}/{media_id(observation_id)}/{kind}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == f"{kind}_not_available"
    assert response.content not in (level_bytes(observation_id, 0), level_bytes(observation_id, 1))


def test_derivative_urls_are_null_when_not_generated(client):
    item = observation_json(client, "TEST_OBS_0004")
    assert item["thumbnailUrl"] == f"{MEDIA}/{media_id('TEST_OBS_0004')}/thumbnail"
    assert item["previewUrl"] is None
    item = observation_json(client, "TEST_OBS_0005")
    assert item["thumbnailUrl"] is None and item["previewUrl"] is None
    assert item["level0DownloadUrl"] == f"{MEDIA}/{media_id('TEST_OBS_0005')}/level0"
    assert item["level1DownloadUrl"] == f"{MEDIA}/{media_id('TEST_OBS_0005')}/level1"


def test_recorded_derivative_missing_on_disk_is_503(client, media_root, derivatives_data):
    relative = derivatives_data["derivatives"][0]["preview"]["relative_path"]
    media_file(media_root, relative).unlink()
    response = client.get(f"{MEDIA}/{media_id('TEST_OBS_0001')}/preview")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "media_unavailable"


# --- Unknown, foreign and non-public media ------------------------------------------------------


ALL_KINDS = ["level0", "level1", "original", "preview", "thumbnail"]


@pytest.mark.parametrize("kind", ALL_KINDS)
@pytest.mark.parametrize(
    "unknown",
    [
        "csm_000000000000000000000000",
        "TEST_OBS_0001",
        media_id("TEST_OBS_0006"),  # incomplete manifest entry
        media_id("TEST_OBS_0001", site_id=HIDDEN_SITE_ID),  # ID minted for another (non-public) site
    ],
)
def test_unknown_or_foreign_media_is_404(client, unknown, kind):
    response = client.get(f"{MEDIA}/{unknown}/{kind}")
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "media_not_found", "message": "No public media has this identifier."}}


def test_media_of_non_public_site_is_never_served(registry_data, write_json, media_root):
    data = copy.deepcopy(registry_data)
    data["sites"][0]["publication_status"] = "restricted"  # download flags still true: publication wins
    hidden = TestClient(create_app(fixture_settings(registry=write_json("registry.json", data), media_root=media_root)))
    for kind in ALL_KINDS:
        assert hidden.get(f"{MEDIA}/{media_id('TEST_OBS_0001')}/{kind}").status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        f"{MEDIA}/..%2F..%2Fetc%2Fpasswd/level0",
        f"{MEDIA}/{media_id('TEST_OBS_0001')}/..%2F..%2Fmanifest.json",
        f"{MEDIA}/{media_id('TEST_OBS_0001')}/level-0",
        f"{MEDIA}/{media_id('TEST_OBS_0001')}/level-1",
        f"{MEDIA}/{media_id('TEST_OBS_0001')}/level2",
        f"{MEDIA}/C:%5CWindows%5Cwin.ini/level1",
        f"{MEDIA}/%5C%5Cserver%5Cshare/level0",
        f"{MEDIA}/{media_id('TEST_OBS_0001')}/level1/extra",
    ],
)
def test_request_paths_never_reach_the_filesystem(client, path):
    response = client.get(path)
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


# --- Media not configured --------------------------------------------------------------------------


def test_without_media_root_urls_are_null_and_endpoints_unavailable(client_without_media):
    mid = media_id("TEST_OBS_0001")
    item = client_without_media.get(f"/api/v1/coastsnap/sites/{PUBLIC_SITE_ID}/observations/{mid}").json()
    for field in ("thumbnailUrl", "previewUrl", "level0DownloadUrl", "level1DownloadUrl", "originalUrl",
                  "level0ChecksumSha256", "level1ChecksumSha256"):
        assert item[field] is None, field
    assert item["level0DownloadAvailable"] is False and item["level1DownloadAvailable"] is False
    for level in LEVELS:
        assert client_without_media.get(f"{MEDIA}/{mid}/{level}").status_code == 503
    assert client_without_media.get(f"{MEDIA}/{mid}/thumbnail").status_code == 404  # no index -> not generated


def test_media_base_url_prefixes_media_urls(media_root):
    app_client = TestClient(create_app(fixture_settings(media_root=media_root, media_base_url="http://localhost:8000/")))
    mid = media_id("TEST_OBS_0001")
    item = observation_json(app_client, "TEST_OBS_0001")
    assert item["level0DownloadUrl"] == f"http://localhost:8000/media/coastsnap/{mid}/level0"
    assert item["level1DownloadUrl"] == f"http://localhost:8000/media/coastsnap/{mid}/level1"
    assert item["thumbnailUrl"] == f"http://localhost:8000/media/coastsnap/{mid}/thumbnail"


# --- No filesystem paths or raw source IDs in responses or headers ---------------------------------


def _forbidden(media_root: Path) -> list[str]:
    return [
        "level-0", "level-1", "derivatives/", "root-TEST_ROOT_ID", "TEST_PUBLICATION_ROOT", "TEST_OBS_",
        "TEST_MEDIA_REF_", "source-records", "manifest", "/g/data", "example.invalid", "\\",
        str(media_root), media_root.as_posix(), str(FIXTURES), FIXTURES.as_posix(),
        str(DERIVATIVES_INDEX_PATH.name),
    ]


@pytest.mark.parametrize(
    ("observation_id", "kind"),
    [
        ("TEST_OBS_0001", "level0"),
        ("TEST_OBS_0001", "level1"),
        ("TEST_OBS_0001", "original"),
        ("TEST_OBS_0001", "preview"),
        ("TEST_OBS_0001", "thumbnail"),
        ("TEST_OBS_0004", "preview"),  # 404
        ("TEST_OBS_0006", "level0"),  # 404
    ],
)
def test_media_headers_and_error_bodies_contain_no_paths(client, media_root, observation_id, kind):
    response = client.get(f"{MEDIA}/{media_id(observation_id)}/{kind}")
    header_text = "\n".join(f"{name}: {value}" for name, value in response.headers.items())
    body_text = response.text if response.headers["content-type"].startswith("application/json") else ""
    for forbidden in _forbidden(media_root):
        assert forbidden not in header_text, f"{forbidden!r} leaked in headers"
        assert forbidden not in body_text, f"{forbidden!r} leaked in body"


def test_catalogue_json_contains_no_media_paths_or_source_ids(client, media_root):
    body = client.get(f"/api/v1/coastsnap/sites/{PUBLIC_SITE_ID}/observations", params={"pageSize": 100}).text
    for forbidden in _forbidden(media_root):
        assert forbidden not in body
    for internal_field in ("relativePath", "relative_path", "fileSize", "file_size", "downloadPermitted", "sourceSha256"):
        assert internal_field not in body


def test_published_checksums_are_the_manifest_checksums(client):
    item = observation_json(client, "TEST_OBS_0003")
    entry = manifest_entry("TEST_OBS_0003")
    assert item["level0ChecksumSha256"] == entry["level0"]["checksum"]["sha256"]
    assert item["level1ChecksumSha256"] == entry["level1"]["checksum"]["sha256"]


# --- Derivative integrity and separate derivatives root -------------------------------------------


@pytest.mark.parametrize("kind", ["preview", "thumbnail"])
def test_derivative_etag_is_index_checksum(client, derivatives_data, kind):
    recorded = derivatives_data["derivatives"][0][kind]
    response = client.get(f"{MEDIA}/{media_id('TEST_OBS_0001')}/{kind}")
    assert response.headers["etag"] == f'"{recorded["sha256"]}"'
    assert hashlib.sha256(response.content).hexdigest() == recorded["sha256"]
    assert int(response.headers["content-length"]) == recorded["file_size_bytes"]


def test_derivative_with_size_mismatch_is_503(client, media_root, derivatives_data):
    relative = derivatives_data["derivatives"][0]["thumbnail"]["relative_path"]
    media_file(media_root, relative).write_bytes(b"tampered")
    response = client.get(f"{MEDIA}/{media_id('TEST_OBS_0001')}/thumbnail")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "media_unavailable"


def test_separate_derivatives_root(tmp_path):
    level_root = tmp_path / "staging"
    derivatives_root = tmp_path / "derivatives-out"
    build_media_root(level_root, MANIFEST_PATH, DERIVATIVES_INDEX_PATH, derivatives_root=derivatives_root)
    assert not (level_root / "derivatives").exists()
    app_client = TestClient(create_app(fixture_settings(media_root=level_root, derivatives_root=derivatives_root)))
    mid = media_id("TEST_OBS_0001")
    assert app_client.get(f"{MEDIA}/{mid}/thumbnail").content == derivative_bytes("TEST_OBS_0001", "thumbnail")
    assert app_client.get(f"{MEDIA}/{mid}/level0").content == level_bytes("TEST_OBS_0001", 0)
    assert app_client.get(f"{MEDIA}/{mid}/level1").content == level_bytes("TEST_OBS_0001", 1)


def test_derivatives_are_never_resolved_from_the_level_root_when_a_separate_root_is_set(tmp_path):
    # Derivatives exist only under the Level 0/1 root; the configured derivatives root is empty.
    level_root = build_media_root(tmp_path / "staging", MANIFEST_PATH, DERIVATIVES_INDEX_PATH)
    empty = tmp_path / "empty-derivatives"
    empty.mkdir()
    app_client = TestClient(create_app(fixture_settings(media_root=level_root, derivatives_root=empty)))
    assert app_client.get(f"{MEDIA}/{media_id('TEST_OBS_0001')}/thumbnail").status_code == 503

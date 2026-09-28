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
from synthetic_media import derivative_bytes, level_bytes

MEDIA = "/media/coastsnap"


def media_id(observation_id: str, site_id: str = PUBLIC_SITE_ID) -> str:
    return build_media_id(site_id, observation_id)


def manifest_entry(observation_id: str) -> dict:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return next(e for e in manifest["entries"] if e["observation"]["observation_id"] == observation_id)


def media_file(media_root: Path, relative_path: str) -> Path:
    return media_root.joinpath(*relative_path.split("/"))


# --- Original ---------------------------------------------------------------------------


def test_original_download_serves_level1_bytes(client):
    response = client.get(f"{MEDIA}/{media_id('TEST_OBS_0001')}/original")
    assert response.status_code == 200
    assert response.content == level_bytes("TEST_OBS_0001", 1)
    assert response.content != level_bytes("TEST_OBS_0001", 0)  # provisional policy: Level 1, not Level 0


def test_original_content_type(client):
    response = client.get(f"{MEDIA}/{media_id('TEST_OBS_0001')}/original")
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_original_content_disposition_is_attachment_with_opaque_filename(client):
    mid = media_id("TEST_OBS_0002")
    response = client.get(f"{MEDIA}/{mid}/original")
    assert response.headers["content-disposition"] == f'attachment; filename="{mid}.jpg"'


def test_original_etag_is_catalogue_checksum_and_matches_content(client):
    response = client.get(f"{MEDIA}/{media_id('TEST_OBS_0003')}/original")
    expected = manifest_entry("TEST_OBS_0003")["level1"]["checksum"]["sha256"]
    assert response.headers["etag"] == f'"{expected}"'
    assert hashlib.sha256(response.content).hexdigest() == expected
    assert int(response.headers["content-length"]) == manifest_entry("TEST_OBS_0003")["level1"]["file_size_bytes"]


def test_original_supports_single_range_requests(client):
    full = level_bytes("TEST_OBS_0001", 1)
    response = client.get(f"{MEDIA}/{media_id('TEST_OBS_0001')}/original", headers={"Range": "bytes=0-9"})
    assert response.status_code == 206
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-range"] == f"bytes 0-9/{len(full)}"
    assert response.content == full[:10]


def test_original_range_with_matching_if_range_etag(client):
    mid = media_id("TEST_OBS_0001")
    etag = client.get(f"{MEDIA}/{mid}/original").headers["etag"]
    response = client.get(f"{MEDIA}/{mid}/original", headers={"Range": "bytes=10-19", "If-Range": etag})
    assert response.status_code == 206
    assert response.content == level_bytes("TEST_OBS_0001", 1)[10:20]
    stale = client.get(f"{MEDIA}/{mid}/original", headers={"Range": "bytes=10-19", "If-Range": '"stale"'})
    assert stale.status_code == 200


def test_unsatisfiable_range_is_416(client):
    response = client.get(f"{MEDIA}/{media_id('TEST_OBS_0001')}/original", headers={"Range": "bytes=999999-"})
    assert response.status_code == 416


def test_head_on_original_returns_headers_only(client):
    response = client.head(f"{MEDIA}/{media_id('TEST_OBS_0001')}/original")
    assert response.status_code == 200
    assert response.content == b""
    assert response.headers["content-disposition"].startswith("attachment;")


def test_missing_original_file_is_503(client, media_root):
    media_file(media_root, manifest_entry("TEST_OBS_0002")["level1"]["local_relative_path"]).unlink()
    response = client.get(f"{MEDIA}/{media_id('TEST_OBS_0002')}/original")
    assert response.status_code == 503
    assert response.json() == {
        "error": {"code": "media_unavailable", "message": "This media file is temporarily unavailable."}
    }


def test_original_with_size_mismatch_is_not_served_under_catalogue_etag(client, media_root):
    media_file(media_root, manifest_entry("TEST_OBS_0002")["level1"]["local_relative_path"]).write_bytes(b"tampered")
    response = client.get(f"{MEDIA}/{media_id('TEST_OBS_0002')}/original")
    assert response.status_code == 503


def test_restricted_download_is_403_and_not_advertised(registry_data, write_json, media_root):
    data = copy.deepcopy(registry_data)
    data["sites"][0]["original_download_permitted"] = False
    restricted = TestClient(create_app(fixture_settings(registry=write_json("registry.json", data), media_root=media_root)))
    mid = media_id("TEST_OBS_0001")

    response = restricted.get(f"{MEDIA}/{mid}/original")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "download_not_permitted"

    item = restricted.get(f"/api/v1/coastsnap/sites/{PUBLIC_SITE_ID}/observations/{mid}").json()
    assert item["isOriginalAvailable"] is False
    assert item["originalUrl"] is None
    # Derivatives are still offered for a public site whose originals are restricted.
    assert item["previewUrl"] == f"{MEDIA}/{mid}/preview"
    assert restricted.get(f"{MEDIA}/{mid}/preview").status_code == 200


def test_download_permission_defaults_to_false(registry_data, write_json, media_root):
    data = copy.deepcopy(registry_data)
    del data["sites"][0]["original_download_permitted"]
    default = TestClient(create_app(fixture_settings(registry=write_json("registry.json", data), media_root=media_root)))
    assert default.get(f"{MEDIA}/{media_id('TEST_OBS_0001')}/original").status_code == 403


def test_unsupported_level1_type_is_not_offered(manifest_data, write_json, tmp_path):
    data = copy.deepcopy(manifest_data)
    entry = next(e for e in data["entries"] if e["observation"]["observation_id"] == "TEST_OBS_0001")
    for key in ("local_relative_path", "remote_relative_path"):
        entry["level1"][key] = entry["level1"][key].replace(".jpg", ".heic")
    manifest_path = write_json("manifest.json", data)
    root = tmp_path / "media-heic"
    root.mkdir()
    app_client = TestClient(create_app(fixture_settings(manifest=manifest_path, media_root=root)))
    mid = media_id("TEST_OBS_0001")
    assert app_client.get(f"/api/v1/coastsnap/sites/{PUBLIC_SITE_ID}/observations/{mid}").json()["originalUrl"] is None
    response = app_client.get(f"{MEDIA}/{mid}/original")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "original_not_available"


# --- Preview and thumbnail ---------------------------------------------------------------


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
def test_missing_derivative_is_404_and_never_falls_back_to_original(client, observation_id, kind):
    response = client.get(f"{MEDIA}/{media_id(observation_id)}/{kind}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == f"{kind}_not_available"
    assert response.content != level_bytes(observation_id, 1)


def test_derivative_urls_are_null_when_not_generated(client):
    item = client.get(f"/api/v1/coastsnap/sites/{PUBLIC_SITE_ID}/observations/{media_id('TEST_OBS_0004')}").json()
    assert item["thumbnailUrl"] == f"{MEDIA}/{media_id('TEST_OBS_0004')}/thumbnail"
    assert item["previewUrl"] is None
    item = client.get(f"/api/v1/coastsnap/sites/{PUBLIC_SITE_ID}/observations/{media_id('TEST_OBS_0005')}").json()
    assert item["thumbnailUrl"] is None and item["previewUrl"] is None
    assert item["originalUrl"] == f"{MEDIA}/{media_id('TEST_OBS_0005')}/original"


def test_recorded_derivative_missing_on_disk_is_503(client, media_root, derivatives_data):
    relative = derivatives_data["derivatives"][0]["preview_relative_path"]
    media_file(media_root, relative).unlink()
    response = client.get(f"{MEDIA}/{media_id('TEST_OBS_0001')}/preview")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "media_unavailable"


# --- Unknown, foreign and non-public media -----------------------------------------------


@pytest.mark.parametrize("kind", ["original", "preview", "thumbnail"])
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
    data["sites"][0]["publication_status"] = "restricted"
    hidden = TestClient(create_app(fixture_settings(registry=write_json("registry.json", data), media_root=media_root)))
    for kind in ("original", "preview", "thumbnail"):
        assert hidden.get(f"{MEDIA}/{media_id('TEST_OBS_0001')}/{kind}").status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        f"{MEDIA}/..%2F..%2Fetc%2Fpasswd/original",
        f"{MEDIA}/{media_id('TEST_OBS_0001')}/..%2F..%2Fmanifest.json",
        f"{MEDIA}/{media_id('TEST_OBS_0001')}/level-1",
        f"{MEDIA}/C:%5CWindows%5Cwin.ini/original",
        f"{MEDIA}/%5C%5Cserver%5Cshare/original",
        f"{MEDIA}/{media_id('TEST_OBS_0001')}/original/extra",
    ],
)
def test_request_paths_never_reach_the_filesystem(client, path):
    response = client.get(path)
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


# --- Media not configured ----------------------------------------------------------------


def test_without_media_root_urls_are_null_and_endpoints_unavailable(client_without_media):
    mid = media_id("TEST_OBS_0001")
    item = client_without_media.get(f"/api/v1/coastsnap/sites/{PUBLIC_SITE_ID}/observations/{mid}").json()
    assert item["thumbnailUrl"] is None and item["previewUrl"] is None and item["originalUrl"] is None
    assert item["isOriginalAvailable"] is False
    assert client_without_media.get(f"{MEDIA}/{mid}/original").status_code == 503
    assert client_without_media.get(f"{MEDIA}/{mid}/thumbnail").status_code == 404  # no index -> not generated


def test_media_base_url_prefixes_media_urls(media_root):
    app_client = TestClient(create_app(fixture_settings(media_root=media_root, media_base_url="http://localhost:8000/")))
    mid = media_id("TEST_OBS_0001")
    item = app_client.get(f"/api/v1/coastsnap/sites/{PUBLIC_SITE_ID}/observations/{mid}").json()
    assert item["originalUrl"] == f"http://localhost:8000/media/coastsnap/{mid}/original"
    assert item["thumbnailUrl"] == f"http://localhost:8000/media/coastsnap/{mid}/thumbnail"


# --- No filesystem paths in responses or headers ------------------------------------------


def _forbidden(media_root: Path) -> list[str]:
    return [
        "level-0", "level-1", "derivatives/", "root-TEST_ROOT_ID", "TEST_PUBLICATION_ROOT", "TEST_OBS_",
        "source-records", "manifest", "/g/data", "\\",
        str(media_root), media_root.as_posix(), str(FIXTURES), FIXTURES.as_posix(),
        str(DERIVATIVES_INDEX_PATH.name),
    ]


@pytest.mark.parametrize(
    ("observation_id", "kind"),
    [
        ("TEST_OBS_0001", "original"),
        ("TEST_OBS_0001", "preview"),
        ("TEST_OBS_0001", "thumbnail"),
        ("TEST_OBS_0004", "preview"),  # 404
        ("TEST_OBS_0006", "original"),  # 404
    ],
)
def test_media_headers_and_error_bodies_contain_no_paths(client, media_root, observation_id, kind):
    response = client.get(f"{MEDIA}/{media_id(observation_id)}/{kind}")
    header_text = "\n".join(f"{name}: {value}" for name, value in response.headers.items())
    body_text = response.text if response.headers["content-type"].startswith("application/json") else ""
    for forbidden in _forbidden(media_root):
        assert forbidden not in header_text, f"{forbidden!r} leaked in headers"
        assert forbidden not in body_text, f"{forbidden!r} leaked in body"


def test_catalogue_json_contains_no_media_paths(client, media_root):
    body = client.get(f"/api/v1/coastsnap/sites/{PUBLIC_SITE_ID}/observations", params={"pageSize": 100}).text
    for forbidden in _forbidden(media_root):
        assert forbidden not in body
    for internal_field in ("relativePath", "relative_path", "sha256", "fileSize", "level1"):
        assert internal_field not in body

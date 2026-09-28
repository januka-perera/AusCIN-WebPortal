from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

from auscin_api.catalogue import build_media_id
from auscin_api.main import create_app
from conftest import HIDDEN_SITE_ID, MANIFEST_PATH, PUBLIC_SITE_ID, fixture_settings

BASE = "/api/v1/coastsnap"
PRESENTABLE = ["TEST_OBS_0005", "TEST_OBS_0004", "TEST_OBS_0003", "TEST_OBS_0002", "TEST_OBS_0001"]  # newest first


def media_id(observation_id: str, site_id: str = PUBLIC_SITE_ID) -> str:
    return build_media_id(site_id, observation_id)


# --- Health -----------------------------------------------------------------------------


def test_health_reports_counts_only(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "publicSiteCount": 1, "publicObservationCount": 5}


# --- Sites ------------------------------------------------------------------------------


def test_lists_only_public_sites(client):
    response = client.get(f"{BASE}/sites")
    assert response.status_code == 200
    sites = response.json()
    assert [site["id"] for site in sites] == [PUBLIC_SITE_ID]
    assert HIDDEN_SITE_ID not in response.text
    assert "Hidden Test Point" not in response.text


def test_site_lookup_uses_frontend_shape(client):
    response = client.get(f"{BASE}/sites/{PUBLIC_SITE_ID}")
    assert response.status_code == 200
    assert response.json() == {
        "id": PUBLIC_SITE_ID,
        "name": "Test Beach CoastSnap",
        "state": "NSW",
        "latitude": -33.0,
        "longitude": 151.0,
        "region": "Synthetic test region",
        "description": (
            "Synthetic CoastSnap site used only by the API test suite and local development. Not a real location."
        ),
        "status": "active",
        "establishedSince": "2026-07-01",
        "displayTimeZone": "Australia/Sydney",
        "representativeImageUrl": None,
        "isSynthetic": True,
    }


@pytest.mark.parametrize(
    "path",
    [
        f"{BASE}/sites/{HIDDEN_SITE_ID}",
        f"{BASE}/sites/{HIDDEN_SITE_ID}/observations",
        f"{BASE}/sites/{HIDDEN_SITE_ID}/date-range",
        f"{BASE}/sites/{HIDDEN_SITE_ID}/observations/{media_id('TEST_OBS_0001', HIDDEN_SITE_ID)}",
    ],
)
def test_non_public_site_is_indistinguishable_from_unknown(client, path):
    response = client.get(path)
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "site_not_found", "message": "No public CoastSnap site has this identifier."}
    }


def test_observations_of_a_manifest_mapped_to_a_non_public_site_are_never_exposed(registry_data, write_json):
    # Point the one manifest's root at the embargoed site instead of the public one.
    data = copy.deepcopy(registry_data)
    data["sites"][0]["spotteron_root_id"] = "TEST_ROOT_ID_UNUSED"
    data["sites"][1]["spotteron_root_id"] = "TEST_ROOT_ID"
    hidden_client = TestClient(create_app(fixture_settings(registry=write_json("registry.json", data))))

    assert hidden_client.get("/api/v1/health").json()["publicObservationCount"] == 0
    assert hidden_client.get(f"{BASE}/sites/{PUBLIC_SITE_ID}/observations").json()["total"] == 0
    assert hidden_client.get(f"{BASE}/sites/{HIDDEN_SITE_ID}/observations").status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        f"{BASE}/sites/CS-UNKNOWN",
        f"{BASE}/sites/CS-UNKNOWN/observations",
        f"{BASE}/sites/CS-UNKNOWN/date-range",
        f"{BASE}/sites/cs-test-site",
        f"{BASE}/sites/TEST_ROOT_ID",
    ],
)
def test_unknown_site_returns_controlled_404(client, path):
    response = client.get(path)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "site_not_found"


@pytest.mark.parametrize(
    "path",
    [
        f"{BASE}/sites/..%2F..%2Fetc%2Fpasswd",
        f"{BASE}/sites/{PUBLIC_SITE_ID}/observations/..%2F..%2Fmanifest.json",
        f"{BASE}/sites/{PUBLIC_SITE_ID}/../../../etc/passwd",
        "/api/v1/unknown",
    ],
)
def test_unmatched_and_traversal_urls_return_controlled_404(client, path):
    response = client.get(path)
    assert response.status_code == 404
    assert response.json()["error"]["code"] in {"not_found", "site_not_found", "observation_not_found"}
    assert "passwd" not in response.text and "manifest" not in response.text


def test_write_methods_are_not_allowed(client):
    response = client.post(f"{BASE}/sites")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


# --- Observations -----------------------------------------------------------------------


def test_observation_listing_is_newest_first(client):
    response = client.get(f"{BASE}/sites/{PUBLIC_SITE_ID}/observations")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert body["page"] == 1
    assert body["pageSize"] == 24
    assert body["totalPages"] == 1
    assert [item["id"] for item in body["items"]] == [media_id(o) for o in PRESENTABLE]


def test_observation_preserves_worker_timestamps(client):
    response = client.get(f"{BASE}/sites/{PUBLIC_SITE_ID}/observations/{media_id('TEST_OBS_0001')}")
    assert response.status_code == 200
    item = response.json()
    assert item["capturedAtUtc"] == "2026-08-01T22:30:00Z"
    assert item["capturedAtSourceRaw"] == "2026-08-01 22:30:00"
    assert item["ingestedAtUtc"] == "2026-09-02T01:00:00Z"
    assert item["displayTimeZone"] == "Australia/Sydney"


def test_observation_shape_matches_frontend_contract(client):
    item = client.get(f"{BASE}/sites/{PUBLIC_SITE_ID}/observations/{media_id('TEST_OBS_0003')}").json()
    assert set(item) == {
        "id", "siteId", "sourcePlatform", "mediaId", "mediaType", "capturedAtUtc", "capturedAtSourceRaw",
        "width", "height", "ingestedAtUtc", "displayTimeZone", "contributor", "processingStatus", "publicationStatus",
        "thumbnailUrl", "previewUrl", "isOriginalAvailable", "originalUrl", "caption", "altText", "isSynthetic",
    }
    assert item["id"] == item["mediaId"] == media_id("TEST_OBS_0003")
    assert item["siteId"] == PUBLIC_SITE_ID
    assert item["sourcePlatform"] == "spotteron"
    assert item["processingStatus"] == "processed"
    assert item["publicationStatus"] == "public"
    mid = media_id("TEST_OBS_0003")
    assert item["thumbnailUrl"] == f"/media/coastsnap/{mid}/thumbnail"
    assert item["previewUrl"] == f"/media/coastsnap/{mid}/preview"
    assert item["isOriginalAvailable"] is True
    assert item["originalUrl"] == f"/media/coastsnap/{mid}/original"
    assert item["contributor"] == {
        "displayName": "CoastSnap contributor",
        "attributionText": "CoastSnap community photo (synthetic test data)",
    }
    assert item["caption"] == "Test Beach CoastSnap — CoastSnap observation, 10 August 2026"


def test_observation_lookup_is_site_scoped(client):
    # A media ID computed for another site must never resolve under this one.
    foreign = media_id("TEST_OBS_0001", site_id=HIDDEN_SITE_ID)
    response = client.get(f"{BASE}/sites/{PUBLIC_SITE_ID}/observations/{foreign}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "observation_not_found"


@pytest.mark.parametrize(
    "unknown",
    [
        "csm_000000000000000000000000",
        "TEST_OBS_0001",  # raw source IDs are not public identifiers
        media_id("TEST_OBS_0006"),  # incomplete entry (no Level 1)
    ],
)
def test_unknown_media_returns_controlled_404(client, unknown):
    response = client.get(f"{BASE}/sites/{PUBLIC_SITE_ID}/observations/{unknown}")
    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "observation_not_found",
            "message": "No observation with this identifier exists at this site.",
        }
    }


# --- Filters ----------------------------------------------------------------------------


def ids(response) -> list[str]:
    return [item["id"] for item in response.json()["items"]]


def test_date_filter_uses_site_local_date(client):
    # TEST_OBS_0001 is 22:30 UTC on 1 Aug = 08:30 on 2 Aug in Sydney.
    response = client.get(f"{BASE}/sites/{PUBLIC_SITE_ID}/observations", params={"date": "2026-08-02"})
    assert ids(response) == [media_id("TEST_OBS_0002"), media_id("TEST_OBS_0001")]
    empty = client.get(f"{BASE}/sites/{PUBLIC_SITE_ID}/observations", params={"date": "2026-08-01"})
    assert empty.json()["total"] == 0


def test_inclusive_date_range_filter(client):
    response = client.get(
        f"{BASE}/sites/{PUBLIC_SITE_ID}/observations", params={"from": "2026-08-10", "to": "2026-08-21"}
    )
    assert ids(response) == [media_id("TEST_OBS_0004"), media_id("TEST_OBS_0003")]


def test_media_type_filter(client):
    url = f"{BASE}/sites/{PUBLIC_SITE_ID}/observations"
    assert client.get(url, params={"mediaType": "image"}).json()["total"] == 5
    assert client.get(url, params={"mediaType": "timelapse"}).json()["total"] == 0


@pytest.mark.parametrize(
    "params",
    [{"date": "01-08-2026"}, {"from": "2026-13-01"}, {"mediaType": "video"}, {"page": "0"}, {"pageSize": "101"}],
)
def test_invalid_query_parameters_are_rejected(client, params):
    response = client.get(f"{BASE}/sites/{PUBLIC_SITE_ID}/observations", params=params)
    assert response.status_code == 422


# --- Pagination -------------------------------------------------------------------------


def test_pagination_pages_through_results(client):
    url = f"{BASE}/sites/{PUBLIC_SITE_ID}/observations"
    first = client.get(url, params={"pageSize": 2, "page": 1}).json()
    second = client.get(url, params={"pageSize": 2, "page": 2}).json()
    third = client.get(url, params={"pageSize": 2, "page": 3}).json()
    assert (first["total"], first["totalPages"], first["pageSize"]) == (5, 3, 2)
    assert [i["id"] for i in first["items"] + second["items"] + third["items"]] == [media_id(o) for o in PRESENTABLE]
    assert len(third["items"]) == 1


def test_out_of_range_page_is_clamped_like_the_frontend(client):
    body = client.get(f"{BASE}/sites/{PUBLIC_SITE_ID}/observations", params={"pageSize": 2, "page": 99}).json()
    assert body["page"] == 3
    assert [i["id"] for i in body["items"]] == [media_id("TEST_OBS_0001")]


def test_empty_result_has_one_page(client):
    body = client.get(f"{BASE}/sites/{PUBLIC_SITE_ID}/observations", params={"date": "2020-01-01"}).json()
    assert body == {"items": [], "total": 0, "page": 1, "pageSize": 24, "totalPages": 1}


# --- Date range -------------------------------------------------------------------------


def test_date_range_returns_earliest_and_latest(client):
    body = client.get(f"{BASE}/sites/{PUBLIC_SITE_ID}/date-range").json()
    assert body["earliest"]["id"] == media_id("TEST_OBS_0001")
    assert body["latest"]["id"] == media_id("TEST_OBS_0005")


def test_date_range_of_public_site_without_observations_is_null(registry_data, write_json):
    data = copy.deepcopy(registry_data)
    data["sites"][0]["spotteron_root_id"] = "TEST_ROOT_ID_EMPTY"
    empty_client = TestClient(create_app(fixture_settings(registry=write_json("registry.json", data))))
    response = empty_client.get(f"{BASE}/sites/{PUBLIC_SITE_ID}/date-range")
    assert response.status_code == 200
    assert response.json() == {"earliest": None, "latest": None}


# --- No filesystem paths or internal identifiers in any response ------------------------

FORBIDDEN_SUBSTRINGS = [
    "level-0",
    "level-1",
    "root-TEST_ROOT_ID",
    "TEST_ROOT_ID",
    "TEST_PUBLICATION_ROOT",
    "TEST_OBS_",
    "TEST_MEDIA_REF_",
    "source-records",
    "manifests/",
    "manifest.json",
    "sites-registry",
    ".jpg",
    "example.invalid",
    "/g/data",
    "\\\\",
    str(MANIFEST_PATH.parent),
    str(MANIFEST_PATH.parent).replace("\\", "/"),
]


def all_json_paths() -> list[str]:
    obs = [media_id(o) for o in PRESENTABLE]
    return [
        "/api/v1/health",
        f"{BASE}/sites",
        f"{BASE}/sites/{PUBLIC_SITE_ID}",
        f"{BASE}/sites/{PUBLIC_SITE_ID}/observations?pageSize=100",
        f"{BASE}/sites/{PUBLIC_SITE_ID}/date-range",
        *[f"{BASE}/sites/{PUBLIC_SITE_ID}/observations/{o}" for o in obs],
        f"{BASE}/sites/{HIDDEN_SITE_ID}",
        f"{BASE}/sites/{PUBLIC_SITE_ID}/observations/TEST_OBS_0001",
    ]


@pytest.mark.parametrize("path", all_json_paths())
def test_responses_contain_no_paths_or_source_identifiers(client, media_root, path):
    response = client.get(path)
    assert response.headers["content-type"].startswith("application/json")
    forbidden_values = [*FORBIDDEN_SUBSTRINGS, "derivatives/", str(media_root), media_root.as_posix()]
    for forbidden in forbidden_values:
        # The last path deliberately requests a raw source ID; it must not be echoed.
        assert forbidden not in response.text, f"{forbidden!r} leaked from {path}"


# --- Dimensions -------------------------------------------------------------------------


def test_dimensions_come_from_the_derivatives_index(client):
    # The fixture index records the synthetic Level 1 files' real 8x6 dimensions.
    item = client.get(f"{BASE}/sites/{PUBLIC_SITE_ID}/observations/{media_id('TEST_OBS_0001')}").json()
    assert (item["width"], item["height"]) == (8, 6)


def test_dimensions_are_null_without_a_derivatives_entry(client, client_without_media):
    # TEST_OBS_0005 has no derivatives entry; without an index nothing has dimensions.
    item = client.get(f"{BASE}/sites/{PUBLIC_SITE_ID}/observations/{media_id('TEST_OBS_0005')}").json()
    assert item["width"] is None and item["height"] is None
    bare = client_without_media.get(f"{BASE}/sites/{PUBLIC_SITE_ID}/observations/{media_id('TEST_OBS_0001')}").json()
    assert bare["width"] is None and bare["height"] is None


def test_dimensions_of_a_stale_derivatives_entry_are_not_returned(derivatives_data, write_json, media_root):
    data = copy.deepcopy(derivatives_data)
    data["derivatives"][0]["source_sha256"] = "0" * 64  # TEST_OBS_0001's entry no longer matches its Level 1
    stale = TestClient(create_app(fixture_settings(derivatives_index=write_json("d.json", data), media_root=media_root)))
    item = stale.get(f"{BASE}/sites/{PUBLIC_SITE_ID}/observations/{media_id('TEST_OBS_0001')}").json()
    assert item["width"] is None and item["height"] is None

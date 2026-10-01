"""Site publication eligibility: public registry policy + confirmed manifest coordinate + a presentable image.

Synthetic fixtures only. No Spotteron, no /g/data, no real files beyond pytest's temp directory.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

import pytest
from fastapi.testclient import TestClient

from auscin_api.catalogue import CatalogueError, build_media_id, load_catalogue
from auscin_api.main import create_app
from conftest import MANIFEST_PATH, PUBLIC_SITE_ID, REGISTRY_PATH, fixture_settings

BASE = "/api/v1/coastsnap"
FIRST_OBSERVATION = build_media_id(PUBLIC_SITE_ID, "TEST_OBS_0001")


def with_site(manifest_data: dict[str, Any], **fields: Any) -> dict[str, Any]:
    """The same site record change applied to every entry, as the worker writes it."""
    data = copy.deepcopy(manifest_data)
    for entry in data["entries"]:
        entry["site"].update(fields)
    return data


def assert_site_omitted(client: TestClient) -> None:
    assert client.get("/api/v1/health").json() == {"status": "ok", "publicSiteCount": 0, "publicObservationCount": 0}
    assert client.get(f"{BASE}/sites").json() == []
    for path in (
        f"{BASE}/sites/{PUBLIC_SITE_ID}",
        f"{BASE}/sites/{PUBLIC_SITE_ID}/observations",
        f"{BASE}/sites/{PUBLIC_SITE_ID}/date-range",
        f"{BASE}/sites/{PUBLIC_SITE_ID}/observations/{FIRST_OBSERVATION}",
    ):
        response = client.get(path)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "site_not_found"


# --- Eligible ----------------------------------------------------------------------------------


def test_eligible_site_is_listed_with_consistent_counts(client):
    sites = client.get(f"{BASE}/sites").json()
    assert [(s["id"], s["latitude"], s["longitude"]) for s in sites] == [(PUBLIC_SITE_ID, -33.0, 151.0)]
    observations = client.get(f"{BASE}/sites/{PUBLIC_SITE_ID}/observations").json()
    health = client.get("/api/v1/health").json()
    assert health["publicSiteCount"] == len(sites) == 1
    assert health["publicObservationCount"] == observations["total"] == 5


def test_public_coordinates_come_from_the_manifest_not_the_registry(manifest_data, registry_data, write_json):
    manifest = with_site(manifest_data, latitude=-33.0004, longitude=151.0003)
    registry = copy.deepcopy(registry_data)
    registry["sites"][0].update(latitude=-12.5, longitude=130.8)  # a legacy registry value that differs
    client = TestClient(create_app(fixture_settings(
        registry=write_json("registry.json", registry), manifest=write_json("manifest.json", manifest),
    )))

    site = client.get(f"{BASE}/sites/{PUBLIC_SITE_ID}").json()
    assert (site["latitude"], site["longitude"]) == (-33.0004, 151.0003)
    assert [(s["latitude"], s["longitude"]) for s in client.get(f"{BASE}/sites").json()] == [(-33.0004, 151.0003)]


def test_registry_without_coordinates_is_valid(registry_data):
    assert "latitude" not in registry_data["sites"][0] and "longitude" not in registry_data["sites"][0]
    assert load_catalogue(REGISTRY_PATH, MANIFEST_PATH).public_site_count == 1


def test_coordinate_provenance_is_not_exposed(client):
    text = client.get(f"{BASE}/sites").text + client.get(f"{BASE}/sites/{PUBLIC_SITE_ID}").text
    for forbidden in ("coordinate", "spotteron-observation-mean", "confirmed", "TEST_ROOT_ID"):
        assert forbidden not in text


# --- Not confirmed: omitted ---------------------------------------------------------------------


def test_manifest_from_before_coordinate_discovery_loads_but_publishes_nothing(manifest_data, write_json):
    data = copy.deepcopy(manifest_data)
    for entry in data["entries"]:
        entry["site"] = {"root_id": "TEST_ROOT_ID", "name": None, "latitude": None, "longitude": None}
    path = write_json("manifest.json", data)

    catalogue = load_catalogue(REGISTRY_PATH, path)
    assert catalogue.public_site_count == 0
    assert catalogue.public_observation_count == 0
    assert_site_omitted(TestClient(create_app(fixture_settings(manifest=path))))


def test_null_status_with_coordinates_is_not_treated_as_confirmed(manifest_data, write_json):
    data = with_site(manifest_data, coordinate_status=None)  # latitude/longitude still set
    assert_site_omitted(TestClient(create_app(fixture_settings(manifest=write_json("manifest.json", data)))))


@pytest.mark.parametrize("status", ["missing", "invalid", "inconsistent"])
def test_unconfirmed_coordinate_status_is_omitted(manifest_data, write_json, status):
    data = with_site(manifest_data, coordinate_status=status, latitude=None, longitude=None, coordinate_error="x")
    assert_site_omitted(TestClient(create_app(fixture_settings(manifest=write_json("manifest.json", data)))))


def test_unconfirmed_status_never_falls_back_to_registry_coordinates(manifest_data, registry_data, write_json):
    manifest = with_site(manifest_data, coordinate_status="missing", latitude=None, longitude=None)
    registry = copy.deepcopy(registry_data)
    registry["sites"][0].update(latitude=-33.0, longitude=151.0)
    client = TestClient(create_app(fixture_settings(
        registry=write_json("registry.json", registry), manifest=write_json("manifest.json", manifest),
    )))
    assert_site_omitted(client)


def test_unknown_coordinate_status_is_rejected_as_invalid_input(manifest_data, write_json):
    data = with_site(manifest_data, coordinate_status="probably")
    with pytest.raises(CatalogueError, match="Invalid manifest"):
        load_catalogue(REGISTRY_PATH, write_json("manifest.json", data))


@pytest.mark.parametrize(
    "latitude, longitude",
    [(None, 151.0), (-33.0, None), (-91.0, 151.0), (-33.0, 181.0), (0.0, 0.0)],
)
def test_confirmed_record_without_valid_coordinates_is_rejected(manifest_data, write_json, latitude, longitude):
    data = with_site(manifest_data, latitude=latitude, longitude=longitude)
    with pytest.raises(CatalogueError, match="confirmed but has missing or invalid coordinates"):
        load_catalogue(REGISTRY_PATH, write_json("manifest.json", data))


def test_disagreeing_site_records_are_withheld_not_published(manifest_data, write_json, caplog):
    """An interrupted worker run can leave some entries with the bare pre-discovery site record."""
    data = copy.deepcopy(manifest_data)
    data["entries"][-1]["site"] = {"root_id": "TEST_ROOT_ID", "name": None, "latitude": None, "longitude": None}
    path = write_json("manifest.json", data)

    with caplog.at_level(logging.WARNING, logger="auscin_api.catalogue"):
        assert load_catalogue(REGISTRY_PATH, path).public_site_count == 0
    assert "disagree" in caplog.text
    assert_site_omitted(TestClient(create_app(fixture_settings(manifest=path))))


def test_disagreeing_confirmed_coordinates_are_withheld(manifest_data, write_json):
    data = copy.deepcopy(manifest_data)
    data["entries"][0]["site"]["latitude"] = -33.5
    assert load_catalogue(REGISTRY_PATH, write_json("manifest.json", data)).public_site_count == 0


def test_site_record_from_another_root_is_still_rejected(manifest_data, write_json):
    data = copy.deepcopy(manifest_data)
    data["entries"][0]["site"]["root_id"] = "OTHER_ROOT"
    with pytest.raises(CatalogueError, match="does not belong to manifest root_id"):
        load_catalogue(REGISTRY_PATH, write_json("manifest.json", data))


# --- No presentable image: omitted ----------------------------------------------------------------


def test_manifest_without_entries_publishes_nothing(manifest_data, write_json):
    data = copy.deepcopy(manifest_data)
    data["entries"] = []
    client = TestClient(create_app(fixture_settings(manifest=write_json("manifest.json", data), derivatives_index=None)))
    assert_site_omitted(client)


@pytest.mark.parametrize(
    "drop",
    [("level0",), ("level1",), ("observation", "spotted_at_utc")],
    ids=["no-level0", "no-level1", "no-capture-time"],
)
def test_confirmed_site_with_only_incomplete_observations_is_omitted(manifest_data, write_json, media_root, drop):
    data = copy.deepcopy(manifest_data)
    for entry in data["entries"]:
        target = entry
        for key in drop[:-1]:
            target = target[key]
        target[drop[-1]] = None
        if drop[-1] == "level0":
            entry["level0_transfer"] = None
        if drop[-1] == "level1":
            entry["level1_transfer"] = None
    client = TestClient(create_app(fixture_settings(
        manifest=write_json("manifest.json", data), derivatives_index=None, media_root=media_root,
    )))

    assert_site_omitted(client)
    assert client.get(f"/media/coastsnap/{FIRST_OBSERVATION}/level1").status_code == 404


def test_one_presentable_observation_is_enough(manifest_data, write_json):
    data = copy.deepcopy(manifest_data)
    for entry in data["entries"][1:]:
        entry["level1"] = None
        entry["level1_transfer"] = None
    client = TestClient(create_app(fixture_settings(manifest=write_json("manifest.json", data), derivatives_index=None)))

    assert [s["id"] for s in client.get(f"{BASE}/sites").json()] == [PUBLIC_SITE_ID]
    assert client.get("/api/v1/health").json()["publicObservationCount"] == 1


# --- Non-public: omitted -----------------------------------------------------------------------


@pytest.mark.parametrize("status", ["embargoed", "project-only", "restricted"])
def test_confirmed_site_with_images_is_omitted_unless_public(registry_data, write_json, media_root, status):
    data = copy.deepcopy(registry_data)
    data["sites"][0]["publication_status"] = status
    client = TestClient(create_app(fixture_settings(registry=write_json("registry.json", data), media_root=media_root)))

    assert_site_omitted(client)
    assert client.get(f"/media/coastsnap/{FIRST_OBSERVATION}/level1").status_code == 404

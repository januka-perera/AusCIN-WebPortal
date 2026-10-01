"""Several explicitly configured manifests, one per site/root, combined into one catalogue.

The second site is derived from the committed synthetic fixtures by renaming
the root (TEST_ROOT_ID -> TEST_ROOT_ID_B) and moving its confirmed coordinate.
Everything is written under pytest's temp directory. Nothing scans a directory,
calls Spotteron or touches /g/data.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from auscin_api import catalogue as catalogue_module
from auscin_api.catalogue import CatalogueError, build_media_id, load_multi_site_catalogue
from auscin_api.main import create_app
from auscin_api.settings import Settings
from conftest import DERIVATIVES_INDEX_PATH, MANIFEST_PATH, PUBLIC_SITE_ID, REGISTRY_PATH
from synthetic_media import build_media_root

BASE = "/api/v1/coastsnap"
SECOND_SITE_ID = "CS-TEST-SECOND"
SECOND_ROOT = "TEST_ROOT_ID_B"
SECOND_COORDINATE = (-34.0, 151.5)


def rename_root(data: dict[str, Any]) -> dict[str, Any]:
    """The same synthetic records under another root: IDs, site record and every relative path."""
    return json.loads(json.dumps(data).replace('"TEST_ROOT_ID"', f'"{SECOND_ROOT}"').replace(
        "root-TEST_ROOT_ID/", f"root-{SECOND_ROOT}/").replace("sites/TEST_ROOT_ID.json", f"sites/{SECOND_ROOT}.json"))


def second_manifest(**site_fields: Any) -> dict[str, Any]:
    data = rename_root(json.loads(MANIFEST_PATH.read_text(encoding="utf-8")))
    for entry in data["entries"]:
        entry["site"].update({"latitude": SECOND_COORDINATE[0], "longitude": SECOND_COORDINATE[1], **site_fields})
    return data


def two_site_registry(**second_overrides: Any) -> dict[str, Any]:
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    second = copy.deepcopy(data["sites"][0])
    second.update({"site_id": SECOND_SITE_ID, "spotteron_root_id": SECOND_ROOT,
                   "name": "Another Test Beach CoastSnap", **second_overrides})
    data["sites"].append(second)
    return data


class Inputs:
    """Writes the configured files and builds settings/clients from them."""

    def __init__(self, tmp_path: Path):
        self.dir = tmp_path

    def write(self, name: str, data: dict[str, Any]) -> Path:
        path = self.dir / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def settings(self, registry: Path, manifests: list[Path], indexes: list[Path] = (), media_root: Path | None = None):
        return Settings(environment="test", site_registry_path=registry, manifest_paths=tuple(manifests),
                        derivatives_index_paths=tuple(indexes), media_root=media_root)

    def client(self, *args, **kwargs) -> TestClient:
        return TestClient(create_app(self.settings(*args, **kwargs)))


@pytest.fixture
def inputs(tmp_path: Path) -> Inputs:
    return Inputs(tmp_path)


@pytest.fixture
def two_sites(inputs: Inputs):
    registry = inputs.write("registry.json", two_site_registry())
    manifest_b = inputs.write("manifest-b.json", second_manifest())
    index_b = inputs.write("derivatives-b.json", rename_root(json.loads(DERIVATIVES_INDEX_PATH.read_text("utf-8"))))
    media = build_media_root(inputs.dir / "media", MANIFEST_PATH, DERIVATIVES_INDEX_PATH)
    build_media_root(media, manifest_b, index_b)
    return registry, manifest_b, index_b, media


# --- Two eligible sites ---------------------------------------------------------------------------


def test_two_manifests_publish_two_sites_with_their_own_coordinates(inputs, two_sites):
    registry, manifest_b, index_b, media = two_sites
    client = inputs.client(registry, [MANIFEST_PATH, manifest_b], [DERIVATIVES_INDEX_PATH, index_b], media)

    sites = client.get(f"{BASE}/sites").json()
    assert [(s["id"], s["latitude"], s["longitude"]) for s in sites] == [
        (SECOND_SITE_ID, *SECOND_COORDINATE),  # "Another Test Beach" sorts before "Test Beach"
        (PUBLIC_SITE_ID, -33.0, 151.0),
    ]
    assert set(sites[0]) == set(sites[1])  # the same response shape the frontend already validates
    assert client.get("/api/v1/health").json() == {"status": "ok", "publicSiteCount": 2, "publicObservationCount": 10}


def test_observations_stay_isolated_to_their_own_site(inputs, two_sites):
    registry, manifest_b, index_b, media = two_sites
    client = inputs.client(registry, [MANIFEST_PATH, manifest_b], [DERIVATIVES_INDEX_PATH, index_b], media)

    a = client.get(f"{BASE}/sites/{PUBLIC_SITE_ID}/observations").json()["items"]
    b = client.get(f"{BASE}/sites/{SECOND_SITE_ID}/observations").json()["items"]
    assert {o["siteId"] for o in a} == {PUBLIC_SITE_ID} and {o["siteId"] for o in b} == {SECOND_SITE_ID}
    assert not {o["mediaId"] for o in a} & {o["mediaId"] for o in b}
    # A media ID is never resolved under the other site.
    assert client.get(f"{BASE}/sites/{PUBLIC_SITE_ID}/observations/{b[0]['mediaId']}").status_code == 404


def test_each_site_serves_its_own_media_and_derivatives(inputs, two_sites):
    registry, manifest_b, index_b, media = two_sites
    client = inputs.client(registry, [MANIFEST_PATH, manifest_b], [index_b, DERIVATIVES_INDEX_PATH], media)

    b_id = build_media_id(SECOND_SITE_ID, "TEST_OBS_0001")
    observation = client.get(f"{BASE}/sites/{SECOND_SITE_ID}/observations/{b_id}").json()
    assert observation["thumbnailUrl"] == f"/media/coastsnap/{b_id}/thumbnail"
    assert client.get(f"/media/coastsnap/{b_id}/level1").status_code == 200
    assert client.get(f"/media/coastsnap/{b_id}/thumbnail").status_code == 200


def test_manifest_and_index_order_do_not_change_any_response(inputs, two_sites):
    registry, manifest_b, index_b, media = two_sites
    forward = inputs.client(registry, [MANIFEST_PATH, manifest_b], [DERIVATIVES_INDEX_PATH, index_b], media)
    reverse = inputs.client(registry, [manifest_b, MANIFEST_PATH], [index_b, DERIVATIVES_INDEX_PATH], media)
    for path in (f"{BASE}/sites", f"{BASE}/sites/{PUBLIC_SITE_ID}/observations",
                 f"{BASE}/sites/{SECOND_SITE_ID}/observations", "/api/v1/health"):
        assert forward.get(path).json() == reverse.get(path).json()


def test_a_manifest_without_an_index_offers_no_derivatives_for_that_site_only(inputs, two_sites):
    registry, manifest_b, _index_b, media = two_sites
    client = inputs.client(registry, [MANIFEST_PATH, manifest_b], [DERIVATIVES_INDEX_PATH], media)
    a = client.get(f"{BASE}/sites/{PUBLIC_SITE_ID}/observations").json()["items"]
    b = client.get(f"{BASE}/sites/{SECOND_SITE_ID}/observations").json()["items"]
    assert any(o["thumbnailUrl"] for o in a)
    assert all(o["thumbnailUrl"] is None for o in b)


# --- One eligible, one hidden ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("registry_overrides", "site_fields"),
    [
        ({"publication_status": "embargoed"}, {}),
        ({}, {"coordinate_status": "inconsistent", "latitude": None, "longitude": None}),
        ({}, {"coordinate_status": None}),
    ],
    ids=["not-public", "unconfirmed-coordinate", "pre-discovery-manifest"],
)
def test_an_ineligible_site_is_hidden_without_affecting_the_other(inputs, registry_overrides, site_fields):
    registry = inputs.write("registry.json", two_site_registry(**registry_overrides))
    manifest_b = inputs.write("manifest-b.json", second_manifest(**site_fields))
    client = inputs.client(registry, [MANIFEST_PATH, manifest_b])

    assert [s["id"] for s in client.get(f"{BASE}/sites").json()] == [PUBLIC_SITE_ID]
    assert client.get(f"{BASE}/sites/{SECOND_SITE_ID}").status_code == 404
    assert client.get("/api/v1/health").json()["publicSiteCount"] == 1


def test_a_site_without_presentable_images_is_hidden_without_affecting_the_other(inputs):
    registry = inputs.write("registry.json", two_site_registry())
    data = second_manifest()
    for entry in data["entries"]:
        entry["level1"] = None
        entry["level1_transfer"] = None
    client = inputs.client(registry, [MANIFEST_PATH, inputs.write("manifest-b.json", data)])
    assert [s["id"] for s in client.get(f"{BASE}/sites").json()] == [PUBLIC_SITE_ID]


def test_a_manifest_with_no_registry_entry_is_hidden(inputs):
    manifest_b = inputs.write("manifest-b.json", second_manifest())
    catalogue = load_multi_site_catalogue(REGISTRY_PATH, [MANIFEST_PATH, manifest_b])
    assert [s.id for s in catalogue.list_sites()] == [PUBLIC_SITE_ID]


# --- Conflicts and corrupt input reject the whole catalogue ------------------------------------------


def test_the_same_root_in_two_manifests_is_rejected(inputs, manifest_data):
    copy_path = inputs.write("manifest-copy.json", manifest_data)
    with pytest.raises(CatalogueError, match="more than one manifest for root_id 'TEST_ROOT_ID'"):
        load_multi_site_catalogue(REGISTRY_PATH, [MANIFEST_PATH, copy_path])


def test_duplicate_site_ids_in_the_registry_are_rejected(inputs):
    registry = inputs.write("registry.json", two_site_registry(site_id=PUBLIC_SITE_ID))
    manifest_b = inputs.write("manifest-b.json", second_manifest())
    with pytest.raises(CatalogueError, match="duplicate site_id"):
        load_multi_site_catalogue(registry, [MANIFEST_PATH, manifest_b])


def test_one_root_mapped_to_two_registry_sites_is_rejected(inputs):
    registry = inputs.write("registry.json", two_site_registry(spotteron_root_id="TEST_ROOT_ID"))
    with pytest.raises(CatalogueError, match="duplicate spotteron_root_id"):
        load_multi_site_catalogue(registry, [MANIFEST_PATH])


def test_duplicate_public_media_ids_are_rejected(inputs, monkeypatch):
    registry = inputs.write("registry.json", two_site_registry())
    manifest_b = inputs.write("manifest-b.json", second_manifest())
    monkeypatch.setattr(catalogue_module, "build_media_id", lambda site_id, observation_id: f"csm_{observation_id}")
    with pytest.raises(CatalogueError, match="duplicate public media ID"):
        load_multi_site_catalogue(registry, [MANIFEST_PATH, manifest_b])


def test_an_observation_from_another_root_is_rejected_with_its_manifest_named(inputs):
    data = second_manifest()
    data["entries"][0]["observation"]["root_id"] = "TEST_ROOT_ID"
    with pytest.raises(CatalogueError, match=f"manifest for root_id '{SECOND_ROOT}'.*does not belong"):
        load_multi_site_catalogue(REGISTRY_PATH, [MANIFEST_PATH, inputs.write("manifest-b.json", data)])


def test_a_corrupt_second_manifest_publishes_nothing(inputs):
    registry = inputs.write("registry.json", two_site_registry())
    data = second_manifest()
    data["entries"][0]["level1"]["local_relative_path"] = "../../etc/passwd"
    with pytest.raises(CatalogueError, match="local_relative_path"):
        load_multi_site_catalogue(registry, [MANIFEST_PATH, inputs.write("manifest-b.json", data)])


def test_an_index_for_an_unconfigured_root_is_rejected(inputs):
    index_b = inputs.write("derivatives-b.json", rename_root(json.loads(DERIVATIVES_INDEX_PATH.read_text("utf-8"))))
    with pytest.raises(CatalogueError, match="does not match any configured manifest root_id"):
        load_multi_site_catalogue(REGISTRY_PATH, [MANIFEST_PATH], [index_b])


def test_two_indexes_for_one_root_are_rejected(inputs, derivatives_data):
    copy_path = inputs.write("derivatives-copy.json", derivatives_data)
    with pytest.raises(CatalogueError, match="more than one derivatives index for root_id 'TEST_ROOT_ID'"):
        load_multi_site_catalogue(REGISTRY_PATH, [MANIFEST_PATH], [DERIVATIVES_INDEX_PATH, copy_path])


def test_an_index_claiming_a_root_but_built_from_another_manifest_is_rejected(inputs, two_sites):
    """Index B's header says root B, but its entries are root A's renditions (paths under root-TEST_ROOT_ID)."""
    registry, manifest_b, _index_b, _media = two_sites
    wrong = json.loads(DERIVATIVES_INDEX_PATH.read_text("utf-8"))
    wrong["root_id"] = SECOND_ROOT
    with pytest.raises(CatalogueError, match=f"manifest for root_id '{SECOND_ROOT}'.*derivative"):
        load_multi_site_catalogue(registry, [MANIFEST_PATH, manifest_b], [inputs.write("wrong.json", wrong)])


def test_an_empty_manifest_list_is_rejected():
    with pytest.raises(CatalogueError, match="at least one manifest"):
        load_multi_site_catalogue(REGISTRY_PATH, [])


# --- Configuration end to end -----------------------------------------------------------------------


def test_the_singular_setting_still_serves_the_one_fixture_site():
    settings = Settings.from_env({
        "AUSCIN_API_ENV": "test",
        "COASTSNAP_SITE_REGISTRY_PATH": str(REGISTRY_PATH),
        "COASTSNAP_MANIFEST_PATH": str(MANIFEST_PATH),
        "COASTSNAP_DERIVATIVES_INDEX_PATH": str(DERIVATIVES_INDEX_PATH),
    })
    client = TestClient(create_app(settings))
    assert [s["id"] for s in client.get(f"{BASE}/sites").json()] == [PUBLIC_SITE_ID]


def test_the_list_setting_serves_every_listed_site(two_sites):
    registry, manifest_b, index_b, _media = two_sites
    settings = Settings.from_env({
        "AUSCIN_API_ENV": "test",
        "COASTSNAP_SITE_REGISTRY_PATH": str(registry),
        "COASTSNAP_MANIFEST_PATHS": os.pathsep.join([str(MANIFEST_PATH), str(manifest_b)]),
        "COASTSNAP_DERIVATIVES_INDEX_PATHS": os.pathsep.join([str(index_b), str(DERIVATIVES_INDEX_PATH)]),
    })
    client = TestClient(create_app(settings))
    assert [s["id"] for s in client.get(f"{BASE}/sites").json()] == [SECOND_SITE_ID, PUBLIC_SITE_ID]

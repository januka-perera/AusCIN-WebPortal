from __future__ import annotations

import pytest

from coastsnap_import.image_resolver import (
    ImageUrlResolutionError,
    resolve_attribution_permitted,
    resolve_contributor_display_name,
    resolve_latitude,
    resolve_level0_image_url,
    resolve_longitude,
    resolve_media_reference,
)
from tests.conftest import load_fixture


def _spot(index: int = 0) -> dict:
    return load_fixture("spotteron_page_1.json")["data"][index]


def test_resolves_image_url_from_attributes():
    assert resolve_level0_image_url(_spot(0)) == "https://cdn.example-spotteron.test/images/1001.jpg"


def test_raises_when_no_candidate_field_matches():
    no_image_spot = load_fixture("spotteron_no_image.json")["data"][0]
    with pytest.raises(ImageUrlResolutionError, match="1001|2001"):
        resolve_level0_image_url(no_image_spot)


def test_ignores_non_http_values():
    spot = {"attributes": {"image_url": "not-a-url"}}
    with pytest.raises(ImageUrlResolutionError):
        resolve_level0_image_url(spot)


def test_resolves_latitude_and_longitude():
    spot = _spot(0)
    assert resolve_latitude(spot) == -33.45
    assert resolve_longitude(spot) == 151.4


def test_missing_coordinates_return_none():
    assert resolve_latitude({"attributes": {}}) is None
    assert resolve_longitude({"attributes": {}}) is None


def test_resolves_contributor_display_name():
    assert resolve_contributor_display_name(_spot(0)) == "Test Contributor A"


def test_resolves_media_reference_when_present():
    spot = {"attributes": {"image_id": "img-123"}}
    assert resolve_media_reference(spot) == "img-123"


def test_media_reference_absent_returns_none():
    assert resolve_media_reference({"attributes": {}}) is None


def test_attribution_permitted_true_when_flag_true():
    assert resolve_attribution_permitted(_spot(0)) is True


def test_attribution_permitted_false_when_flag_false():
    assert resolve_attribution_permitted(_spot(1)) is False


def test_attribution_permitted_defaults_false_when_absent():
    assert resolve_attribution_permitted({"attributes": {}}) is False
    assert resolve_attribution_permitted({}) is False

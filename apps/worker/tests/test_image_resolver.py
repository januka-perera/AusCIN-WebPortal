"""Image-reference resolution tests. HTTP validation is mocked with
`responses` throughout — no test here ever makes a real network call.
See spotteron_real_shape.json for the confirmed real Spotteron
attributes.image reference shape this module is built against.
"""

from __future__ import annotations

import pytest
import responses

from coastsnap_import.image_resolver import (
    ImageUrlResolutionError,
    ImageUrlResolver,
    peek_image_reference_or_url,
    resolve_attribution_permitted,
    resolve_contributor_display_name,
    resolve_latitude,
    resolve_longitude,
    resolve_media_reference,
)
from tests.conftest import load_fixture

IMAGE_BASE_URL = "https://files.spotteron.test/images/spots"
REAL_SHAPE_REFERENCE = "000037/2026/09/23/gxbdt1a3e04qxc5ooa9llndgqzd4swa5"
REAL_SHAPE_EXPECTED_URL = f"{IMAGE_BASE_URL}/{REAL_SHAPE_REFERENCE}.jpg"


def _spot(index: int = 0, fixture: str = "spotteron_page_1.json") -> dict:
    return load_fixture(fixture)["data"][index]


def _real_shape_spot(index: int = 0) -> dict:
    return load_fixture("spotteron_real_shape.json")["data"][index]


# --- ImageUrlResolver: the six required scenarios ---


@responses.activate
def test_successful_image_reference_resolution():
    responses.add(responses.HEAD, REAL_SHAPE_EXPECTED_URL, status=200, content_type="image/jpeg")

    resolver = ImageUrlResolver(image_base_url=IMAGE_BASE_URL)
    resolved = resolver.resolve(_real_shape_spot(0), observation_id="2001")

    assert resolved == REAL_SHAPE_EXPECTED_URL


@responses.activate
def test_direct_full_url_resolution_bypasses_image_base_url():
    spot = _spot(0)  # spotteron_page_1.json: attributes.image_url is already a full URL
    direct_url = spot["attributes"]["image_url"]
    responses.add(responses.HEAD, direct_url, status=200, content_type="image/jpeg")

    resolver = ImageUrlResolver(image_base_url=IMAGE_BASE_URL)
    resolved = resolver.resolve(spot, observation_id="1001")

    assert resolved == direct_url


@responses.activate
def test_404_response_raises_with_structured_detail():
    responses.add(responses.HEAD, REAL_SHAPE_EXPECTED_URL, status=404)

    resolver = ImageUrlResolver(image_base_url=IMAGE_BASE_URL)
    with pytest.raises(ImageUrlResolutionError) as excinfo:
        resolver.resolve(_real_shape_spot(0), observation_id="2001")

    error = excinfo.value
    assert error.observation_id == "2001"
    assert error.image_reference == REAL_SHAPE_REFERENCE
    assert error.attempted_url == REAL_SHAPE_EXPECTED_URL
    assert error.http_status == 404


@responses.activate
def test_non_image_content_type_raises():
    responses.add(responses.HEAD, REAL_SHAPE_EXPECTED_URL, status=200, content_type="text/html")

    resolver = ImageUrlResolver(image_base_url=IMAGE_BASE_URL)
    with pytest.raises(ImageUrlResolutionError, match="non-image content-type"):
        resolver.resolve(_real_shape_spot(0), observation_id="2001")


def test_missing_image_reference_raises_without_any_http_call():
    no_image_spot = load_fixture("spotteron_no_image.json")["data"][0]
    resolver = ImageUrlResolver(image_base_url=IMAGE_BASE_URL)
    # Deliberately no @responses.activate / no mock registered: if the
    # resolver tried an HTTP call with nothing to resolve, it would
    # raise a connection error here instead of the expected clean
    # ImageUrlResolutionError.
    with pytest.raises(ImageUrlResolutionError) as excinfo:
        resolver.resolve(no_image_spot, observation_id="2001")

    assert excinfo.value.observation_id == "2001"
    assert excinfo.value.image_reference is None
    assert excinfo.value.attempted_url is None
    assert excinfo.value.http_status is None


def test_malformed_response_raises_without_guessing():
    malformed_spot = {"error": "not a real spot record"}
    resolver = ImageUrlResolver(image_base_url=IMAGE_BASE_URL)
    with pytest.raises(ImageUrlResolutionError):
        resolver.resolve(malformed_spot, observation_id="9999")


@responses.activate
def test_falls_back_to_get_when_head_is_not_supported():
    responses.add(responses.HEAD, REAL_SHAPE_EXPECTED_URL, status=405)
    responses.add(responses.GET, REAL_SHAPE_EXPECTED_URL, status=200, content_type="image/jpeg", body=b"jpeg-bytes")

    resolver = ImageUrlResolver(image_base_url=IMAGE_BASE_URL)
    resolved = resolver.resolve(_real_shape_spot(0), observation_id="2001")

    assert resolved == REAL_SHAPE_EXPECTED_URL


@responses.activate
def test_bearer_token_sent_as_authorization_header():
    def _require_auth_header(request):
        assert request.headers.get("Authorization") == "Bearer secret-token"
        return (200, {"Content-Type": "image/jpeg"}, b"")

    responses.add_callback(responses.HEAD, REAL_SHAPE_EXPECTED_URL, callback=_require_auth_header)

    resolver = ImageUrlResolver(image_base_url=IMAGE_BASE_URL, bearer_token="secret-token")
    resolver.resolve(_real_shape_spot(0), observation_id="2001")


def test_peek_image_reference_or_url_makes_no_http_call():
    # No @responses.activate: proves this helper is purely local.
    assert peek_image_reference_or_url(_real_shape_spot(0)) == REAL_SHAPE_REFERENCE
    assert peek_image_reference_or_url(_spot(0)) == "https://cdn.example-spotteron.test/images/1001.jpg"
    assert peek_image_reference_or_url(load_fixture("spotteron_no_image.json")["data"][0]) is None


# --- Other field resolvers (unchanged pure functions) ---


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

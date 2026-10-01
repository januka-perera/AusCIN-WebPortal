"""derive_site_coordinates: one site coordinate from image-bearing observations.

Pure-function tests — no network, no files.
"""

from __future__ import annotations

import math
from typing import Optional

import pytest

from coastsnap_import import cli
from coastsnap_import.image_resolver import (
    SITE_COORDINATE_TOLERANCE_METRES,
    SiteCoordinates,
    derive_site_coordinates,
)
from coastsnap_import.models import CoordinateStatus, SourceObservation
from coastsnap_import.spotteron_client import filter_by_root_id
from tests.conftest import load_fixture

LAT = -26.681912
LON = 153.137469
METRES_PER_DEGREE_LATITUDE = 6_371_008.8 * math.pi / 180


def _obs(
    observation_id: str,
    latitude: Optional[float],
    longitude: Optional[float],
    *,
    media_reference: Optional[str] = "000037/2026/09/23/ref",
    image_url: Optional[str] = None,
) -> SourceObservation:
    return SourceObservation(
        observation_id=observation_id,
        root_id="487447",
        latitude=latitude,
        longitude=longitude,
        media_reference=media_reference,
        image_url=image_url,
    )


def test_single_image_bearing_observation_is_confirmed():
    result = derive_site_coordinates([_obs("1", LAT, LON)])

    assert result == SiteCoordinates(
        status=CoordinateStatus.CONFIRMED, latitude=LAT, longitude=LON, observation_count=1
    )


def test_resolved_image_url_alone_counts_as_image_bearing():
    result = derive_site_coordinates([_obs("1", LAT, LON, media_reference=None, image_url="https://x.test/1.jpg")])

    assert result.status is CoordinateStatus.CONFIRMED


def test_identical_coordinates_are_confirmed_at_that_coordinate():
    result = derive_site_coordinates([_obs(str(i), LAT, LON) for i in range(4)])

    assert result.status is CoordinateStatus.CONFIRMED
    assert result.latitude == pytest.approx(LAT, abs=1e-12)
    assert result.longitude == pytest.approx(LON, abs=1e-12)
    assert result.observation_count == 4
    assert result.error is None


def test_small_variation_within_tolerance_is_confirmed_at_the_mean():
    # ~33 m apart: ordinary phone GPS scatter around one camera mount.
    result = derive_site_coordinates([_obs("1", LAT, LON), _obs("2", LAT + 0.0003, LON + 0.0002)])

    assert result.status is CoordinateStatus.CONFIRMED
    assert result.latitude == pytest.approx(LAT + 0.00015)
    assert result.longitude == pytest.approx(LON + 0.0001)


def test_tolerance_is_distance_from_the_mean():
    def two_points_apart(metres: float) -> SiteCoordinates:
        offset = metres / METRES_PER_DEGREE_LATITUDE
        return derive_site_coordinates([_obs("1", LAT, LON), _obs("2", LAT + offset, LON)])

    # Each point lies half the separation from the mean.
    assert two_points_apart(2 * SITE_COORDINATE_TOLERANCE_METRES - 10).status is CoordinateStatus.CONFIRMED
    assert two_points_apart(2 * SITE_COORDINATE_TOLERANCE_METRES + 10).status is CoordinateStatus.INCONSISTENT


def test_disagreement_beyond_tolerance_is_inconsistent_with_no_coordinate():
    # ~1.1 km apart: not one camera mount.
    result = derive_site_coordinates([_obs("1", LAT, LON), _obs("2", LAT + 0.01, LON)])

    assert result.status is CoordinateStatus.INCONSISTENT
    assert result.latitude is None and result.longitude is None
    assert result.observation_count == 2
    assert "tolerance" in (result.error or "")


def test_one_outlier_among_agreeing_observations_is_inconsistent():
    observations = [_obs(str(i), LAT, LON) for i in range(10)] + [_obs("far", LAT + 0.05, LON)]

    assert derive_site_coordinates(observations).status is CoordinateStatus.INCONSISTENT


def test_no_observations_is_missing():
    result = derive_site_coordinates([])

    assert result.status is CoordinateStatus.MISSING
    assert result.latitude is None and result.longitude is None
    assert result.observation_count == 0


@pytest.mark.parametrize("latitude, longitude", [(None, None), (LAT, None), (None, LON)])
def test_missing_coordinates_are_missing(latitude, longitude):
    result = derive_site_coordinates([_obs("1", latitude, longitude)])

    assert result.status is CoordinateStatus.MISSING
    assert result.error


@pytest.mark.parametrize(
    "latitude, longitude",
    [
        (math.nan, LON),
        (LAT, math.inf),
        (-math.inf, LON),
        (90.0001, LON),
        (-91.0, LON),
        (LAT, 180.5),
        (LAT, -181.0),
        (0.0, 0.0),
    ],
)
def test_non_finite_out_of_range_and_null_island_are_invalid(latitude, longitude):
    result = derive_site_coordinates([_obs("1", latitude, longitude)])

    assert result.status is CoordinateStatus.INVALID
    assert result.latitude is None and result.longitude is None
    assert result.observation_count == 0


def test_range_boundaries_are_valid():
    assert derive_site_coordinates([_obs("1", -90.0, 180.0)]).status is CoordinateStatus.CONFIRMED
    # Zero on one axis is a real place; only exactly 0,0 is rejected.
    assert derive_site_coordinates([_obs("1", 0.0, LON)]).status is CoordinateStatus.CONFIRMED


def test_invalid_coordinates_are_ignored_when_valid_ones_exist():
    result = derive_site_coordinates([_obs("1", LAT, LON), _obs("2", 0.0, 0.0), _obs("3", math.nan, LON)])

    assert result.status is CoordinateStatus.CONFIRMED
    assert result.latitude == LAT
    assert result.observation_count == 1


def test_observations_without_an_image_reference_are_ignored():
    no_image_far_away = _obs("2", LAT + 1.0, LON, media_reference=None, image_url=None)
    blank_reference = _obs("3", LAT - 1.0, LON, media_reference="", image_url="")

    result = derive_site_coordinates([_obs("1", LAT, LON), no_image_far_away, blank_reference])

    assert result.status is CoordinateStatus.CONFIRMED
    assert result.observation_count == 1


def test_only_observations_without_images_is_missing():
    result = derive_site_coordinates([_obs("1", LAT, LON, media_reference=None)])

    assert result.status is CoordinateStatus.MISSING


def test_result_is_independent_of_observation_order():
    observations = [
        _obs("1", LAT, LON),
        _obs("2", LAT + 0.00011, LON - 0.00007),
        _obs("3", LAT - 0.00023, LON + 0.00031),
        _obs("4", LAT + 0.00002, LON + 0.00013),
    ]

    forward = derive_site_coordinates(observations)
    reverse = derive_site_coordinates(list(reversed(observations)))
    rotated = derive_site_coordinates(observations[2:] + observations[:2])

    assert forward.status is CoordinateStatus.CONFIRMED
    assert forward == reverse == rotated


def test_confirmed_shape_from_live_response_fixture():
    """attributes.latitude/attributes.longitude, as in the captured live v2.4 response."""
    page = load_fixture("spotteron_live_shape_page.json")["data"]
    observations = [cli._parse_observation(spot, "487447", "UTC") for spot in filter_by_root_id(page, "487447")]

    result = derive_site_coordinates(observations)

    assert result == SiteCoordinates(
        status=CoordinateStatus.CONFIRMED, latitude=-26.681912, longitude=153.137469, observation_count=1
    )


def test_two_different_sites_in_one_set_are_inconsistent():
    """The fixture's second spot is another CoastSnap site (~800 km away). Mixed
    together, they must never be averaged into a location that is neither."""
    page = load_fixture("spotteron_live_shape_page.json")["data"]
    observations = [cli._parse_observation(spot, "487447", "UTC") for spot in page]

    assert derive_site_coordinates(observations).status is CoordinateStatus.INCONSISTENT

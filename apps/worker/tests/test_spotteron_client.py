from __future__ import annotations

from datetime import datetime, timezone

import pytest
import responses

from coastsnap_import.spotteron_client import (
    SpotteronClient,
    SpotteronClientOptions,
    SpotteronRequestError,
    SpotteronResponseError,
    extract_root_id,
    extract_spotted_at_utc,
    filter_by_root_id,
    filter_by_spotted_at,
)
from tests.conftest import load_fixture

BASE_URL = "https://example-spotteron.test"
SPOTS_URL = f"{BASE_URL}/api/v2.4/spots"


def _client(bearer_token=None) -> SpotteronClient:
    return SpotteronClient(
        SpotteronClientOptions(base_url=BASE_URL, api_version="v2.4", bearer_token=bearer_token, max_retries=2, retry_backoff_seconds=0)
    )


@responses.activate
def test_pagination_stops_on_short_page():
    page1 = load_fixture("spotteron_page_1.json")  # 2 items
    page2 = load_fixture("spotteron_page_2.json")  # 1 item < limit
    responses.add(responses.GET, SPOTS_URL, json=page1, status=200)
    responses.add(responses.GET, SPOTS_URL, json=page2, status=200)

    spots = list(_client().iter_spots(topic_id=37, root_id="37", page_limit=2))

    assert [s["id"] for s in spots] == ["1001", "1002", "1003"]
    assert len(responses.calls) == 2


@responses.activate
def test_pagination_stops_on_empty_page():
    page1 = load_fixture("spotteron_page_1.json")
    responses.add(responses.GET, SPOTS_URL, json=page1, status=200)
    responses.add(responses.GET, SPOTS_URL, json={"data": []}, status=200)

    spots = list(_client().iter_spots(topic_id=37, root_id="37", page_limit=2))

    assert len(spots) == 2
    assert len(responses.calls) == 2


@responses.activate
def test_query_params_include_topic_id_root_id_limit_page():
    responses.add(responses.GET, SPOTS_URL, json={"data": []}, status=200)
    list(_client().iter_spots(topic_id=37, root_id="487447", page_limit=10))
    request = responses.calls[0].request
    assert "filter%5Btopic_id%5D=37" in request.url
    # filter[root_id] is required, not optional — a bare root_id=... param
    # was confirmed against the real API to NOT filter server-side.
    assert "filter%5Broot_id%5D=487447" in request.url
    assert "limit=10" in request.url
    assert "page=1" in request.url


@responses.activate
def test_no_authorization_header_when_no_token():
    responses.add(responses.GET, SPOTS_URL, json={"data": []}, status=200)
    list(_client(bearer_token=None).iter_spots(topic_id=37, root_id="37", page_limit=10))
    assert "Authorization" not in responses.calls[0].request.headers


@responses.activate
def test_authorization_header_present_when_token_configured():
    responses.add(responses.GET, SPOTS_URL, json={"data": []}, status=200)
    list(_client(bearer_token="my-token").iter_spots(topic_id=37, root_id="37", page_limit=10))
    assert responses.calls[0].request.headers["Authorization"] == "Bearer my-token"


@responses.activate
def test_malformed_response_raises():
    malformed = load_fixture("spotteron_malformed.json")
    responses.add(responses.GET, SPOTS_URL, json=malformed, status=200)
    with pytest.raises(SpotteronResponseError):
        list(_client().iter_spots(topic_id=37, root_id="37", page_limit=10))


@responses.activate
def test_retries_on_retryable_status_then_succeeds():
    responses.add(responses.GET, SPOTS_URL, status=503)
    responses.add(responses.GET, SPOTS_URL, json={"data": []}, status=200)
    result = list(_client().iter_spots(topic_id=37, root_id="37", page_limit=10))
    assert result == []
    assert len(responses.calls) == 2


@responses.activate
def test_non_retryable_status_raises_immediately():
    responses.add(responses.GET, SPOTS_URL, status=404, body="not found")
    with pytest.raises(SpotteronRequestError):
        list(_client().iter_spots(topic_id=37, root_id="37", page_limit=10))
    assert len(responses.calls) == 1


def test_extract_spotted_at_parses_utc():
    value = extract_spotted_at_utc({"attributes": {"spotted_at": "2026-08-01T02:15:00Z"}})
    assert value == datetime(2026, 8, 1, 2, 15, tzinfo=timezone.utc)


def test_extract_spotted_at_missing_returns_none():
    assert extract_spotted_at_utc({"attributes": {}}) is None
    assert extract_spotted_at_utc({}) is None


def test_extract_spotted_at_unparseable_returns_none():
    assert extract_spotted_at_utc({"attributes": {"spotted_at": "not-a-date"}}) is None


def test_filter_by_spotted_at_excludes_out_of_range_and_missing():
    spots = load_fixture("spotteron_page_1.json")["data"] + load_fixture("spotteron_page_2.json")["data"]
    spots.append({"id": "9999", "attributes": {}})  # no spotted_at at all

    date_from = datetime(2026, 8, 1, tzinfo=timezone.utc)
    date_to = datetime(2026, 8, 31, 23, 59, 59, tzinfo=timezone.utc)
    result = list(filter_by_spotted_at(spots, date_from, date_to))

    assert [s["id"] for s in result] == ["1001", "1002"]  # 1003 is in September; 9999 has no date


def test_extract_spotted_at_parses_real_space_separated_format_no_timezone():
    # Confirmed real shape (2026-09-23): "YYYY-MM-DD HH:MM:SS", no "T", no timezone marker.
    # Default source_timezone is "UTC" — see the "Timestamp interpretation policy" docstring.
    value = extract_spotted_at_utc({"attributes": {"spotted_at": "2026-09-23 14:57:28"}})
    assert value == datetime(2026, 9, 23, 14, 57, 28, tzinfo=timezone.utc)


def test_extract_spotted_at_timezone_less_uses_default_utc_explicitly():
    # Same as above, but spelled out explicitly rather than relying on the default parameter.
    value = extract_spotted_at_utc({"attributes": {"spotted_at": "2026-09-23 14:57:28"}}, source_timezone="UTC")
    assert value == datetime(2026, 9, 23, 14, 57, 28, tzinfo=timezone.utc)


def test_extract_spotted_at_timezone_less_applies_configured_source_timezone():
    # Brisbane is UTC+10 year-round (no DST) — a deterministic, easy-to-verify offset.
    value = extract_spotted_at_utc(
        {"attributes": {"spotted_at": "2026-09-23 14:57:28"}}, source_timezone="Australia/Brisbane"
    )
    assert value == datetime(2026, 9, 23, 4, 57, 28, tzinfo=timezone.utc)


def test_extract_spotted_at_with_explicit_utc_offset_ignores_configured_source_timezone():
    # A string that already carries an explicit offset/Z is trusted directly;
    # source_timezone must NOT be applied on top of it.
    value = extract_spotted_at_utc(
        {"attributes": {"spotted_at": "2026-09-23T14:57:28Z"}}, source_timezone="Australia/Brisbane"
    )
    assert value == datetime(2026, 9, 23, 14, 57, 28, tzinfo=timezone.utc)

    value_with_offset = extract_spotted_at_utc(
        {"attributes": {"spotted_at": "2026-09-23T14:57:28+05:00"}}, source_timezone="Australia/Brisbane"
    )
    assert value_with_offset == datetime(2026, 9, 23, 9, 57, 28, tzinfo=timezone.utc)


def test_extract_spotted_at_invalid_configured_timezone_returns_none_not_a_crash():
    value = extract_spotted_at_utc(
        {"attributes": {"spotted_at": "2026-09-23 14:57:28"}}, source_timezone="Not/A_Real_Zone"
    )
    assert value is None


def test_extract_spotted_at_raw_preserves_original_string_unconverted():
    from coastsnap_import.spotteron_client import extract_spotted_at_raw

    assert extract_spotted_at_raw({"attributes": {"spotted_at": "2026-09-23 14:57:28"}}) == "2026-09-23 14:57:28"
    assert extract_spotted_at_raw({"attributes": {}}) is None
    assert extract_spotted_at_raw({}) is None


def test_filter_by_spotted_at_date_range_boundaries_with_source_timezone():
    # A spot at 2026-09-23 23:30:00 Brisbane time (UTC+10) is
    # 2026-09-23T13:30:00Z — just inside a UTC boundary that would
    # otherwise exclude it if the timezone were (wrongly) ignored.
    spots = [
        {"id": "in-range", "attributes": {"spotted_at": "2026-09-23 23:30:00"}},  # -> 2026-09-23T13:30:00Z
        {"id": "just-before", "attributes": {"spotted_at": "2026-09-23 09:59:59"}},  # -> 2026-09-22T23:59:59Z
        {"id": "just-after", "attributes": {"spotted_at": "2026-09-24 10:00:01"}},  # -> 2026-09-24T00:00:01Z
    ]
    date_from = datetime(2026, 9, 23, 0, 0, 0, tzinfo=timezone.utc)
    date_to = datetime(2026, 9, 24, 0, 0, 0, tzinfo=timezone.utc)

    result = list(filter_by_spotted_at(spots, date_from, date_to, source_timezone="Australia/Brisbane"))

    assert [s["id"] for s in result] == ["in-range"]


def test_extract_root_id_reads_attributes_root_id():
    assert extract_root_id({"attributes": {"root_id": 487447}}) == "487447"
    assert extract_root_id({"attributes": {"root_id": "487447"}}) == "487447"


def test_extract_root_id_missing_returns_none():
    assert extract_root_id({"attributes": {}}) is None
    assert extract_root_id({}) is None


def test_filter_by_root_id_excludes_other_sites_and_missing():
    # Confirmed against a real response: topic_id=37 alone spans every
    # CoastSnap site globally, so this filter is load-bearing, not optional.
    spots = [
        {"id": "a", "attributes": {"root_id": 487447}},
        {"id": "b", "attributes": {"root_id": 1085047}},  # a different, real site
        {"id": "c", "attributes": {"root_id": "487447"}},  # same site, string form
        {"id": "d", "attributes": {}},  # no root_id at all
    ]
    result = list(filter_by_root_id(spots, "487447"))
    assert [s["id"] for s in result] == ["a", "c"]

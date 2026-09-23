"""Spotteron API v2.4 client.

Confirmed by the project owner: API version "v2.4", filtering by
``topic_id`` (default 37), ``limit``/``page`` pagination, and a
``spotted_at`` field used for (client-side) date filtering, plus
optional bearer-token auth on top of public GET access.

UNCONFIRMED (marked throughout, not invented):
    - The exact response envelope shape. This client assumes a
      JSON:API-ish shape (``{"data": [...]}``) because the existing
      ``tools/check_spotteron_public_download.py`` script already
      demonstrates a JSON:API-style query convention
      (``filter[topic_id]=37&limit=1&page=1``) against a real
      Spotteron URL — that script is prior art already in this repo,
      not something invented here. If the real response differs,
      ``_extract_spots`` is the single place to fix.
    - The exact field names for a spot's attributes (lat/lon, image
      URL, contributor name/consent) beyond ``spotted_at``. See
      image_resolver.py for how those are resolved defensively.
    - Whether the server honours a date-range filter at all. This
      client does NOT rely on one — see filter_by_spotted_at() — it
      always re-filters client-side, per the explicit scope item
      "client-side filtering by spotted_at".

Pagination termination does not depend on the unconfirmed envelope
shape: it stops as soon as a page returns fewer items than the
requested limit (or a page with zero items), which is correct
regardless of whether ``meta``/``links`` are present.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Iterator, Optional

import requests


class SpotteronClientError(Exception):
    """Base class for all Spotteron client failures."""


class SpotteronRequestError(SpotteronClientError):
    """A request failed after retries (network error or non-2xx status)."""


class SpotteronResponseError(SpotteronClientError):
    """The response body did not match the shape this client expects."""


RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class SpotteronClientOptions:
    base_url: str
    api_version: str
    bearer_token: Optional[str] = None
    timeout_seconds: float = 30.0
    max_retries: int = 3
    retry_backoff_seconds: float = 1.0


class SpotteronClient:
    """Thin, defensive wrapper around the Spotteron ``/spots`` list endpoint.

    Endpoint path assumed: ``{base_url}/api/{api_version}/spots`` with
    query params ``filter[topic_id]``, ``limit``, ``page`` — based on
    the confirmed v2.4/topic_id/limit/page scope and the existing
    ``tools/check_spotteron_public_download.py`` prior art. The exact
    path segment is UNCONFIRMED beyond that; if wrong, only
    ``_spots_url`` needs to change.
    """

    def __init__(self, options: SpotteronClientOptions, session: Optional[requests.Session] = None):
        self._options = options
        self._session = session or requests.Session()

    def _spots_url(self) -> str:
        return f"{self._options.base_url}/api/{self._options.api_version}/spots"

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._options.bearer_token:
            headers["Authorization"] = f"Bearer {self._options.bearer_token}"
        return headers

    def _get_page(self, topic_id: int, page: int, limit: int) -> dict[str, Any]:
        params = {"filter[topic_id]": topic_id, "limit": limit, "page": page}
        last_error: Optional[Exception] = None
        for attempt in range(1, self._options.max_retries + 1):
            try:
                response = self._session.get(
                    self._spots_url(),
                    params=params,
                    headers=self._headers(),
                    timeout=self._options.timeout_seconds,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self._options.max_retries:
                    time.sleep(self._options.retry_backoff_seconds * attempt)
                    continue
                raise SpotteronRequestError(
                    f"Request to {self._spots_url()} failed after {attempt} attempts: {exc}"
                ) from exc

            if response.status_code == 200:
                try:
                    return response.json()
                except ValueError as exc:
                    raise SpotteronResponseError(
                        f"Response from {self._spots_url()} (page={page}) was not valid JSON."
                    ) from exc

            if response.status_code in RETRYABLE_STATUS_CODES and attempt < self._options.max_retries:
                time.sleep(self._options.retry_backoff_seconds * attempt)
                continue

            raise SpotteronRequestError(
                f"Spotteron returned HTTP {response.status_code} for page={page}: "
                f"{response.text[:500]!r}"
            )

        # Unreachable in practice (loop always returns or raises), but keeps type checkers happy.
        raise SpotteronRequestError(f"Request failed: {last_error}")

    @staticmethod
    def _extract_spots(payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Extracts the list of raw spot records from one page's response.

        UNCONFIRMED envelope shape — see module docstring. Accepts
        either a JSON:API-style ``{"data": [...]}`` envelope or a bare
        list, and raises SpotteronResponseError for anything else
        rather than guessing further.
        """
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and isinstance(payload.get("data"), list):
            return payload["data"]
        raise SpotteronResponseError(
            "Unrecognised Spotteron response shape: expected a list or a dict with a "
            f"list 'data' key, got keys={list(payload.keys()) if isinstance(payload, dict) else type(payload)!r}"
        )

    def iter_spots(self, topic_id: int, page_limit: int) -> Iterator[dict[str, Any]]:
        """Yields raw spot dicts across all pages for ``topic_id``, oldest pagination order as returned by the API."""
        page = 1
        while True:
            payload = self._get_page(topic_id, page, page_limit)
            spots = self._extract_spots(payload)
            if not spots:
                return
            yield from spots
            if len(spots) < page_limit:
                return  # short page => last page, regardless of any meta/links shape
            page += 1


def extract_spotted_at_utc(raw_spot: dict[str, Any]) -> Optional[datetime]:
    """Reads the confirmed ``spotted_at`` field (top-level or, if the
    envelope turns out to be JSON:API-nested, under ``attributes``) and
    parses it as UTC. Returns None (rather than guessing) if absent or
    unparseable — such spots are excluded by filter_by_spotted_at,
    never silently included.
    """
    raw_value = raw_spot.get("spotted_at")
    if raw_value is None and isinstance(raw_spot.get("attributes"), dict):
        raw_value = raw_spot["attributes"].get("spotted_at")
    if not isinstance(raw_value, str):
        return None
    try:
        value = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def filter_by_spotted_at(
    spots: Iterable[dict[str, Any]], date_from_utc: datetime, date_to_utc: datetime
) -> Iterator[dict[str, Any]]:
    """Client-side date filtering, applied regardless of whether the server also filtered."""
    for spot in spots:
        spotted_at = extract_spotted_at_utc(spot)
        if spotted_at is None:
            continue
        if date_from_utc <= spotted_at <= date_to_utc:
            yield spot

"""Spotteron API v2.4 client.

Confirmed against a REAL, live response (2026-09-23, GET
https://www.spotteron.com/api/v2.4/spots?filter[topic_id]=37&limit=1&page=1,
metadata only, no image downloaded):

    - Envelope shape: ``{"data": [...], "meta": {"page_count": ..., "total": ...}}``.
    - Each item is ``{"id": <int>, "attributes": {...}}`` (no ``type`` key,
      unlike this project's earlier synthetic fixtures).
    - ``attributes.root_id`` is a real, present field (a JSON number) —
      and critically, ``topic_id=37`` ALONE spans every CoastSnap site
      globally (139,181 total spots across every ``root_id`` at the time
      of this check). A single-site importer MUST also filter by
      ``root_id``, both server-side (``filter[root_id]``, confirmed to
      work: narrowed 139,181 -> 1,129 for one real root_id) and
      client-side (``filter_by_root_id`` below) — the same
      defense-in-depth pattern already used for ``spotted_at``, since a
      bare ``root_id=...`` query param without the ``filter[]`` wrapper
      was confirmed to silently NOT filter.
    - ``attributes.spotted_at`` is ``"YYYY-MM-DD HH:MM:SS"`` (a space
      separator, no "T", no timezone marker at all) — NOT a "Z"-suffixed
      ISO-8601 string as earlier synthetic fixtures assumed.
      ``datetime.fromisoformat`` (Python 3.11+) parses this correctly as
      a naive datetime; this client then assumes it is already UTC (see
      extract_spotted_at_utc) — the server's actual timezone convention
      is NOT independently confirmed, only that this assumption is what
      this codebase applies, per AGENTS.md's "use UTC internally" rule.
    - ``attributes.image`` is an opaque reference (see image_resolver.py),
      not a URL — confirmed separately.

STILL UNCONFIRMED (marked throughout, not invented):
    - A stable "site name" field. The real response includes fields
      such as ``fld_01_00001214`` holding a human-readable site label
      (e.g. "CoastSnap Buddina (Australia)") — but ``fld_NN_NNNNNNNN``
      keys are Spotteron's dynamic per-deployment custom-field IDs, not
      a documented, stable API contract, and will differ across sites/
      topics. This client deliberately does NOT read them: guessing a
      dynamic field ID would be exactly the kind of invented API detail
      this project avoids. ``SourceSite.name`` stays ``None`` until a
      confirmed, stable field is identified.
    - The exact field names for contributor name/attribution-consent.
      See image_resolver.py for how those are resolved defensively.

Pagination termination does not depend on the envelope's optional
``meta`` block: it stops as soon as a page returns fewer items than the
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

    def _get_page(self, topic_id: int, root_id: str, page: int, limit: int) -> dict[str, Any]:
        # filter[root_id] is required, not optional: a bare root_id=...
        # param (without the filter[] wrapper) was confirmed NOT to
        # filter server-side — see module docstring.
        params = {"filter[topic_id]": topic_id, "filter[root_id]": root_id, "limit": limit, "page": page}
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

        Confirmed envelope shape — see module docstring — is
        ``{"data": [...], "meta": {...}}``. A bare list is also accepted
        defensively; anything else raises SpotteronResponseError rather
        than guessing further.
        """
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and isinstance(payload.get("data"), list):
            return payload["data"]
        raise SpotteronResponseError(
            "Unrecognised Spotteron response shape: expected a list or a dict with a "
            f"list 'data' key, got keys={list(payload.keys()) if isinstance(payload, dict) else type(payload)!r}"
        )

    def iter_spots(self, topic_id: int, root_id: str, page_limit: int) -> Iterator[dict[str, Any]]:
        """Yields raw spot dicts across all pages for ``topic_id`` AND
        ``root_id`` (both sent as server-side ``filter[...]`` params —
        see module docstring for why ``root_id`` is not optional),
        oldest pagination order as returned by the API."""
        page = 1
        while True:
            payload = self._get_page(topic_id, root_id, page, page_limit)
            spots = self._extract_spots(payload)
            if not spots:
                return
            yield from spots
            if len(spots) < page_limit:
                return  # short page => last page, regardless of any meta/links shape
            page += 1


def extract_root_id(raw_spot: dict[str, Any]) -> Optional[str]:
    """Reads the confirmed ``attributes.root_id`` field (falling back to
    a top-level ``root_id`` in case the envelope shape varies) and
    returns it as a string, since Spotteron returns it as a JSON
    number. None if absent — such records are excluded by
    filter_by_root_id, never silently assumed to match.
    """
    raw_value = raw_spot.get("root_id")
    if raw_value is None and isinstance(raw_spot.get("attributes"), dict):
        raw_value = raw_spot["attributes"].get("root_id")
    if raw_value is None:
        return None
    return str(raw_value)


def filter_by_root_id(spots: Iterable[dict[str, Any]], root_id: str) -> Iterator[dict[str, Any]]:
    """Client-side site filtering, applied regardless of whether the
    server's ``filter[root_id]`` parameter actually took effect.

    Confirmed against a real Spotteron v2.4 response that ``topic_id=37``
    alone spans every CoastSnap site globally (139,181 spots across every
    root_id at the time of checking) — so this is not optional the way
    filter_by_spotted_at's server-side counterpart might arguably be;
    without it, a "single-site" run would silently ingest observations
    from other sites entirely.
    """
    root_id_str = str(root_id)
    for spot in spots:
        if extract_root_id(spot) == root_id_str:
            yield spot


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

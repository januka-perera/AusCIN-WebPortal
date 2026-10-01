"""Resolves and validates the Level 0 original image URL from a raw
Spotteron spot record, plus a few other fields whose exact JSON path
is still unconfirmed (latitude/longitude, contributor name,
attribution permission).

CONFIRMED, from a real Spotteron v2.4 response supplied by the project
owner: ``attributes.image`` is not a URL — it is an opaque reference,
e.g.::

    "000037/2026/09/23/gxbdt1a3e04qxc5ooa9llndgqzd4swa5"

This same value is Spotteron's own "media reference" for the image —
it is preserved exactly (never discarded once resolved) as both:

    - ``ImageResolution.image_reference``, returned alongside the
      resolved URL by ``ImageUrlResolver.resolve()``;
    - ``resolve_media_reference()``'s primary candidate, for callers
      that need the reference before/without resolving a URL (e.g.
      ``--plan-only``, or parsing an observation before its image URL
      has been validated).

The single candidate download URL is built as::

    {image_base_url}/{image_reference}.jpg

with ``image_base_url`` defaulting to
"https://files.spotteron.com/images/spots" and configurable via
``SPOTTERON_IMAGE_BASE_URL`` (see config.py). This module does not
guess among several URL *formats* — exactly one candidate is built
(or used directly, if a field already contains a full URL — kept as a
forward-compatible path for if the API later returns one; in that case
there is no separate reference to preserve, so ``image_reference`` is
``None``) — and that one candidate is validated with a real HTTP
request (HEAD, falling back to a streamed GET whose body is never
read) before being accepted. A failed validation raises
``ImageUrlResolutionError`` carrying the observation ID, the image
reference, the attempted URL and the HTTP status, so a failure is
diagnosable without re-running anything.

CONFIRMED against the real live response (see
spotteron_client.py): per-spot ``attributes.latitude`` and
``attributes.longitude`` as JSON numbers. The other latitude/longitude
candidates below remain unconfirmed fallbacks. ``derive_site_coordinates``
turns these per-spot values into one site coordinate; nothing here
infers a location from filenames, pixels or geocoding.

UNCONFIRMED: contributor name and attribution-permission field names.
Each is tried as an ordered list of candidate JSON paths; absence never
becomes a guess.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Optional

import requests

from .models import CoordinateStatus, SourceObservation

_DIRECT_URL_CANDIDATES: tuple[tuple[str, ...], ...] = (
    ("attributes", "image_url"),
    ("attributes", "photo_url"),
    ("image_url",),
    ("photo_url",),
)

# Confirmed real field (see module docstring). "photo" is an
# unconfirmed, lower-priority fallback only.
_IMAGE_REFERENCE_CANDIDATES: tuple[tuple[str, ...], ...] = (
    ("attributes", "image"),
    ("attributes", "photo"),
)

_MEDIA_REFERENCE_CANDIDATES: tuple[tuple[str, ...], ...] = (
    ("attributes", "image"),  # confirmed real field — same opaque reference used to build the Level 0 URL
    ("attributes", "image_id"),
    ("attributes", "media_id"),
    ("attributes", "photo_id"),
)

_LATITUDE_CANDIDATES: tuple[tuple[str, ...], ...] = (
    ("attributes", "latitude"),
    ("attributes", "lat"),
    ("latitude",),
)

_LONGITUDE_CANDIDATES: tuple[tuple[str, ...], ...] = (
    ("attributes", "longitude"),
    ("attributes", "lng"),
    ("attributes", "lon"),
    ("longitude",),
)

_CONTRIBUTOR_NAME_CANDIDATES: tuple[tuple[str, ...], ...] = (
    ("attributes", "contributor_name"),
    ("attributes", "user_name"),
    ("attributes", "nickname"),
    ("attributes", "author"),
)

# Conservative by design: attribution is only ever considered "permitted"
# if one of these candidate fields exists AND is truthy. Absence always
# means False, never guessed True — see AGENTS.md "never expose private
# contributor information" and this project's explicit "attribution only
# when permitted" requirement.
_ATTRIBUTION_PERMITTED_CANDIDATES: tuple[tuple[str, ...], ...] = (
    ("attributes", "attribution_permitted"),
    ("attributes", "public_attribution"),
    ("attributes", "consent_to_credit"),
)


class ImageUrlResolutionError(Exception):
    """Raised when no field yields a usable Level 0 image, or the one
    candidate URL fails validation. Always carries enough structured
    detail to diagnose without re-running anything."""

    def __init__(
        self,
        *,
        observation_id: str,
        image_reference: Optional[str],
        attempted_url: Optional[str],
        http_status: Optional[int],
        reason: str,
    ):
        self.observation_id = observation_id
        self.image_reference = image_reference
        self.attempted_url = attempted_url
        self.http_status = http_status
        self.reason = reason
        super().__init__(
            f"Could not resolve a usable Level 0 image for observation_id={observation_id!r}: "
            f"image_reference={image_reference!r} attempted_url={attempted_url!r} "
            f"http_status={http_status!r} reason={reason}"
        )


def _dig(raw: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = raw
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def _first_string_match(raw_spot: dict[str, Any], candidates: tuple[tuple[str, ...], ...]) -> Optional[str]:
    for path in candidates:
        value = _dig(raw_spot, path)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _first_float_match(raw_spot: dict[str, Any], candidates: tuple[tuple[str, ...], ...]) -> Optional[float]:
    for path in candidates:
        value = _dig(raw_spot, path)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return None


def peek_image_reference_or_url(raw_spot: dict[str, Any]) -> Optional[str]:
    """A non-validating peek at what *would* be used to build the Level 0
    URL — makes no HTTP request. Used only for --plan-only output."""
    direct_url = _first_string_match(raw_spot, _DIRECT_URL_CANDIDATES)
    if direct_url and direct_url.startswith(("http://", "https://")):
        return direct_url
    return _first_string_match(raw_spot, _IMAGE_REFERENCE_CANDIDATES)


@dataclass(frozen=True)
class ImageResolution:
    """The result of resolving one observation's Level 0 image.

    ``image_reference`` is the exact, unmodified ``attributes.image``
    value used to build ``url`` — never discarded once resolved, so a
    caller can preserve it (e.g. as ``SourceObservation.media_reference``)
    without having to independently re-derive it from the raw record.
    It is ``None`` only when the API genuinely provided no separate
    reference — i.e. a direct full URL field was used instead (see
    _DIRECT_URL_CANDIDATES) — never as a side effect of resolution
    itself losing the value.
    """

    url: str
    image_reference: Optional[str]


class ImageUrlResolver:
    """Resolves AND validates the Level 0 image URL for one observation.

    Makes at most one real HTTP request per call to ``resolve`` (a
    HEAD request; falls back to a streamed GET — with the body never
    read — only if HEAD doesn't give a clear answer). Never downloads
    the actual image here; that happens later in processor.py.
    """

    def __init__(
        self,
        image_base_url: str,
        bearer_token: Optional[str] = None,
        timeout_seconds: float = 30.0,
        session: Optional[requests.Session] = None,
    ):
        self._image_base_url = image_base_url.rstrip("/")
        self._bearer_token = bearer_token
        self._timeout_seconds = timeout_seconds
        self._session = session or requests.Session()

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "image/*"}
        if self._bearer_token:
            headers["Authorization"] = f"Bearer {self._bearer_token}"
        return headers

    def resolve(self, raw_spot: dict[str, Any], observation_id: str) -> ImageResolution:
        """Returns a validated, usable Level 0 URL AND the original image
        reference it was built from (see ImageResolution), or raises
        ImageUrlResolutionError."""
        direct_url = _first_string_match(raw_spot, _DIRECT_URL_CANDIDATES)
        image_reference: Optional[str] = None

        if direct_url and direct_url.startswith(("http://", "https://")):
            candidate_url = direct_url
        else:
            image_reference = _first_string_match(raw_spot, _IMAGE_REFERENCE_CANDIDATES)
            if not image_reference:
                raise ImageUrlResolutionError(
                    observation_id=observation_id,
                    image_reference=None,
                    attempted_url=None,
                    http_status=None,
                    reason="no image reference or direct URL field found on the raw spot record",
                )
            candidate_url = f"{self._image_base_url}/{image_reference}.jpg"

        self._validate(candidate_url, observation_id, image_reference)
        return ImageResolution(url=candidate_url, image_reference=image_reference)

    def _validate(self, url: str, observation_id: str, image_reference: Optional[str]) -> None:
        try:
            response = self._session.head(url, headers=self._headers(), timeout=self._timeout_seconds, allow_redirects=True)
            needs_get_fallback = response.status_code in (405, 501) or "Content-Type" not in response.headers
            if needs_get_fallback:
                response.close()
                response = self._session.get(url, headers=self._headers(), timeout=self._timeout_seconds, stream=True)
        except requests.RequestException as exc:
            raise ImageUrlResolutionError(
                observation_id=observation_id,
                image_reference=image_reference,
                attempted_url=url,
                http_status=None,
                reason=f"request failed: {exc}",
            ) from exc

        try:
            if not response.ok:
                raise ImageUrlResolutionError(
                    observation_id=observation_id,
                    image_reference=image_reference,
                    attempted_url=url,
                    http_status=response.status_code,
                    reason="non-success HTTP status",
                )
            content_type = response.headers.get("Content-Type", "")
            if not content_type.lower().startswith("image/"):
                raise ImageUrlResolutionError(
                    observation_id=observation_id,
                    image_reference=image_reference,
                    attempted_url=url,
                    http_status=response.status_code,
                    reason=f"non-image content-type: {content_type!r}",
                )
        finally:
            response.close()


def resolve_media_reference(raw_spot: dict[str, Any]) -> Optional[str]:
    return _first_string_match(raw_spot, _MEDIA_REFERENCE_CANDIDATES)


def resolve_latitude(raw_spot: dict[str, Any]) -> Optional[float]:
    return _first_float_match(raw_spot, _LATITUDE_CANDIDATES)


def resolve_longitude(raw_spot: dict[str, Any]) -> Optional[float]:
    return _first_float_match(raw_spot, _LONGITUDE_CANDIDATES)


COORDINATE_SOURCE_OBSERVATION_MEAN = "spotteron-observation-mean"
"""SourceSite.coordinate_source value: the mean of the confirmed per-spot
``attributes.latitude``/``attributes.longitude`` fields."""

SITE_COORDINATE_TOLERANCE_METRES = 100.0
"""Maximum distance any one observation may lie from the site's mean coordinate.

CoastSnap photos are taken from one fixed camera mount, but each spot's
coordinates come from the contributor's phone, so small GPS scatter is
expected. 100 m allows for that scatter while still rejecting a root
whose observations point at clearly different places (a second site, a
mis-tagged upload). Above the tolerance, no site location is claimed."""

_EARTH_RADIUS_METRES = 6_371_008.8


@dataclass(frozen=True)
class SiteCoordinates:
    """Result of derive_site_coordinates. latitude/longitude are set only when status is CONFIRMED."""

    status: CoordinateStatus
    latitude: Optional[float]
    longitude: Optional[float]
    observation_count: int
    """Image-bearing observations with valid coordinates that the result is based on."""
    error: Optional[str] = None


def _is_valid_coordinate(latitude: float, longitude: float) -> bool:
    return (
        math.isfinite(latitude)
        and math.isfinite(longitude)
        and -90.0 <= latitude <= 90.0
        and -180.0 <= longitude <= 180.0
        and not (latitude == 0.0 and longitude == 0.0)
    )


def _distance_metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Equirectangular approximation: accurate to well under a metre at the
    ~100 m scale this is used for, with no geospatial dependency. Points on
    opposite sides of the antimeridian come out far apart, so such a site
    is reported inconsistent rather than given a wrong mean."""
    mean_lat = math.radians((lat1 + lat2) / 2)
    dx = math.radians(lon2 - lon1) * math.cos(mean_lat)
    dy = math.radians(lat2 - lat1)
    return _EARTH_RADIUS_METRES * math.hypot(dx, dy)


def derive_site_coordinates(observations: Iterable[SourceObservation]) -> SiteCoordinates:
    """Derives one site coordinate from the image-bearing observations of a site.

    Pure and order-independent: the same observations always give the
    same result. Rules:

    1. Observations with neither ``image_url`` nor ``media_reference`` are ignored.
    2. Observations missing either coordinate are ignored.
    3. Non-finite, out-of-range and exactly 0,0 coordinates are rejected;
       the observation is ignored, never used.
    4. No valid coordinate left: MISSING if none were present at all,
       INVALID if some were present but all were rejected.
    5. Any valid coordinate further than SITE_COORDINATE_TOLERANCE_METRES
       from the mean: INCONSISTENT.
    6. Otherwise CONFIRMED, at the arithmetic mean of the valid coordinates.

    The result covers only the observations passed in. The CLI passes
    the manifest's entries — the images this site actually has — so a
    run capped by --max-images confirms the coordinate of the images it
    ingested, not of every spot Spotteron holds for the root.
    """
    valid: list[tuple[float, float]] = []
    rejected = 0
    for observation in observations:
        if not (observation.image_url or observation.media_reference):
            continue
        if observation.latitude is None or observation.longitude is None:
            continue
        if _is_valid_coordinate(observation.latitude, observation.longitude):
            valid.append((observation.latitude, observation.longitude))
        else:
            rejected += 1

    if not valid:
        if rejected:
            return SiteCoordinates(
                status=CoordinateStatus.INVALID, latitude=None, longitude=None, observation_count=0,
                error=f"all {rejected} image-bearing observation coordinate(s) were non-finite, out of range or 0,0",
            )
        return SiteCoordinates(
            status=CoordinateStatus.MISSING, latitude=None, longitude=None, observation_count=0,
            error="no image-bearing observation has latitude and longitude",
        )

    # fsum is exactly rounded, so the mean doesn't depend on observation order.
    mean_lat = math.fsum(lat for lat, _ in valid) / len(valid)
    mean_lon = math.fsum(lon for _, lon in valid) / len(valid)
    furthest = max(_distance_metres(mean_lat, mean_lon, lat, lon) for lat, lon in valid)
    if furthest > SITE_COORDINATE_TOLERANCE_METRES:
        return SiteCoordinates(
            status=CoordinateStatus.INCONSISTENT, latitude=None, longitude=None, observation_count=len(valid),
            error=(
                f"observation coordinates spread {furthest:.0f} m from their mean, beyond the "
                f"{SITE_COORDINATE_TOLERANCE_METRES:.0f} m tolerance"
            ),
        )
    return SiteCoordinates(
        status=CoordinateStatus.CONFIRMED, latitude=mean_lat, longitude=mean_lon, observation_count=len(valid)
    )


def resolve_contributor_display_name(raw_spot: dict[str, Any]) -> Optional[str]:
    return _first_string_match(raw_spot, _CONTRIBUTOR_NAME_CANDIDATES)


def resolve_attribution_permitted(raw_spot: dict[str, Any]) -> bool:
    for path in _ATTRIBUTION_PERMITTED_CANDIDATES:
        value = _dig(raw_spot, path)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"true", "yes", "1"}
    return False

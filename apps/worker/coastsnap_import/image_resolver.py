"""Resolves the Level 0 original image URL (and a few other fields
whose exact JSON path is unconfirmed) from a raw Spotteron spot record.

UNCONFIRMED: the exact field(s) Spotteron v2.4 actually uses for the
full-resolution image URL, latitude/longitude, media reference,
contributor name, and attribution permission. Nothing here is
invented as fact — each is tried as an ordered list of *candidate*
JSON paths, the first present, correctly-typed match wins, and
resolution fails loudly (raising, not guessing) if none match. This
is the single place to update once the real v2.4 schema is confirmed
against a live response — see the final report's "unresolved
assumptions" section.
"""

from __future__ import annotations

from typing import Any, Optional

# Ordered candidate JSON paths, each a tuple of keys to walk. Tried top to
# bottom; first match wins.
_IMAGE_URL_CANDIDATES: tuple[tuple[str, ...], ...] = (
    ("attributes", "image_url"),
    ("attributes", "photo_url"),
    ("attributes", "image"),
    ("attributes", "photo"),
    ("image_url",),
    ("photo_url",),
)

_MEDIA_REFERENCE_CANDIDATES: tuple[tuple[str, ...], ...] = (
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
    """Raised when no candidate field yields a usable Level 0 image URL."""


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


def resolve_level0_image_url(raw_spot: dict[str, Any]) -> str:
    """Returns the best-guess Level 0 original URL, or raises ImageUrlResolutionError."""
    url = _first_string_match(raw_spot, _IMAGE_URL_CANDIDATES)
    if url and url.startswith(("http://", "https://")):
        return url
    spot_id = raw_spot.get("id", raw_spot.get("observation_id", "<unknown>"))
    raise ImageUrlResolutionError(
        f"Could not resolve a Level 0 image URL for spot id={spot_id!r}; "
        f"none of the candidate fields matched a usable http(s) URL: {_IMAGE_URL_CANDIDATES}"
    )


def resolve_media_reference(raw_spot: dict[str, Any]) -> Optional[str]:
    return _first_string_match(raw_spot, _MEDIA_REFERENCE_CANDIDATES)


def resolve_latitude(raw_spot: dict[str, Any]) -> Optional[float]:
    return _first_float_match(raw_spot, _LATITUDE_CANDIDATES)


def resolve_longitude(raw_spot: dict[str, Any]) -> Optional[float]:
    return _first_float_match(raw_spot, _LONGITUDE_CANDIDATES)


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

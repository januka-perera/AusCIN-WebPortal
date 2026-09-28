"""Pydantic models for the site registry (input) and API responses (output).

Response models mirror the frontend's `CoastSnapSite` / `CoastSnapObservation`
(apps/web/data/types/coastsnap.ts) and `PaginatedResult`
(apps/web/data/types/api.ts), serialised with camelCase aliases. No response
model has a field that can hold a filesystem path, a manifest path or a raw
Spotteron identifier.

Contract notes for this milestone (additive or deferred relative to the
frontend types — see apps/api/README.md):

- `thumbnailUrl`, `previewUrl` and `originalUrl` are API media URLs
  (`/media/coastsnap/{mediaId}/...`) when that media is available and
  permitted, otherwise null. `representativeImageUrl` is always null.
- `capturedAtSourceRaw` and `ingestedAtUtc` are additive fields preserving
  the worker's source timestamp and ingestion time.
- `width` and `height` are the Level 1 pixel dimensions as displayed (EXIF
  orientation applied), taken from the worker-generated derivatives index.
  Both are null when no current derivatives entry exists; they are never
  guessed.
- `spotteronSiteId`, `spotteronObservationId`, `spotteronMediaId`,
  `sourceUrl` and `checksumSha256` are omitted.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Generic, Literal, Optional, TypeVar
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

StateOrTerritory = Literal["NSW", "VIC", "QLD", "WA", "SA", "TAS", "NT", "ACT"]
OperatingStatus = Literal["active", "offline", "maintenance"]
PublicationStatus = Literal["public", "embargoed", "project-only", "restricted"]
MediaType = Literal["image", "composite", "timelapse"]
ProcessingStatus = Literal["processed", "processing", "failed"]

SITE_ID_PATTERN = r"^[A-Z0-9][A-Z0-9-]{0,62}[A-Z0-9]$"
SOURCE_ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"


# --- Site registry (reviewed input) ------------------------------------------


class RegistrySite(BaseModel):
    """One human-reviewed site entry. The registry, not the manifest, decides visibility."""

    model_config = ConfigDict(extra="forbid")

    site_id: str = Field(pattern=SITE_ID_PATTERN)
    spotteron_root_id: str = Field(pattern=SOURCE_ID_PATTERN)
    name: str = Field(min_length=1)
    state: StateOrTerritory
    region: str = Field(min_length=1)
    description: str = Field(min_length=1)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    display_time_zone: str
    status: OperatingStatus
    established_since: date
    publication_status: PublicationStatus
    original_download_permitted: bool = False
    """Whether visitors may download the original (currently Level 1 — provisional policy). Only effective for public sites."""
    attribution_text: str = Field(min_length=1)
    is_synthetic: bool

    @field_validator("display_time_zone")
    @classmethod
    def _valid_time_zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"not a valid IANA time zone: {value!r}") from exc
        return value


class SiteRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    sites: list[RegistrySite]

    @model_validator(mode="after")
    def _unique_ids(self) -> "SiteRegistry":
        site_ids = [site.site_id for site in self.sites]
        root_ids = [site.spotteron_root_id for site in self.sites]
        if len(set(site_ids)) != len(site_ids):
            raise ValueError("duplicate site_id in registry")
        if len(set(root_ids)) != len(root_ids):
            raise ValueError("duplicate spotteron_root_id in registry")
        return self


# The derivatives index is parsed with the worker's own model
# (coastsnap_import.derivatives.DerivativesIndex, schema_version 2), exactly as
# the manifest is. The catalogue adds the API-side checks: identifiers, uniqueness,
# path safety and source-checksum staleness.


# --- API responses -------------------------------------------------------------


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class CoastSnapSiteResponse(ApiModel):
    id: str
    name: str
    state: StateOrTerritory
    latitude: float
    longitude: float
    region: str
    description: str
    status: OperatingStatus
    established_since: date
    display_time_zone: str
    representative_image_url: Optional[str] = None
    is_synthetic: bool


class CoastSnapContributorResponse(ApiModel):
    display_name: str
    attribution_text: str


class CoastSnapObservationResponse(ApiModel):
    id: str
    site_id: str
    source_platform: Literal["spotteron"] = "spotteron"
    media_id: str
    media_type: MediaType
    captured_at_utc: datetime
    captured_at_source_raw: Optional[str]
    width: Optional[int] = None
    height: Optional[int] = None
    ingested_at_utc: datetime
    display_time_zone: str
    contributor: CoastSnapContributorResponse
    processing_status: ProcessingStatus
    publication_status: PublicationStatus
    thumbnail_url: Optional[str] = None
    preview_url: Optional[str] = None
    is_original_available: bool = False
    original_url: Optional[str] = None
    caption: str
    alt_text: str
    is_synthetic: bool


T = TypeVar("T")


class PaginatedResponse(ApiModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class DateRangeResponse(ApiModel):
    """Earliest and latest observation at a site; both null when the site has none."""

    earliest: Optional[CoastSnapObservationResponse]
    latest: Optional[CoastSnapObservationResponse]


class HealthResponse(ApiModel):
    status: Literal["ok"]
    public_site_count: int
    public_observation_count: int


class ErrorBody(ApiModel):
    code: str
    message: str


class ErrorResponse(ApiModel):
    error: ErrorBody

"""In-memory CoastSnap catalogue built from a reviewed site registry, one
worker manifest and an optional derivatives index.

The manifest and the derivatives index are parsed with the worker's own models
(`coastsnap_import.models.Manifest` and
`coastsnap_import.derivatives.DerivativesIndex`), so each has exactly one format. Loading is all-or-nothing: an unsafe
path, an inconsistent root ID or an invalid registry or index rejects the whole
input rather than serving a partially trusted catalogue.

Visibility rule: only registry sites with `publication_status == "public"`
are exposed, and only observations from a manifest whose `root_id` belongs to
such a site. A manifest existing on disk never publishes anything by itself.

Each observation keeps trusted internal media metadata (`MediaRecord`): relative
paths, content type, size and checksum. Only the media routes and the
`MediaStore` use it. Response models are built from it, but never carry a path.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal, Optional
from zoneinfo import ZoneInfo

from coastsnap_import.derivatives import DerivativeFile, DerivativeIndexEntry, DerivativesIndex
from coastsnap_import.models import (
    LEVEL0_DIR,
    LEVEL1_DIR,
    METADATA_SOURCE_RECORDS_DIR,
    Manifest,
    ManifestEntry,
    build_site_directory_id,
)
from pydantic import ValidationError

from .paths import UnsafePathError, safe_path_segments
from .schemas import (
    SOURCE_ID_PATTERN,
    CoastSnapContributorResponse,
    CoastSnapObservationResponse,
    CoastSnapSiteResponse,
    MediaType,
    RegistrySite,
    SiteRegistry,
)

logger = logging.getLogger(__name__)

CONTRIBUTOR_PLACEHOLDER_NAME = "CoastSnap contributor"
"""Contributor names are never read from the manifest in this milestone —
the contributor-display policy is not decided yet."""

DERIVATIVES_DIR = "derivatives"
THUMBNAILS_DIR = f"{DERIVATIVES_DIR}/thumbnails"
PREVIEWS_DIR = f"{DERIVATIVES_DIR}/previews"

SAFE_IMAGE_CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
"""Extension -> content type for files the API will serve. Anything else (including HEIC, which
browsers can't display) is kept in the catalogue but not offered for download."""

DERIVATIVE_CONTENT_TYPE = "image/jpeg"

MediaKind = Literal["level0", "level1", "preview", "thumbnail"]

_SOURCE_ID_RE = re.compile(SOURCE_ID_PATTERN)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class CatalogueError(Exception):
    """Raised when catalogue inputs are missing, malformed or unsafe."""


# --- Path safety -----------------------------------------------------------------


def validate_relative_path(value: str, *, field: str, required_prefix: str) -> None:
    """Catalogue-load wrapper around `safe_path_segments`: any unsafe path rejects the input."""
    try:
        safe_path_segments(value, required_prefix=required_prefix)
    except UnsafePathError as exc:
        raise CatalogueError(f"{field}: {exc}") from exc


def _validate_entry_paths(entry: ManifestEntry, root_id: str) -> None:
    site_dir = build_site_directory_id(root_id)
    obs_id = entry.observation.observation_id
    checks: list[tuple[str, Optional[str], str]] = [
        ("source_record_ref.site_record_relative_path", entry.source_record_ref.site_record_relative_path,
         f"{METADATA_SOURCE_RECORDS_DIR}/"),
        ("source_record_ref.observation_record_relative_path",
         entry.source_record_ref.observation_record_relative_path, f"{METADATA_SOURCE_RECORDS_DIR}/"),
    ]
    for level_name, product, level_dir in (("level0", entry.level0, LEVEL0_DIR), ("level1", entry.level1, LEVEL1_DIR)):
        if product is None:
            continue
        prefix = f"{level_dir}/{site_dir}/"
        checks.append((f"{level_name}.local_relative_path", product.local_relative_path, prefix))
        checks.append((f"{level_name}.remote_relative_path", product.remote_relative_path, prefix))
    for transfer_name, transfer in (("level0_transfer", entry.level0_transfer), ("level1_transfer", entry.level1_transfer)):
        if transfer is None:
            continue
        level_dir = LEVEL0_DIR if transfer_name == "level0_transfer" else LEVEL1_DIR
        prefix = f"{level_dir}/{site_dir}/"
        checks.append((f"{transfer_name}.remote_relative_path", transfer.remote_relative_path, prefix))
        checks.append((f"{transfer_name}.remote_part_relative_path", transfer.remote_part_relative_path, prefix))
    for field, value, prefix in checks:
        validate_relative_path(value or "", field=f"observation {obs_id!r} {field}", required_prefix=prefix)


def _validate_derivative_paths(item: DerivativeIndexEntry, root_id: str) -> None:
    site_dir = build_site_directory_id(root_id)
    for field, rendition, base in (
        ("thumbnail", item.thumbnail, THUMBNAILS_DIR),
        ("preview", item.preview, PREVIEWS_DIR),
    ):
        if rendition is None:
            continue
        value = rendition.relative_path
        validate_relative_path(value, field=f"derivative {item.observation_id!r} {field}",
                               required_prefix=f"{base}/{site_dir}/")
        if not value.lower().endswith((".jpg", ".jpeg")):
            raise CatalogueError(f"derivative {item.observation_id!r} {field}: derivatives must be JPEG")


# --- Identifiers ----------------------------------------------------------------


def build_media_id(site_id: str, observation_id: str) -> str:
    """Stable, opaque public ID. Derived from (site, source observation) so it
    survives reloads, but reveals neither the Spotteron ID nor any path."""
    digest = hashlib.sha256(f"coastsnap\x00{site_id}\x00{observation_id}".encode("utf-8")).hexdigest()
    return f"csm_{digest[:24]}"


# --- Catalogue ------------------------------------------------------------------


ProductLevelName = Literal["level0", "level1"]


@dataclass(frozen=True)
class ProductFile:
    """Trusted metadata for one product level's file, taken from the manifest. Never serialised."""

    relative_path: str
    """Relative to the media root (the worker's staging directory). Validated at load and never returned."""
    content_type: Optional[str]
    """None when the file type isn't in SAFE_IMAGE_CONTENT_TYPES; such files are never served."""
    file_size: int
    sha256: str
    download_permitted: bool
    """Registry policy for this level only. Never defaults to True, and says nothing about whether the file exists."""

    @property
    def download_offered(self) -> bool:
        return self.download_permitted and self.content_type is not None


@dataclass(frozen=True)
class MediaRecord:
    """Trusted internal media metadata. Never serialised into a response."""

    level0: ProductFile
    """The untouched source image, exactly as downloaded from Spotteron."""
    level1: ProductFile
    """The AusCIN provenance copy: Level 0's image bytes plus embedded provenance XMP."""
    width: Optional[int]
    """Level 1 pixel dimensions as displayed (EXIF orientation applied), from the derivatives index."""
    height: Optional[int]
    thumbnail: Optional[DerivativeFile]
    """Trusted derivative record: relative path (under the derivatives root), size, checksum, dimensions."""
    preview: Optional[DerivativeFile]

    def product(self, level: ProductLevelName) -> ProductFile:
        return self.level0 if level == "level0" else self.level1


@dataclass(frozen=True)
class CatalogueObservation:
    media_id: str
    site_id: str
    media_type: MediaType
    captured_at_utc: datetime
    captured_at_source_raw: Optional[str]
    ingested_at_utc: datetime
    local_date: date
    """Capture date in the site's display time zone — what date filters compare against."""
    media: MediaRecord


@dataclass(frozen=True)
class ObservationFilters:
    media_type: Optional[MediaType] = None
    date: Optional[date] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None


class Catalogue:
    def __init__(
        self,
        sites: list[RegistrySite],
        observations: list[CatalogueObservation],
        *,
        media_enabled: bool = False,
        media_base_url: str = "",
    ):
        self._sites = {site.site_id: site for site in sites if site.publication_status == "public"}
        by_site: dict[str, list[CatalogueObservation]] = {site_id: [] for site_id in self._sites}
        for observation in observations:
            if observation.site_id in by_site:
                by_site[observation.site_id].append(observation)
        for items in by_site.values():
            items.sort(key=lambda o: (o.captured_at_utc, o.media_id), reverse=True)
        self._observations_by_site = by_site
        self._by_media_id = {o.media_id: o for items in by_site.values() for o in items}
        self._media_enabled = media_enabled
        self._media_base_url = media_base_url

    # Sites

    def list_sites(self) -> list[CoastSnapSiteResponse]:
        return [_site_response(site) for site in sorted(self._sites.values(), key=lambda s: s.name)]

    def get_site(self, site_id: str) -> Optional[CoastSnapSiteResponse]:
        site = self._sites.get(site_id)
        return _site_response(site) if site else None

    def has_site(self, site_id: str) -> bool:
        return site_id in self._sites

    # Observations

    def list_observations(self, site_id: str, filters: ObservationFilters) -> list[CoastSnapObservationResponse]:
        """Newest first. Caller must check has_site() first."""
        return [self._observation_response(o) for o in self._observations_by_site[site_id] if _matches(o, filters)]

    def get_observation(self, site_id: str, media_id: str) -> Optional[CoastSnapObservationResponse]:
        """Site-scoped: a media ID belonging to another site is never resolved."""
        observation = self._by_media_id.get(media_id)
        if observation is None or observation.site_id != site_id:
            return None
        return self._observation_response(observation)

    def date_range(
        self, site_id: str
    ) -> tuple[Optional[CoastSnapObservationResponse], Optional[CoastSnapObservationResponse]]:
        items = self._observations_by_site[site_id]
        if not items:
            return None, None
        return self._observation_response(items[-1]), self._observation_response(items[0])

    # Media

    @property
    def media_enabled(self) -> bool:
        return self._media_enabled

    def get_media(self, media_id: str) -> Optional[CatalogueObservation]:
        """Internal lookup for the media routes. Only observations of public sites are ever indexed."""
        return self._by_media_id.get(media_id)

    def media_url(self, media_id: str, kind: MediaKind) -> str:
        return f"{self._media_base_url}/media/coastsnap/{media_id}/{kind}"

    # Health

    @property
    def public_site_count(self) -> int:
        return len(self._sites)

    @property
    def public_observation_count(self) -> int:
        return len(self._by_media_id)

    # Response mapping

    def _observation_response(self, observation: CatalogueObservation) -> CoastSnapObservationResponse:
        site = self._sites[observation.site_id]
        media = observation.media
        local_label = _long_date(observation.local_date)
        level0_available = self._media_enabled and media.level0.download_offered
        level1_available = self._media_enabled and media.level1.download_offered
        return CoastSnapObservationResponse(
            id=observation.media_id,
            site_id=site.site_id,
            media_id=observation.media_id,
            media_type=observation.media_type,
            captured_at_utc=observation.captured_at_utc,
            captured_at_source_raw=observation.captured_at_source_raw,
            # Trusted dimensions from the worker's derivatives index, and only as a pair.
            width=media.width if media.width and media.height else None,
            height=media.height if media.width and media.height else None,
            ingested_at_utc=observation.ingested_at_utc,
            display_time_zone=site.display_time_zone,
            contributor=CoastSnapContributorResponse(
                display_name=CONTRIBUTOR_PLACEHOLDER_NAME, attribution_text=site.attribution_text
            ),
            processing_status="processed",
            publication_status=site.publication_status,
            thumbnail_url=(
                self.media_url(observation.media_id, "thumbnail") if self._media_enabled and media.thumbnail else None
            ),
            preview_url=(
                self.media_url(observation.media_id, "preview") if self._media_enabled and media.preview else None
            ),
            level0_download_available=level0_available,
            level0_download_url=self.media_url(observation.media_id, "level0") if level0_available else None,
            # A checksum is public integrity metadata, published only alongside a downloadable file.
            level0_checksum_sha256=media.level0.sha256 if level0_available else None,
            level1_download_available=level1_available,
            level1_download_url=self.media_url(observation.media_id, "level1") if level1_available else None,
            level1_checksum_sha256=media.level1.sha256 if level1_available else None,
            # Deprecated: kept for compatibility, and always mirrors Level 1.
            is_original_available=level1_available,
            original_url=self.media_url(observation.media_id, "level1") if level1_available else None,
            caption=f"{site.name} — CoastSnap observation, {local_label}",
            alt_text=f"Community photo of {site.name} taken from the CoastSnap alignment mark on {local_label}.",
            is_synthetic=site.is_synthetic,
        )


def _matches(observation: CatalogueObservation, filters: ObservationFilters) -> bool:
    # Mirrors applyCoastSnapObservationFilters in apps/web/data/coastsnap-queries.ts:
    # a single date takes precedence over a from/to range; both compare local dates.
    if filters.media_type and observation.media_type != filters.media_type:
        return False
    if filters.date:
        return observation.local_date == filters.date
    if filters.date_from and observation.local_date < filters.date_from:
        return False
    if filters.date_to and observation.local_date > filters.date_to:
        return False
    return True


def _site_response(site: RegistrySite) -> CoastSnapSiteResponse:
    return CoastSnapSiteResponse(
        id=site.site_id,
        name=site.name,
        state=site.state,
        latitude=site.latitude,
        longitude=site.longitude,
        region=site.region,
        description=site.description,
        status=site.status,
        established_since=site.established_since,
        display_time_zone=site.display_time_zone,
        representative_image_url=None,
        is_synthetic=site.is_synthetic,
    )


def _long_date(value: date) -> str:
    return f"{value.day} {value:%B %Y}"


# --- Loading --------------------------------------------------------------------


def load_registry(path: Path) -> SiteRegistry:
    try:
        return SiteRegistry.model_validate_json(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CatalogueError(f"Cannot read site registry: {exc.strerror or exc}") from exc
    except ValidationError as exc:
        raise CatalogueError(f"Invalid site registry: {exc}") from exc


def load_manifest(path: Path) -> Manifest:
    try:
        return Manifest.model_validate_json(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CatalogueError(f"Cannot read manifest: {exc.strerror or exc}") from exc
    except ValidationError as exc:
        raise CatalogueError(f"Invalid manifest: {exc}") from exc


def load_derivatives_index(path: Path) -> DerivativesIndex:
    try:
        return DerivativesIndex.model_validate_json(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CatalogueError(f"Cannot read derivatives index: {exc.strerror or exc}") from exc
    except ValidationError as exc:
        raise CatalogueError(f"Invalid derivatives index: {exc}") from exc


def _utc(value: datetime, *, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CatalogueError(f"{field} is not timezone-aware; the worker always writes UTC")
    return value.astimezone(timezone.utc)


def _servable_content_type(relative_path: str) -> Optional[str]:
    suffix = relative_path.rsplit("/", 1)[-1]
    dot = suffix.rfind(".")
    return SAFE_IMAGE_CONTENT_TYPES.get(suffix[dot:].lower()) if dot > 0 else None


def build_catalogue(
    registry: SiteRegistry,
    manifest: Manifest,
    derivatives: Optional[DerivativesIndex] = None,
    *,
    media_enabled: bool = False,
    media_base_url: str = "",
) -> Catalogue:
    root_id = manifest.root_id
    if not _SOURCE_ID_RE.match(root_id):
        raise CatalogueError("manifest root_id has an unexpected format")

    seen: set[str] = set()
    for entry in manifest.entries:
        obs = entry.observation
        if not _SOURCE_ID_RE.match(obs.observation_id):
            raise CatalogueError("manifest contains an observation_id with an unexpected format")
        if obs.observation_id in seen:
            raise CatalogueError(f"duplicate observation {obs.observation_id!r} in manifest")
        seen.add(obs.observation_id)
        if obs.root_id != root_id or entry.site.root_id != root_id:
            raise CatalogueError(f"observation {obs.observation_id!r} does not belong to manifest root_id")
        _validate_entry_paths(entry, root_id)
        for level_name, product in (("level0", entry.level0), ("level1", entry.level1)):
            # Each checksum becomes that level's public ETag and published integrity value.
            if product is not None and not _SHA256_RE.match(product.checksum.sha256):
                raise CatalogueError(f"observation {obs.observation_id!r} {level_name} checksum is not a SHA-256 hex digest")

    level1_by_obs = {e.observation.observation_id: e.level1 for e in manifest.entries}
    derivative_by_obs: dict[str, DerivativeIndexEntry] = {}
    if derivatives is not None:
        if derivatives.root_id != root_id:
            raise CatalogueError("derivatives index root_id does not match the manifest root_id")
        for item in derivatives.derivatives:
            if item.observation_id not in seen:
                raise CatalogueError(f"derivatives index references unknown observation {item.observation_id!r}")
            if item.observation_id in derivative_by_obs:
                raise CatalogueError(f"duplicate observation {item.observation_id!r} in derivatives index")
            _validate_derivative_paths(item, root_id)
            level1 = level1_by_obs[item.observation_id]
            if level1 is None or item.source_sha256 != level1.checksum.sha256 or item.level1_product_id != level1.product_id:
                # Made from a different Level 1 than the manifest now records. Stale renditions are
                # dropped (so none is offered) rather than served as if they matched the original.
                logger.warning("Ignoring stale derivatives for observation %r", item.observation_id)
                continue
            derivative_by_obs[item.observation_id] = item

    site = next((s for s in registry.sites if s.spotteron_root_id == root_id), None)
    observations: list[CatalogueObservation] = []
    if site is not None and site.publication_status == "public":
        zone = ZoneInfo(site.display_time_zone)
        for entry in manifest.entries:
            obs = entry.observation
            # Only complete records are presentable: both products present and a known capture time.
            if entry.level0 is None or entry.level1 is None or obs.spotted_at_utc is None:
                continue
            captured = _utc(obs.spotted_at_utc, field=f"observation {obs.observation_id!r} spotted_at_utc")
            derivative = derivative_by_obs.get(obs.observation_id)
            observations.append(
                CatalogueObservation(
                    media_id=build_media_id(site.site_id, obs.observation_id),
                    site_id=site.site_id,
                    media_type="image",
                    captured_at_utc=captured,
                    captured_at_source_raw=obs.spotted_at_raw,
                    ingested_at_utc=_utc(entry.ingested_at_utc, field="ingested_at_utc"),
                    local_date=captured.astimezone(zone).date(),
                    media=MediaRecord(
                        level0=ProductFile(
                            relative_path=entry.level0.local_relative_path,
                            content_type=_servable_content_type(entry.level0.local_relative_path),
                            file_size=entry.level0.file_size_bytes,
                            sha256=entry.level0.checksum.sha256,
                            download_permitted=site.level0_download_permitted,
                        ),
                        level1=ProductFile(
                            relative_path=entry.level1.local_relative_path,
                            content_type=_servable_content_type(entry.level1.local_relative_path),
                            file_size=entry.level1.file_size_bytes,
                            sha256=entry.level1.checksum.sha256,
                            download_permitted=site.level1_download_permitted,
                        ),
                        width=derivative.source_width if derivative else None,
                        height=derivative.source_height if derivative else None,
                        thumbnail=derivative.thumbnail if derivative else None,
                        preview=derivative.preview if derivative else None,
                    ),
                )
            )
    return Catalogue(registry.sites, observations, media_enabled=media_enabled, media_base_url=media_base_url)


def load_catalogue(
    site_registry_path: Path,
    manifest_path: Path,
    derivatives_index_path: Optional[Path] = None,
    *,
    media_enabled: bool = False,
    media_base_url: str = "",
) -> Catalogue:
    return build_catalogue(
        load_registry(site_registry_path),
        load_manifest(manifest_path),
        load_derivatives_index(derivatives_index_path) if derivatives_index_path else None,
        media_enabled=media_enabled,
        media_base_url=media_base_url,
    )

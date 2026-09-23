"""Ingestion-pipeline data models.

Deliberately NOT the frontend's ``CoastSnapObservation`` type
(``apps/web/data/types/coastsnap.ts``) — that type describes what a
*catalogue* shows a visitor. This module describes what the *importer*
needs to track while doing its job: product level, local and remote
storage paths, parent/child linkage between Level 0 and Level 1,
per-product checksums, processing details and per-file transfer
status. A later, separate mapping step would translate a verified
manifest entry into whatever a future catalogue API exposes.

Field names on ``SourceSite``/``SourceObservation`` below are
placeholders pending confirmation of the real Spotteron v2.4 response
shape (see spotteron_client.py's module docstring for what is and
isn't confirmed). Nothing here invents a Spotteron field that isn't
either explicitly supplied by the project owner or clearly marked
uncertain.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import PurePosixPath
from typing import Optional

from pydantic import BaseModel, Field


class ProductLevel(str, Enum):
    """Where a file sits in the ingestion pipeline."""

    LEVEL_0 = "level0"
    """Exact original, as retrieved from Spotteron. Byte-for-byte immutable once written."""

    LEVEL_1 = "level1"
    """A copy of Level 0 with approved metadata embedded. Never decoded/resized/recompressed."""


class TransferState(str, Enum):
    """The state of one product's SFTP transfer to Gadi."""

    PENDING = "pending"
    UPLOADING = "uploading"
    UPLOADED_PART = "uploaded_part"
    RENAMED = "renamed"
    VERIFIED = "verified"
    FAILED = "failed"
    SKIPPED_EXISTING = "skipped_existing"


class SourceSite(BaseModel):
    """One Spotteron site/root, as returned for the configured root_id.

    Field names are placeholders — TBC against the real v2.4 response.
    The full raw JSON is written separately under
    ``metadata/source-records/sites/`` (see ``build_source_record_paths``)
    rather than duplicated here, per the "don't duplicate raw records in
    every manifest entry" requirement.
    """

    root_id: str
    name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class SourceObservation(BaseModel):
    """One Spotteron spot/observation under ``root_id``.

    Field names are placeholders — TBC against the real v2.4 response,
    except ``spotted_at`` and ``topic_id`` filtering, which the project
    owner confirmed explicitly.
    """

    observation_id: str
    root_id: str
    spotted_at_utc: Optional[datetime] = None
    """Parsed from the raw record's ``spotted_at`` field. None if absent/unparseable — such records are excluded from date filtering rather than guessed at."""
    image_url: Optional[str] = None
    """As resolved by image_resolver.py; may be None if resolution failed."""
    media_reference: Optional[str] = None
    """Spotteron's own identifier for the image/media asset itself, distinct from observation_id. TBC field name."""
    contributor_display_name: Optional[str] = None
    """TBC field name/availability."""
    contributor_attribution_permitted: bool = False
    """Conservative default: only True when a real permission signal is found in the raw record. See image_resolver.py / spotteron_client.py parsing. Never assume permission."""


class SourceRecordRef(BaseModel):
    """Relative paths to the full raw Spotteron JSON, stored separately from the manifest."""

    site_record_relative_path: str
    observation_record_relative_path: str


class ChecksumInfo(BaseModel):
    sha256: str
    computed_at_utc: datetime


class Level0Product(BaseModel):
    """The original file exactly as retrieved from Spotteron. Never modified after this is created."""

    product_id: str
    product_level: ProductLevel = ProductLevel.LEVEL_0
    parent_observation_id: str
    source_url: str
    local_relative_path: str
    """Relative to the configured staging directory — never an absolute host path."""
    remote_relative_path: str
    """Relative to remote_root — see build_level_remote_relative_path(). Never an absolute filesystem path."""
    file_size_bytes: int
    content_type: Optional[str] = None
    checksum: ChecksumInfo
    downloaded_at_utc: datetime


class ProcessingDetails(BaseModel):
    embedder_backend: str
    embedded_metadata_fields: list[str]
    processing_software: str
    processing_version: str
    processed_at_utc: datetime


class Level1Product(BaseModel):
    """A byte-for-byte copy of Level 0 with approved metadata embedded into the copy."""

    product_id: str
    product_level: ProductLevel = ProductLevel.LEVEL_1
    parent_product_id: str
    """-> Level0Product.product_id ("parent media")."""
    parent_observation_id: str
    local_relative_path: str
    remote_relative_path: str
    file_size_bytes: int
    checksum: ChecksumInfo
    """Computed AFTER metadata embedding — this is the checksum of the file as it will actually be transferred."""
    processing: ProcessingDetails


class TransferResult(BaseModel):
    product_id: str
    remote_relative_path: str
    remote_part_relative_path: str
    state: TransferState
    attempts: int
    last_attempt_at_utc: datetime
    remote_checksum: Optional[str] = None
    error_message: Optional[str] = None


class ManifestEntry(BaseModel):
    site: SourceSite
    observation: SourceObservation
    source_record_ref: SourceRecordRef
    level0: Optional[Level0Product] = None
    level1: Optional[Level1Product] = None
    level0_transfer: Optional[TransferResult] = None
    level1_transfer: Optional[TransferResult] = None
    ingested_at_utc: datetime
    schema_version: int = 1


class Manifest(BaseModel):
    run_id: str
    root_id: str
    topic_id: int
    date_from_utc: datetime
    date_to_utc: datetime
    generated_at_utc: datetime
    remote_root: str
    entries: list[ManifestEntry] = Field(default_factory=list)
    schema_version: int = 1


# --- Remote/local path structure -------------------------------------------
#
# Per the approved design: paths are always built relative to a root
# (remote_root for the SFTP side, staging_dir locally) and stored as
# relative paths in the manifest. Nothing in this module ever holds or
# returns an absolute filesystem path.

LEVEL0_DIR = "level-0"
LEVEL1_DIR = "level-1"
METADATA_SOURCE_RECORDS_DIR = "metadata/source-records"
MANIFESTS_DIR = "manifests"


def build_level_relative_path(
    level: ProductLevel, site_id: str, captured_at_utc: datetime, filename: str
) -> str:
    """``level-0|level-1/<site-id>/<year>/<month>/<day>/images/<filename>``, POSIX-style regardless of host OS."""
    base = LEVEL0_DIR if level is ProductLevel.LEVEL_0 else LEVEL1_DIR
    path = PurePosixPath(base, site_id, f"{captured_at_utc:%Y}", f"{captured_at_utc:%m}", f"{captured_at_utc:%d}", "images", filename)
    return str(path)


def build_source_record_paths(root_id: str, observation_id: str) -> SourceRecordRef:
    return SourceRecordRef(
        site_record_relative_path=str(PurePosixPath(METADATA_SOURCE_RECORDS_DIR, "sites", f"{root_id}.json")),
        observation_record_relative_path=str(
            PurePosixPath(METADATA_SOURCE_RECORDS_DIR, "observations", f"{observation_id}.json")
        ),
    )


def build_manifest_relative_path(run_id: str) -> str:
    return str(PurePosixPath(MANIFESTS_DIR, f"{run_id}.json"))

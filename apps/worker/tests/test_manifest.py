from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from coastsnap_import.config import DEFAULT_REMOTE_ROOT
from coastsnap_import.manifest import ManifestError, ManifestStore
from coastsnap_import.models import (
    ChecksumInfo,
    Level0Product,
    Level1Product,
    ManifestEntry,
    ProcessingDetails,
    SourceObservation,
    SourceRecordRef,
    SourceSite,
    TransferResult,
    TransferState,
)

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _entry(observation_id: str, level0_state=None, level1_state=None) -> ManifestEntry:
    checksum = ChecksumInfo(sha256="a" * 64, computed_at_utc=NOW)
    level0 = Level0Product(
        product_id=f"{observation_id}-L0",
        parent_observation_id=observation_id,
        source_url="https://cdn.example-spotteron.test/x.jpg",
        local_relative_path="level-0/S/2026/08/01/images/x.jpg",
        remote_relative_path="level-0/S/2026/08/01/images/x.jpg",
        file_size_bytes=10,
        checksum=checksum,
        downloaded_at_utc=NOW,
    )
    level1 = Level1Product(
        product_id=f"{observation_id}-L1",
        parent_product_id=level0.product_id,
        parent_observation_id=observation_id,
        local_relative_path="level-1/S/2026/08/01/images/x.jpg",
        remote_relative_path="level-1/S/2026/08/01/images/x.jpg",
        file_size_bytes=12,
        checksum=checksum,
        processing=ProcessingDetails(
            embedder_backend="exiftool",
            embedded_metadata_fields=["XMP-dc:Source"],
            processing_software="coastsnap-import",
            processing_version="0.1.0",
            processed_at_utc=NOW,
        ),
    )

    def _transfer(state):
        if state is None:
            return None
        return TransferResult(
            product_id=level0.product_id,
            remote_relative_path=level0.remote_relative_path,
            remote_part_relative_path=level0.remote_relative_path + ".part",
            state=state,
            attempts=1,
            last_attempt_at_utc=NOW,
            remote_checksum="a" * 64 if state in (TransferState.VERIFIED, TransferState.SKIPPED_EXISTING) else None,
        )

    return ManifestEntry(
        site=SourceSite(root_id="37"),
        observation=SourceObservation(observation_id=observation_id, root_id="37", spotted_at_utc=NOW),
        source_record_ref=SourceRecordRef(
            site_record_relative_path="metadata/source-records/sites/37.json",
            observation_record_relative_path=f"metadata/source-records/observations/{observation_id}.json",
        ),
        level0=level0,
        level1=level1,
        level0_transfer=_transfer(level0_state),
        level1_transfer=_transfer(level1_state),
        ingested_at_utc=NOW,
    )


def test_load_returns_none_when_file_missing(tmp_path: Path):
    assert ManifestStore().load(tmp_path / "missing.json") is None


def test_load_or_create_creates_new_manifest_when_missing(tmp_path: Path):
    manifest = ManifestStore().load_or_create(
        tmp_path / "manifest.json", run_id="r1", root_id="37", topic_id=37,
        date_from_utc=NOW, date_to_utc=NOW, remote_root="/g/data/qu34/AusCIN/coastsnap-test",
    )
    assert manifest.entries == []
    assert manifest.root_id == "37"


def test_load_or_create_reuses_existing_manifest_when_remote_root_matches(tmp_path: Path):
    path = tmp_path / "manifest.json"
    store = ManifestStore()
    first = store.load_or_create(
        path, run_id="r1", root_id="37", topic_id=37,
        date_from_utc=NOW, date_to_utc=NOW, remote_root="/g/data/qu34/AusCIN/coastsnap",
    )
    store.save(first, path)

    second = store.load_or_create(
        path, run_id="r2", root_id="37", topic_id=37,
        date_from_utc=NOW, date_to_utc=NOW, remote_root="/g/data/qu34/AusCIN/coastsnap",
    )
    assert second.remote_root == "/g/data/qu34/AusCIN/coastsnap"


def test_load_or_create_rejects_a_configured_remote_root_that_differs_from_the_existing_manifest(tmp_path: Path):
    """The exact real-world failure this guards against: a manifest was
    created recording one remote_root, and a later run resolves a
    DIFFERENT value (whatever the reason — env edited, CLI flag added,
    a different shell). Reusing the manifest would silently keep
    displaying the OLD remote root while a real transfer goes to the
    NEW one. This must raise, never silently pick either value."""
    path = tmp_path / "manifest.json"
    store = ManifestStore()
    original = store.create(
        run_id="r1", root_id="37", topic_id=37, date_from_utc=NOW, date_to_utc=NOW,
        remote_root="/g/data/qu34/AusCIN/coastsnap-test",
    )
    store.save(original, path)

    with pytest.raises(ManifestError, match="coastsnap-test.*coastsnap\\b"):
        store.load_or_create(
            path, run_id="r2", root_id="37", topic_id=37, date_from_utc=NOW, date_to_utc=NOW,
            remote_root="/g/data/qu34/AusCIN/coastsnap",  # different: no "-test" suffix
        )


def test_load_or_create_rejects_default_remote_root_silently_overriding_an_explicit_one(tmp_path: Path):
    """The default remote_root must never silently win over a manifest
    that was created with an explicitly configured one — e.g. a rerun
    where GADI_REMOTE_ROOT was accidentally unset falls back to
    DEFAULT_REMOTE_ROOT, which must not be treated as equivalent to
    the value the manifest was actually created with."""
    path = tmp_path / "manifest.json"
    store = ManifestStore()
    explicit = store.create(
        run_id="r1", root_id="37", topic_id=37, date_from_utc=NOW, date_to_utc=NOW,
        remote_root="/g/data/qu34/AusCIN/coastsnap",  # explicitly configured, not the default
    )
    store.save(explicit, path)

    with pytest.raises(ManifestError):
        store.load_or_create(
            path, run_id="r2", root_id="37", topic_id=37, date_from_utc=NOW, date_to_utc=NOW,
            remote_root=DEFAULT_REMOTE_ROOT,  # the module default, resolved because the env var was unset
        )


def test_save_then_load_round_trips(tmp_path: Path):
    store = ManifestStore()
    manifest = store.create("r1", "37", 37, NOW, NOW, "/g/data/qu34/AusCIN/coastsnap-test")
    manifest = store.upsert_entry(manifest, _entry("1001", TransferState.VERIFIED, TransferState.VERIFIED))
    path = tmp_path / "manifest.json"

    store.save(manifest, path)
    reloaded = store.load(path)

    assert reloaded is not None
    assert len(reloaded.entries) == 1
    assert reloaded.entries[0].observation.observation_id == "1001"
    assert reloaded.entries[0].level0.checksum.sha256 == "a" * 64


def test_save_is_atomic_no_tmp_file_left_behind(tmp_path: Path):
    store = ManifestStore()
    manifest = store.create("r1", "37", 37, NOW, NOW, "/g/data/qu34/AusCIN/coastsnap-test")
    path = tmp_path / "manifest.json"
    store.save(manifest, path)
    assert path.exists()
    assert not path.with_suffix(path.suffix + ".tmp").exists()


def test_upsert_replaces_existing_entry_not_duplicates(tmp_path: Path):
    store = ManifestStore()
    manifest = store.create("r1", "37", 37, NOW, NOW, "/g/data/qu34/AusCIN/coastsnap-test")
    manifest = store.upsert_entry(manifest, _entry("1001", None, None))
    manifest = store.upsert_entry(manifest, _entry("1001", TransferState.VERIFIED, TransferState.VERIFIED))

    assert len(manifest.entries) == 1
    assert manifest.entries[0].level0_transfer.state == TransferState.VERIFIED


def test_find_entry(tmp_path: Path):
    store = ManifestStore()
    manifest = store.create("r1", "37", 37, NOW, NOW, "/g/data/qu34/AusCIN/coastsnap-test")
    manifest = store.upsert_entry(manifest, _entry("1001", None, None))
    assert store.find_entry(manifest, "1001") is not None
    assert store.find_entry(manifest, "does-not-exist") is None


@pytest.mark.parametrize(
    "level0_state,level1_state,expected",
    [
        (None, None, False),
        (TransferState.PENDING, TransferState.PENDING, False),
        (TransferState.VERIFIED, TransferState.PENDING, False),
        (TransferState.VERIFIED, TransferState.VERIFIED, True),
        (TransferState.VERIFIED, TransferState.SKIPPED_EXISTING, True),
        (TransferState.FAILED, TransferState.VERIFIED, False),
    ],
)
def test_is_fully_transferred(level0_state, level1_state, expected):
    entry = _entry("1001", level0_state, level1_state)
    assert ManifestStore.is_fully_transferred(entry) is expected


def test_has_local_products():
    assert ManifestStore.has_local_products(_entry("1001", None, None)) is True
    bare_entry = _entry("1001", None, None).model_copy(update={"level1": None})
    assert ManifestStore.has_local_products(bare_entry) is False


def test_load_raises_manifest_error_for_corrupt_json(tmp_path: Path):
    path = tmp_path / "manifest.json"
    path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ManifestError):
        ManifestStore().load(path)

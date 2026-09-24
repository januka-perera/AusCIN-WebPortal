"""JSON manifest read/write.

The manifest is the single source of truth for idempotent reruns: the
CLI consults it before doing any work for a given observation. Writes
are atomic (write to a temp file, then os.replace) so a crash mid-save
can never leave a corrupt or half-written manifest in place.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import Manifest, ManifestEntry, TransferState


class ManifestError(Exception):
    """Raised for manifest read/write failures."""


class ManifestStore:
    def load(self, path: Path) -> Optional[Manifest]:
        if not path.exists():
            return None
        try:
            return Manifest.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ManifestError(f"Failed to load manifest at {path}: {exc}") from exc

    def create(
        self,
        run_id: str,
        root_id: str,
        topic_id: int,
        date_from_utc: datetime,
        date_to_utc: datetime,
        remote_root: str,
    ) -> Manifest:
        return Manifest(
            run_id=run_id,
            root_id=root_id,
            topic_id=topic_id,
            date_from_utc=date_from_utc,
            date_to_utc=date_to_utc,
            generated_at_utc=datetime.now(timezone.utc),
            remote_root=remote_root,
            entries=[],
        )

    def load_or_create(
        self,
        path: Path,
        run_id: str,
        root_id: str,
        topic_id: int,
        date_from_utc: datetime,
        date_to_utc: datetime,
        remote_root: str,
    ) -> Manifest:
        """Loads the existing manifest at ``path`` if present, otherwise
        creates a fresh one.

        ``remote_root`` here is the CURRENT run's single authoritative
        value (WorkerConfig.remote_root — see config.py). If a manifest
        already exists, its OWN recorded ``remote_root`` must match it
        exactly: a manifest is meant to describe files transferred to
        one remote location, so silently reusing a stale manifest under
        a different remote_root would keep displaying the OLD location
        while a real transfer actually goes to the NEW one — the exact
        failure mode that this check exists to prevent (see
        cli.py/config.py/README.md's "remote root consistency" notes).
        Raises ManifestError rather than silently preferring either
        value.
        """
        existing = self.load(path)
        if existing is not None:
            if existing.remote_root != remote_root:
                raise ManifestError(
                    f"Manifest at {path} was created with remote_root={existing.remote_root!r}, but the "
                    f"current configuration resolves remote_root={remote_root!r}. Refusing to continue: "
                    "reusing this manifest with a different remote root would record the wrong location "
                    "for files that may already have been transferred. Fix GADI_REMOTE_ROOT/--remote-root "
                    f"to match {existing.remote_root!r}, or use a different --manifest/--staging-dir if a "
                    "new remote root is genuinely intended."
                )
            return existing
        return self.create(run_id, root_id, topic_id, date_from_utc, date_to_utc, remote_root)

    def save(self, manifest: Manifest, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        try:
            tmp_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
            os.replace(tmp_path, path)  # atomic on the same filesystem
        except OSError as exc:
            raise ManifestError(f"Failed to save manifest to {path}: {exc}") from exc

    @staticmethod
    def find_entry(manifest: Manifest, observation_id: str) -> Optional[ManifestEntry]:
        for entry in manifest.entries:
            if entry.observation.observation_id == observation_id:
                return entry
        return None

    @staticmethod
    def upsert_entry(manifest: Manifest, entry: ManifestEntry) -> Manifest:
        entries = [e for e in manifest.entries if e.observation.observation_id != entry.observation.observation_id]
        entries.append(entry)
        return manifest.model_copy(update={"entries": entries})

    @staticmethod
    def is_fully_transferred(entry: ManifestEntry) -> bool:
        return (
            entry.level0_transfer is not None
            and entry.level0_transfer.state in (TransferState.VERIFIED, TransferState.SKIPPED_EXISTING)
            and entry.level1_transfer is not None
            and entry.level1_transfer.state in (TransferState.VERIFIED, TransferState.SKIPPED_EXISTING)
        )

    @staticmethod
    def has_local_products(entry: ManifestEntry) -> bool:
        return entry.level0 is not None and entry.level1 is not None

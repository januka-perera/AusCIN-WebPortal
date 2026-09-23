"""CLI entry point for the single-site CoastSnap importer.

Three explicit, mutually exclusive run modes — no flag's behaviour is
allowed to be misleading about what it does or doesn't touch:

    --plan-only      (default) Fetch Spotteron metadata only. No image
                      downloads, no Level 0/1 files, no manifest. Makes
                      no Gadi connection.
    --process-local  Fetch records, download images, create Level 0/1
                      files and write the manifest, all locally. Makes
                      no Gadi connection.
    --transfer       Everything --process-local does, plus an SFTP
                      transfer to Gadi. Requires Gadi SFTP configuration
                      (see config.py / .env.example).

    python -m coastsnap_import.cli \\
        --root-id <ROOT_ID> \\
        --date-from 2026-08-01 --date-to 2026-08-31 \\
        --staging-dir ./staging --manifest ./staging/manifests/<ROOT_ID>.json \\
        [--max-images 5] [--remote-root /g/data/qu34/AusCIN/coastsnap-test] \\
        [--plan-only | --process-local | --transfer] [--no-delete]

--date-from/--date-to accept either a bare UTC date (YYYY-MM-DD) or a
full ISO-8601 UTC timestamp (e.g. 2026-08-23T00:00:00Z).

--delete-after-success always exits with an error: deletion is not
implemented in this version, so the flag is rejected rather than
silently accepted and ignored.

--preflight runs environment/connectivity checks only (Python version,
required packages, ExifTool, staging directory, Spotteron API
reachability) and exits — it never contacts Gadi and never downloads
an image. When --preflight is given, --root-id/--date-from/--date-to
are not required:

    python -m coastsnap_import.cli --preflight [--staging-dir ./staging]

See the module docstrings of spotteron_client.py and image_resolver.py
for what is confirmed vs. unconfirmed about the real Spotteron v2.4
schema. This module makes no live network calls when imported (only
when actually run) so it is safe to import from tests.
"""

from __future__ import annotations

import argparse
import itertools
import os
import sys
from datetime import datetime, time, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from . import __version__
from .config import ConfigError, WorkerConfig
from .preflight import (
    PreflightCheck,
    check_bearer_token_configured,
    check_exiftool_available,
    check_exiftool_namespace_config,
    check_exiftool_version,
    check_python_dependencies,
    check_python_version,
    check_spotteron_reachable,
    check_staging_dir_disk_space,
    check_staging_dir_writable,
)
from .image_resolver import (
    ImageUrlResolutionError,
    ImageUrlResolver,
    peek_image_reference_or_url,
    resolve_attribution_permitted,
    resolve_contributor_display_name,
    resolve_latitude,
    resolve_longitude,
    resolve_media_reference,
)
from .manifest import ManifestStore
from .metadata_embedder import MetadataEmbeddingError, MetadataFields, build_embedder
from .models import (
    ManifestEntry,
    ProductLevel,
    SourceObservation,
    SourceSite,
    TransferResult,
    TransferState,
    build_level_relative_path,
    build_manifest_relative_path,
    build_source_record_paths,
)
from .processor import Level0Level1Processor, ProcessingError, compute_sha256, infer_extension
from .sftp_publisher import (
    ParamikoReadBackSftpTransport,
    ParamikoSshSftpOptions,
    ParamikoSshSftpTransport,
    SftpPublisher,
    SftpTransferError,
    SshSftpTransport,
)
from .spotteron_client import (
    SpotteronClient,
    SpotteronClientError,
    SpotteronClientOptions,
    extract_spotted_at_utc,
    filter_by_root_id,
    filter_by_spotted_at,
)


class RunMode(str, Enum):
    PLAN_ONLY = "plan-only"
    PROCESS_LOCAL = "process-local"
    TRANSFER = "transfer"


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="coastsnap-import", description=__doc__)
    # Not required at the argparse level: --preflight needs none of
    # these. main() enforces they're all present for every other mode.
    parser.add_argument("--root-id", default=None, help="Spotteron root/site ID to ingest. Required unless --preflight.")
    parser.add_argument("--date-from", default=None, help="UTC range start: YYYY-MM-DD or full ISO-8601 (e.g. 2026-08-23T00:00:00Z). Required unless --preflight.")
    parser.add_argument("--date-to", default=None, help="UTC range end (inclusive): YYYY-MM-DD or full ISO-8601. Required unless --preflight.")
    parser.add_argument("--max-images", type=int, default=5, help="Maximum observations to process (default: 5).")
    parser.add_argument("--staging-dir", default=None, help="Local staging directory (overrides COASTSNAP_STAGING_DIR).")
    parser.add_argument("--manifest", default=None, help="Manifest JSON path (default: <staging-dir>/manifests/<root-id>.json).")
    parser.add_argument("--remote-root", default=None, help="Remote root on Gadi (overrides GADI_REMOTE_ROOT).")
    parser.add_argument(
        "--preflight", action="store_true",
        help="Check the environment (Python, packages, ExifTool, staging directory, Spotteron reachability) and exit. Never contacts Gadi or downloads an image.",
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--plan-only", action="store_true",
        help="Fetch Spotteron metadata only. No image downloads, no local files, no Gadi connection. This is the default.",
    )
    mode_group.add_argument(
        "--process-local", action="store_true",
        help="Download images and create Level 0/1 files and a manifest locally. No Gadi connection.",
    )
    mode_group.add_argument(
        "--transfer", action="store_true",
        help="Process locally and transfer to Gadi via SFTP. Requires Gadi SFTP configuration.",
    )

    parser.add_argument("--no-delete", action="store_true", help="Explicitly confirm no deletion (this is always the case in this version).")
    parser.add_argument("--delete-after-success", action="store_true", help="Rejected: deletion is not implemented in this version.")
    return parser.parse_args(argv)


def resolve_run_mode(args: argparse.Namespace) -> RunMode:
    if args.transfer:
        return RunMode.TRANSFER
    if args.process_local:
        return RunMode.PROCESS_LOCAL
    return RunMode.PLAN_ONLY


def _parse_boundary(value: str, *, end_of_day: bool) -> datetime:
    try:
        date_only = datetime.strptime(value, "%Y-%m-%d").date()
        return datetime.combine(date_only, time.max if end_of_day else time.min, tzinfo=timezone.utc)
    except ValueError:
        pass

    iso_value = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(iso_value)
    except ValueError as exc:
        raise ConfigError(
            f"{value!r} is not a valid date/time: use YYYY-MM-DD or full ISO-8601 (e.g. 2026-08-23T00:00:00Z)"
        ) from exc
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _parse_utc_date_range(date_from: str, date_to: str) -> tuple[datetime, datetime]:
    start = _parse_boundary(date_from, end_of_day=False)
    end = _parse_boundary(date_to, end_of_day=True)
    if start > end:
        raise ConfigError(f"--date-from ({date_from}) must not be after --date-to ({date_to}).")
    return start, end


def _parse_observation(raw_spot: dict, root_id: str) -> SourceObservation:
    observation_id = str(raw_spot.get("id") or raw_spot.get("observation_id") or "")
    if not observation_id:
        raise ProcessingError(f"Spot record has no usable id: {raw_spot!r}")

    return SourceObservation(
        observation_id=observation_id,
        root_id=root_id,
        spotted_at_utc=extract_spotted_at_utc(raw_spot),
        latitude=resolve_latitude(raw_spot),
        longitude=resolve_longitude(raw_spot),
        image_url=None,  # resolved separately; failures there must not stop parsing
        media_reference=resolve_media_reference(raw_spot),
        contributor_display_name=resolve_contributor_display_name(raw_spot),
        contributor_attribution_permitted=resolve_attribution_permitted(raw_spot),
    )


def _run_plan_only(
    client: SpotteronClient, *, root_id: str, topic_id: int, date_from_utc: datetime, date_to_utc: datetime,
    max_images: int, page_limit: int,
) -> int:
    """Fetches Spotteron metadata only. Never downloads an image, never
    writes a local file, never touches Gadi."""
    count = 0
    try:
        raw_spots = client.iter_spots(topic_id=topic_id, root_id=root_id, page_limit=page_limit)
        site_filtered = filter_by_root_id(raw_spots, root_id)
        date_filtered = filter_by_spotted_at(site_filtered, date_from_utc, date_to_utc)
        for raw_spot in itertools.islice(date_filtered, max_images):
            observation_id = str(raw_spot.get("id") or raw_spot.get("observation_id") or "<unknown>")
            spotted_at = extract_spotted_at_utc(raw_spot)
            image_hint = peek_image_reference_or_url(raw_spot)
            print(f"[plan] root_id={root_id} observation_id={observation_id} spotted_at_utc={spotted_at} image_reference_or_url={image_hint!r}")
            count += 1
    except SpotteronClientError as exc:
        print(f"[fatal] Spotteron request failed: {exc}", file=sys.stderr)
        return 1

    print(f"Plan complete: {count} observation(s) in range (no files written, no Gadi connection made).")
    return 0


def run(
    config: WorkerConfig, *, root_id: str, topic_id: int, date_from_utc: datetime, date_to_utc: datetime,
    max_images: int, manifest_path: Path, mode: RunMode,
) -> int:
    """Runs the pipeline once. Returns a process exit code (0 = no failures)."""
    if mode is RunMode.TRANSFER:
        config.require_transfer_fields()

    client = SpotteronClient(
        SpotteronClientOptions(
            base_url=config.spotteron_base_url,
            api_version=config.spotteron_api_version,
            bearer_token=config.spotteron_bearer_token,
        )
    )

    if mode is RunMode.PLAN_ONLY:
        return _run_plan_only(
            client, root_id=root_id, topic_id=topic_id, date_from_utc=date_from_utc, date_to_utc=date_to_utc,
            max_images=max_images, page_limit=config.spotteron_page_limit,
        )

    manifest_store = ManifestStore()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    manifest = manifest_store.load_or_create(
        manifest_path, run_id=run_id, root_id=root_id, topic_id=topic_id,
        date_from_utc=date_from_utc, date_to_utc=date_to_utc, remote_root=config.remote_root,
    )
    manifest = manifest.model_copy(update={"run_id": run_id, "generated_at_utc": datetime.now(timezone.utc)})

    # Site record: Spotteron does not appear (per current knowledge) to
    # expose a distinct "site" resource separate from a topic/root_id
    # filter on spots, so this is derived only from the ingestion
    # parameters, not fetched. TBC — see final report.
    site = SourceSite(root_id=root_id)
    site_raw_record = {
        "root_id": root_id,
        "topic_id": topic_id,
        "note": (
            "No distinct Spotteron 'site' API resource was assumed to exist for this "
            "proof of concept; this record reflects the ingestion parameters only."
        ),
    }

    image_resolver = ImageUrlResolver(
        image_base_url=config.spotteron_image_base_url,
        bearer_token=config.spotteron_bearer_token,
    )
    processor = Level0Level1Processor(staging_dir=config.staging_dir)
    embedder = build_embedder(config.metadata_backend, exiftool_path=config.exiftool_path)

    transport: Optional[SshSftpTransport] = None
    publisher: Optional[SftpPublisher] = None
    if mode is RunMode.TRANSFER:
        sftp_options = ParamikoSshSftpOptions(
            host=config.gadi_sftp_host,  # type: ignore[arg-type]  # validated by require_transfer_fields()
            port=config.gadi_sftp_port,
            username=config.gadi_sftp_username,  # type: ignore[arg-type]
            private_key_path=config.gadi_sftp_private_key_path,  # type: ignore[arg-type]
        )
        transport = (
            ParamikoReadBackSftpTransport(sftp_options)
            if config.gadi_checksum_strategy == "read-back"
            else ParamikoSshSftpTransport(sftp_options)
        )
        publisher = SftpPublisher(transport, remote_root=config.remote_root)

    processed = 0
    skipped_already_done = 0
    failed = 0

    try:
        raw_spots = client.iter_spots(topic_id=topic_id, root_id=root_id, page_limit=config.spotteron_page_limit)
        site_filtered = filter_by_root_id(raw_spots, root_id)
        date_filtered = filter_by_spotted_at(site_filtered, date_from_utc, date_to_utc)
        limited = itertools.islice(date_filtered, max_images)

        for raw_spot in limited:
            try:
                observation = _parse_observation(raw_spot, root_id)
            except ProcessingError as exc:
                print(f"[error] {exc}", file=sys.stderr)
                failed += 1
                continue

            existing_entry = manifest_store.find_entry(manifest, observation.observation_id)
            if existing_entry is not None and manifest_store.is_fully_transferred(existing_entry):
                print(f"[skip] {observation.observation_id} already ingested and verified.")
                skipped_already_done += 1
                continue

            try:
                entry = _ingest_one(
                    raw_spot=raw_spot,
                    site=site,
                    site_raw_record=site_raw_record,
                    observation=observation,
                    root_id=root_id,
                    processor=processor,
                    image_resolver=image_resolver,
                    embedder=embedder,
                    embedder_backend=config.metadata_backend,
                    staging_dir=config.staging_dir,
                    attempt_transfer=(mode is RunMode.TRANSFER),
                    publisher=publisher,
                    existing_entry=existing_entry,
                )
            except (ProcessingError, ImageUrlResolutionError, MetadataEmbeddingError, SftpTransferError) as exc:
                print(f"[error] {observation.observation_id}: {exc}", file=sys.stderr)
                failed += 1
                continue

            manifest = manifest_store.upsert_entry(manifest, entry)
            manifest_store.save(manifest, manifest_path)  # save after every observation: never lose progress
            processed += 1
    except SpotteronClientError as exc:
        print(f"[fatal] Spotteron request failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if transport is not None:
            transport.close()

    print(
        f"Run complete: processed={processed} skipped_already_done={skipped_already_done} "
        f"failed={failed} manifest={manifest_path}"
    )
    return 1 if failed else 0


def _reusable_local_product(staging_dir: Path, product) -> bool:
    """True if a previously-recorded Level 0/Level 1 product's local file
    still exists on disk and still hashes to its recorded checksum —
    the basis for not redoing work on a rerun."""
    if product is None:
        return False
    candidate_path = staging_dir / product.local_relative_path
    if not candidate_path.exists():
        return False
    return compute_sha256(candidate_path).sha256 == product.checksum.sha256


def _reusable_transfer(transfer: Optional[TransferResult]) -> Optional[TransferResult]:
    if transfer is not None and transfer.state in (TransferState.VERIFIED, TransferState.SKIPPED_EXISTING):
        return transfer
    return None


def _ingest_one(
    *,
    raw_spot: dict,
    site: SourceSite,
    site_raw_record: dict,
    observation: SourceObservation,
    root_id: str,
    processor: Level0Level1Processor,
    image_resolver: ImageUrlResolver,
    embedder,
    embedder_backend: str,
    staging_dir: Path,
    attempt_transfer: bool,
    publisher: Optional[SftpPublisher],
    existing_entry: Optional[ManifestEntry],
) -> ManifestEntry:
    """Processes one observation, reusing any already-verified local
    files/transfers from ``existing_entry`` instead of redoing them —
    this is what makes a rerun idempotent rather than merely safe."""
    assert observation.spotted_at_utc is not None  # guaranteed by date filtering upstream

    # Preserve the full raw record separately — never duplicated into the manifest entry.
    record_ref = build_source_record_paths(root_id, observation.observation_id)
    _write_json(staging_dir / record_ref.site_record_relative_path, site_raw_record)
    _write_json(staging_dir / record_ref.observation_record_relative_path, raw_spot)

    image_url = image_resolver.resolve(raw_spot, observation.observation_id)
    observation = observation.model_copy(update={"image_url": image_url})

    level0_id = f"{observation.observation_id}-L0"
    filename = f"{observation.observation_id}{_infer_suffix(image_url)}"
    level0_remote_relative = build_level_relative_path(ProductLevel.LEVEL_0, root_id, observation.spotted_at_utc, filename)
    level1_remote_relative = build_level_relative_path(ProductLevel.LEVEL_1, root_id, observation.spotted_at_utc, filename)

    # --- Level 0: reuse the existing download if it's still intact. ---
    level0 = existing_entry.level0 if existing_entry else None
    if not _reusable_local_product(staging_dir, level0):
        level0 = processor.download_level0(
            product_id=level0_id,
            observation_id=observation.observation_id,
            image_url=image_url,
            remote_relative_path=level0_remote_relative,
        )

    # --- Level 1: reuse the existing copy+embed if it's still intact. ---
    level1 = existing_entry.level1 if existing_entry else None
    level1_local_path = staging_dir / level1_remote_relative
    if not _reusable_local_product(staging_dir, level1):
        level1_local_path = processor.copy_level0_to_level1_path(level0, level1_remote_relative)
        fields = MetadataFields(
            source_platform="spotteron",
            root_id=root_id,
            observation_id=observation.observation_id,
            media_reference=observation.media_reference,
            captured_at_utc=observation.spotted_at_utc,
            latitude=observation.latitude,
            longitude=observation.longitude,
            contributor_attribution=(
                observation.contributor_display_name if observation.contributor_attribution_permitted else None
            ),
            processing_software="coastsnap-import",
            processing_version=__version__,
        )
        embedded_fields = embedder.embed(level1_local_path, fields)
        level1 = processor.finalize_level1(
            level0=level0,
            level1_local_path=level1_local_path,
            level1_remote_relative_path=level1_remote_relative,
            embedded_metadata_fields=embedded_fields,
            embedder_backend=embedder_backend,
            processing_software="coastsnap-import",
            processing_version=__version__,
        )

    # --- Transfers: reuse anything already verified; (re)attempt only what isn't. ---
    level0_transfer = _reusable_transfer(existing_entry.level0_transfer if existing_entry else None)
    level1_transfer = _reusable_transfer(existing_entry.level1_transfer if existing_entry else None)
    if attempt_transfer:
        assert publisher is not None
        if level0_transfer is None:
            level0_transfer = publisher.publish(
                local_path=staging_dir / level0.local_relative_path,
                remote_relative_path=level0.remote_relative_path,
                local_checksum=level0.checksum,
                product_id=level0.product_id,
            )
        if level1_transfer is None:
            level1_transfer = publisher.publish(
                local_path=level1_local_path,
                remote_relative_path=level1.remote_relative_path,
                local_checksum=level1.checksum,
                product_id=level1.product_id,
            )
    elif level0_transfer is None or level1_transfer is None:
        print(f"[process-local] would transfer {level0.remote_relative_path} and {level1.remote_relative_path} in --transfer mode")

    return ManifestEntry(
        site=site,
        observation=observation,
        source_record_ref=record_ref,
        level0=level0,
        level1=level1,
        level0_transfer=level0_transfer,
        level1_transfer=level1_transfer,
        ingested_at_utc=datetime.now(timezone.utc),
    )


def _infer_suffix(url: str) -> str:
    return infer_extension(url, content_type=None)


def _write_json(path: Path, data: dict) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _report_preflight(checks: list[PreflightCheck]) -> int:
    all_ok = True
    for check in checks:
        status = "PASS" if check.ok else "FAIL"
        print(f"[{status}] {check.name}: {check.detail}")
        all_ok = all_ok and check.ok
    print("Preflight: ALL CHECKS PASSED" if all_ok else "Preflight: ONE OR MORE CHECKS FAILED")
    return 0 if all_ok else 1


def run_preflight(args: argparse.Namespace) -> int:
    """Environment/connectivity checks only. Never contacts Gadi, never
    downloads an image. Reused as-is even when SPOTTERON_BASE_URL or
    COASTSNAP_STAGING_DIR aren't configured yet — those show up as
    failed checks here rather than a crash, since the whole point of
    this command is to surface exactly what's missing before a real run.
    """
    checks: list[PreflightCheck] = [check_python_version()]
    checks.extend(check_python_dependencies())

    exiftool_path = os.environ.get("EXIFTOOL_PATH") or "exiftool"
    checks.append(check_exiftool_available(exiftool_path))
    checks.append(check_exiftool_version(exiftool_path))
    checks.append(check_exiftool_namespace_config(exiftool_path))

    try:
        config = WorkerConfig.from_env(staging_dir=Path(args.staging_dir) if args.staging_dir else None)
    except ConfigError as exc:
        checks.append(PreflightCheck("Worker configuration (SPOTTERON_BASE_URL / COASTSNAP_STAGING_DIR)", False, str(exc)))
        return _report_preflight(checks)

    checks.append(check_staging_dir_writable(config.staging_dir))
    checks.append(check_staging_dir_disk_space(config.staging_dir))
    checks.append(
        check_spotteron_reachable(
            config.spotteron_base_url,
            config.spotteron_api_version,
            config.spotteron_topic_id,
            config.spotteron_bearer_token,
        )
    )
    checks.append(check_bearer_token_configured(config.spotteron_bearer_token))
    return _report_preflight(checks)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    if args.preflight:
        return run_preflight(args)

    if not (args.root_id and args.date_from and args.date_to):
        print(
            "[config error] --root-id, --date-from and --date-to are required unless --preflight is given.",
            file=sys.stderr,
        )
        return 2

    if args.delete_after_success:
        print(
            "[config error] --delete-after-success is rejected: deletion is not implemented in this "
            "version. Remove this flag; no files are ever deleted automatically.",
            file=sys.stderr,
        )
        return 2

    mode = resolve_run_mode(args)

    try:
        date_from_utc, date_to_utc = _parse_utc_date_range(args.date_from, args.date_to)
        config = WorkerConfig.from_env(
            staging_dir=Path(args.staging_dir) if args.staging_dir else None,
            **({"remote_root": args.remote_root} if args.remote_root else {}),
        )
    except ConfigError as exc:
        print(f"[config error] {exc}", file=sys.stderr)
        return 2

    manifest_path = (
        Path(args.manifest)
        if args.manifest
        else config.staging_dir / build_manifest_relative_path(args.root_id)
    )

    try:
        return run(
            config,
            root_id=args.root_id,
            topic_id=config.spotteron_topic_id,
            date_from_utc=date_from_utc,
            date_to_utc=date_to_utc,
            max_images=args.max_images,
            manifest_path=manifest_path,
            mode=mode,
        )
    except ConfigError as exc:
        print(f"[config error] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""CLI/pipeline integration tests. Every Spotteron call is mocked with
`responses`; every SFTP/SSH interaction goes through FakeSshSftpTransport
(see conftest.py) — no test here ever makes a real Spotteron or Gadi call.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import responses

from coastsnap_import import cli
from coastsnap_import.models import TransferState
from tests.conftest import FakeSshSftpTransport, load_fixture

BASE_URL = "https://example-spotteron.test"
SPOTS_URL = f"{BASE_URL}/api/v2.4/spots"
IMAGE_URL_1001 = "https://cdn.example-spotteron.test/images/1001.jpg"
IMAGE_URL_1002 = "https://cdn.example-spotteron.test/images/1002.jpg"
SAMPLE_IMAGE_BYTES = b"\xff\xd8\xff\xe0synthetic-test-bytes-not-a-real-photo"


class FakeEmbedder:
    """Stands in for a real metadata backend at the CLI-integration layer
    — ExifToolXmpEmbedder's own argument-building/error-handling is
    covered directly in test_metadata_embedder.py, so these tests don't
    need a real exiftool binary."""

    def embed(self, file_path: Path, fields) -> list[str]:
        return ["FAKE:AllApprovedFieldsEmbedded"]


@pytest.fixture(autouse=True)
def _fake_embedder(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(cli, "build_embedder", lambda backend, exiftool_path=None: FakeEmbedder())


@pytest.fixture
def base_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    staging_dir = tmp_path / "staging"
    monkeypatch.setenv("SPOTTERON_BASE_URL", BASE_URL)
    monkeypatch.setenv("COASTSNAP_STAGING_DIR", str(staging_dir))
    monkeypatch.delenv("SPOTTERON_BEARER_TOKEN", raising=False)
    return staging_dir


def _mock_spots_page(page1_name="spotteron_page_1.json"):
    # A single registered response is reused for every request to the
    # same URL (verified against the installed `responses` version), so
    # one registration per fixture page is enough even across multiple
    # main() invocations in the same test.
    responses.add(responses.GET, SPOTS_URL, json=load_fixture(page1_name), status=200)


def _mock_image_downloads():
    # Both a HEAD (image-reference validation, see image_resolver.py)
    # and a GET (the actual Level 0 download) are needed per image URL.
    for url in (IMAGE_URL_1001, IMAGE_URL_1002):
        responses.add(responses.HEAD, url, status=200, content_type="image/jpeg")
        responses.add(responses.GET, url, body=SAMPLE_IMAGE_BYTES, status=200, content_type="image/jpeg")


def _no_transport(*_args, **_kwargs):
    raise AssertionError("this mode must never construct an SSH/SFTP transport")


def test_main_missing_config_exits_2_without_network_call(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SPOTTERON_BASE_URL", raising=False)
    monkeypatch.delenv("COASTSNAP_STAGING_DIR", raising=False)
    # Deliberately NOT using @responses.activate / not registering any
    # mock: if the code tried to reach the network it would raise a
    # connection error here rather than returning cleanly.
    exit_code = cli.main(["--root-id", "37", "--date-from", "2026-08-01", "--date-to", "2026-08-31"])
    assert exit_code == 2


def test_preflight_does_not_require_root_id_or_date_range(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SPOTTERON_BASE_URL", raising=False)
    monkeypatch.delenv("COASTSNAP_STAGING_DIR", raising=False)
    # No --root-id/--date-from/--date-to given at all: must not error on
    # missing required args the way every other mode does.
    exit_code = cli.main(["--preflight"])
    assert exit_code == 1  # config genuinely isn't set in this test env, but it didn't crash on missing args


@responses.activate
def test_preflight_passes_and_makes_exactly_one_spotteron_call(base_env: Path, monkeypatch: pytest.MonkeyPatch):
    responses.add(responses.GET, SPOTS_URL, json={"data": []}, status=200)
    monkeypatch.setattr(cli, "ParamikoSshSftpTransport", _no_transport)
    monkeypatch.setattr(cli, "ParamikoReadBackSftpTransport", _no_transport)

    exit_code = cli.main(["--preflight"])

    assert exit_code == 0
    assert len(responses.calls) == 1  # exactly one bounded metadata request, no image, no Gadi
    assert not (base_env / "level-0").exists()  # no pipeline files written


def test_preflight_fails_cleanly_when_config_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.delenv("SPOTTERON_BASE_URL", raising=False)
    monkeypatch.delenv("COASTSNAP_STAGING_DIR", raising=False)
    # Deliberately no @responses.activate: missing SPOTTERON_BASE_URL
    # must be reported as a failed check, not attempted as a request.
    exit_code = cli.main(["--preflight", "--staging-dir", str(tmp_path / "staging")])
    assert exit_code == 1


@responses.activate
def test_plan_only_does_not_write_files(base_env: Path):
    _mock_spots_page()
    # No image HEAD/GET mocks registered: --plan-only must never touch
    # the image-reference resolver's HTTP validation at all.

    exit_code = cli.main(
        ["--root-id", "37", "--date-from", "2026-08-01", "--date-to", "2026-08-31", "--plan-only", "--max-images", "2"]
    )

    assert exit_code == 0
    assert not base_env.exists()  # no Level 0/1, manifest or source-record files anywhere


@responses.activate
def test_default_mode_with_no_flag_is_safe_plan_only(base_env: Path):
    _mock_spots_page()

    exit_code = cli.main(["--root-id", "37", "--date-from", "2026-08-01", "--date-to", "2026-08-31"])

    assert exit_code == 0
    assert not base_env.exists()


@responses.activate
def test_process_local_full_pipeline(base_env: Path, monkeypatch: pytest.MonkeyPatch):
    _mock_spots_page()
    _mock_image_downloads()
    monkeypatch.setattr(cli, "ParamikoSshSftpTransport", _no_transport)
    monkeypatch.setattr(cli, "ParamikoReadBackSftpTransport", _no_transport)

    exit_code = cli.main(
        ["--root-id", "37", "--date-from", "2026-08-01", "--date-to", "2026-08-31", "--process-local", "--max-images", "2"]
    )

    assert exit_code == 0
    level0_file = base_env / "level-0" / "root-37" / "2026" / "08" / "01" / "images" / "1001.jpg"
    level1_file = base_env / "level-1" / "root-37" / "2026" / "08" / "01" / "images" / "1001.jpg"
    assert level0_file.read_bytes() == SAMPLE_IMAGE_BYTES
    assert level1_file.exists()

    manifest = json.loads((base_env / "manifests" / "37.json").read_text())
    assert len(manifest["entries"]) == 2
    assert manifest["entries"][0]["level0_transfer"] is None
    assert manifest["entries"][0]["level1_transfer"] is None

    # Raw records preserved separately, not duplicated into the manifest entry.
    assert (base_env / "metadata" / "source-records" / "observations" / "1001.json").exists()
    assert "raw" not in manifest["entries"][0]["observation"]


@responses.activate
def test_transfer_requires_transfer_configuration(base_env: Path):
    # No GADI_SFTP_* env vars set. require_transfer_fields() must reject
    # this before any Spotteron or SFTP call is made.
    exit_code = cli.main(
        ["--root-id", "37", "--date-from", "2026-08-01", "--date-to", "2026-08-31", "--transfer", "--max-images", "1"]
    )
    assert exit_code == 2


def test_transfer_refuses_production_remote_root_without_confirmation(
    base_env: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # Deliberately no @responses.activate / no mocks registered: the
    # production-root guard must reject this before any Spotteron or
    # SFTP call is made, exactly like a missing-config rejection.
    key_path = tmp_path / "id_ed25519"
    key_path.write_text("not a real key")
    monkeypatch.setenv("GADI_SFTP_HOST", "gadi.example.test")
    monkeypatch.setenv("GADI_SFTP_USERNAME", "ausc-ingest")
    monkeypatch.setenv("GADI_SFTP_PRIVATE_KEY_PATH", str(key_path))
    # GADI_REMOTE_ROOT deliberately left unset: falls back to the
    # default, which is itself under /g/data/qu34 (production).
    monkeypatch.setattr(cli, "ParamikoSshSftpTransport", _no_transport)

    exit_code = cli.main(
        ["--root-id", "37", "--date-from", "2026-08-01", "--date-to", "2026-08-31", "--transfer", "--max-images", "1"]
    )

    assert exit_code == 2


@responses.activate
def test_transfer_allows_production_remote_root_with_explicit_confirmation(
    base_env: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    _mock_spots_page()
    _mock_image_downloads()
    key_path = tmp_path / "id_ed25519"
    key_path.write_text("not a real key")
    monkeypatch.setenv("GADI_SFTP_HOST", "gadi.example.test")
    monkeypatch.setenv("GADI_SFTP_USERNAME", "ausc-ingest")
    monkeypatch.setenv("GADI_SFTP_PRIVATE_KEY_PATH", str(key_path))
    monkeypatch.setattr(cli, "ParamikoSshSftpTransport", lambda options: FakeSshSftpTransport())

    exit_code = cli.main(
        [
            "--root-id", "37", "--date-from", "2026-08-01", "--date-to", "2026-08-31",
            "--transfer", "--max-images", "1", "--confirm-production-remote-root",
        ]
    )

    assert exit_code == 0


def test_transfer_refuses_blank_remote_root(base_env: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    key_path = tmp_path / "id_ed25519"
    key_path.write_text("not a real key")
    monkeypatch.setenv("GADI_SFTP_HOST", "gadi.example.test")
    monkeypatch.setenv("GADI_SFTP_USERNAME", "ausc-ingest")
    monkeypatch.setenv("GADI_SFTP_PRIVATE_KEY_PATH", str(key_path))
    monkeypatch.setenv("GADI_REMOTE_ROOT", "   ")
    monkeypatch.setattr(cli, "ParamikoSshSftpTransport", _no_transport)

    exit_code = cli.main(
        [
            "--root-id", "37", "--date-from", "2026-08-01", "--date-to", "2026-08-31",
            "--transfer", "--max-images", "1", "--confirm-production-remote-root",
        ]
    )

    assert exit_code == 2


@responses.activate
def test_transfer_verifies_and_renames(base_env: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _mock_spots_page()
    _mock_image_downloads()
    key_path = tmp_path / "id_ed25519"
    key_path.write_text("not a real key")
    monkeypatch.setenv("GADI_SFTP_HOST", "gadi.example.test")
    monkeypatch.setenv("GADI_SFTP_USERNAME", "ausc-ingest")
    monkeypatch.setenv("GADI_SFTP_PRIVATE_KEY_PATH", str(key_path))
    monkeypatch.setenv("GADI_REMOTE_ROOT", "/scratch/ausc-ingest/coastsnap-test")  # non-production: no override flag needed

    fake_transport = FakeSshSftpTransport()
    monkeypatch.setattr(cli, "ParamikoSshSftpTransport", lambda options: fake_transport)

    exit_code = cli.main(
        ["--root-id", "37", "--date-from", "2026-08-01", "--date-to", "2026-08-31", "--transfer", "--max-images", "1"]
    )

    assert exit_code == 0
    manifest = json.loads((base_env / "manifests" / "37.json").read_text())
    entry = manifest["entries"][0]
    assert entry["level0_transfer"]["state"] == TransferState.VERIFIED.value
    assert entry["level1_transfer"]["state"] == TransferState.VERIFIED.value
    assert len(fake_transport.renamed) == 2  # level0 + level1
    assert fake_transport.closed is True


@responses.activate
def test_idempotent_rerun_skips_without_reuploading(base_env: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _mock_spots_page()
    _mock_image_downloads()
    key_path = tmp_path / "id_ed25519"
    key_path.write_text("not a real key")
    monkeypatch.setenv("GADI_SFTP_HOST", "gadi.example.test")
    monkeypatch.setenv("GADI_SFTP_USERNAME", "ausc-ingest")
    monkeypatch.setenv("GADI_SFTP_PRIVATE_KEY_PATH", str(key_path))
    monkeypatch.setenv("GADI_REMOTE_ROOT", "/scratch/ausc-ingest/coastsnap-test")  # non-production: no override flag needed

    args = [
        "--root-id", "37", "--date-from", "2026-08-01", "--date-to", "2026-08-31",
        "--transfer", "--max-images", "1",
    ]

    first_transport = FakeSshSftpTransport()
    monkeypatch.setattr(cli, "ParamikoSshSftpTransport", lambda options: first_transport)
    first_exit = cli.main(args)
    assert first_exit == 0
    assert len(first_transport.uploaded) == 2  # level0 + level1 .part uploads

    # Simulate a fresh process/connection on the rerun — a *new*, empty
    # fake transport — the manifest alone must be what prevents redoing
    # the work, not any state left over in the transport.
    second_transport = FakeSshSftpTransport()
    monkeypatch.setattr(cli, "ParamikoSshSftpTransport", lambda options: second_transport)
    second_exit = cli.main(args)

    assert second_exit == 0
    assert second_transport.uploaded == []  # nothing re-uploaded


@responses.activate
def test_corrupted_local_level0_file_triggers_redownload_on_rerun(base_env: Path):
    _mock_spots_page()
    _mock_image_downloads()
    args = [
        "--root-id", "37", "--date-from", "2026-08-01", "--date-to", "2026-08-31",
        "--process-local", "--max-images", "1",
    ]

    assert cli.main(args) == 0
    level0_file = base_env / "level-0" / "root-37" / "2026" / "08" / "01" / "images" / "1001.jpg"
    level1_file = base_env / "level-1" / "root-37" / "2026" / "08" / "01" / "images" / "1001.jpg"
    assert level0_file.read_bytes() == SAMPLE_IMAGE_BYTES

    # Simulate on-disk corruption: the recorded checksum no longer matches.
    level0_file.write_bytes(b"corrupted-on-disk-content")
    level1_file.write_bytes(b"corrupted-on-disk-content")

    assert cli.main(args) == 0  # a clear redownload, not a crash or a silently-reused bad file

    assert level0_file.read_bytes() == SAMPLE_IMAGE_BYTES
    assert level1_file.read_bytes() == SAMPLE_IMAGE_BYTES  # re-copied from the fresh Level 0 and re-embedded


@responses.activate
def test_max_images_limits_processed_count(base_env: Path):
    _mock_spots_page()
    _mock_image_downloads()

    exit_code = cli.main(
        ["--root-id", "37", "--date-from", "2026-08-01", "--date-to", "2026-08-31", "--process-local", "--max-images", "1"]
    )

    assert exit_code == 0
    manifest = json.loads((base_env / "manifests" / "37.json").read_text())
    assert len(manifest["entries"]) == 1


@responses.activate
def test_process_local_handles_real_live_response_shape(base_env: Path):
    """Uses spotteron_live_shape_page.json, modelled directly on a real
    captured Spotteron v2.4 response: envelope has a top-level "meta"
    block, each item has no "type" key, spotted_at is space-separated
    with no timezone marker, root_id is a JSON number, and the page
    contains a SECOND spot from a different (real) root_id — proving
    filter_by_root_id actually excludes cross-site observations rather
    than just filter_by_spotted_at doing all the work.
    """
    responses.add(responses.GET, SPOTS_URL, json=load_fixture("spotteron_live_shape_page.json"), status=200)
    live_image_url = "https://files.spotteron.com/images/spots/000037/2026/09/23/gkckxusp53of89ksukepgv6x6rwx7o7v.jpg"
    responses.add(responses.HEAD, live_image_url, status=200, content_type="image/jpeg")
    responses.add(responses.GET, live_image_url, body=SAMPLE_IMAGE_BYTES, status=200, content_type="image/jpeg")

    exit_code = cli.main(
        [
            "--root-id", "487447", "--date-from", "2026-09-01", "--date-to", "2026-09-30",
            "--process-local", "--max-images", "5",
        ]
    )

    assert exit_code == 0
    manifest = json.loads((base_env / "manifests" / "487447.json").read_text())
    # Only the root_id=487447 spot is present — the root_id=1085047 spot
    # from a different site must never appear, even though it matched
    # topic_id and the date range.
    assert len(manifest["entries"]) == 1
    entry = manifest["entries"][0]
    assert entry["observation"]["observation_id"] == "1351374"
    assert entry["observation"]["root_id"] == "487447"
    # Preserved on the observation itself, not just transiently used for
    # metadata embedding — there is no separate Spotteron "site" record
    # for this to otherwise live on.
    assert entry["observation"]["latitude"] == -26.681912
    assert entry["observation"]["longitude"] == 153.137469
    # Both the raw source value and the normalised UTC value are shown
    # in the manifest — the real format has no timezone marker at all.
    assert entry["observation"]["spotted_at_raw"] == "2026-09-23 14:57:28"
    assert entry["observation"]["spotted_at_utc"] == "2026-09-23T14:57:28Z"
    # No stable "site name" field exists in the real API (fld_01_00001214
    # is a dynamic, per-deployment field, never treated as a schema
    # field — see spotteron_client.py) — site.name stays None, and the
    # directory identity is still deterministic ("root-487447"), not
    # derived from any dynamic field.
    assert entry["site"]["name"] is None
    assert entry["site"]["root_id"] == "487447"
    # Parsed correctly from the real "YYYY-MM-DD HH:MM:SS" (no "T", no
    # timezone) format into the expected date-partitioned path.
    level0_file = base_env / "level-0" / "root-487447" / "2026" / "09" / "23" / "images" / "1351374.jpg"
    assert level0_file.read_bytes() == SAMPLE_IMAGE_BYTES


def test_delete_after_success_is_rejected_before_any_network_call(base_env: Path):
    # Deliberately NOT using @responses.activate / not registering any
    # Spotteron or SFTP mock: if the flag were merely warned-about
    # (its old behaviour) rather than rejected outright, this would
    # attempt a real network call and fail with a connection error
    # instead of the expected clean exit 2.
    exit_code = cli.main(
        [
            "--root-id", "37", "--date-from", "2026-08-01", "--date-to", "2026-08-31",
            "--process-local", "--max-images", "1", "--delete-after-success",
        ]
    )

    assert exit_code == 2
    assert not base_env.exists()


def test_parse_args_defaults():
    args = cli.parse_args(["--root-id", "37", "--date-from", "2026-08-01", "--date-to", "2026-08-31"])
    assert args.max_images == 5
    assert args.no_delete is False
    assert args.delete_after_success is False
    assert args.plan_only is False
    assert args.process_local is False
    assert args.transfer is False
    assert cli.resolve_run_mode(args) is cli.RunMode.PLAN_ONLY


def test_parse_args_rejects_multiple_modes():
    with pytest.raises(SystemExit):
        cli.parse_args(
            ["--root-id", "37", "--date-from", "2026-08-01", "--date-to", "2026-08-31", "--plan-only", "--transfer"]
        )


def test_parse_utc_date_range_rejects_reversed_range():
    from coastsnap_import.config import ConfigError

    with pytest.raises(ConfigError):
        cli._parse_utc_date_range("2026-08-31", "2026-08-01")


def test_parse_utc_date_range_rejects_bad_format():
    from coastsnap_import.config import ConfigError

    with pytest.raises(ConfigError):
        cli._parse_utc_date_range("31-08-2026", "2026-08-31")


def test_parse_utc_date_range_spans_full_days():
    start, end = cli._parse_utc_date_range("2026-08-01", "2026-08-01")
    assert start.hour == 0 and start.minute == 0
    assert end.hour == 23 and end.minute == 59


def test_parse_utc_date_range_accepts_full_iso8601_with_z_suffix():
    start, end = cli._parse_utc_date_range("2026-08-23T00:00:00Z", "2026-09-23T00:00:00Z")
    assert start == datetime(2026, 8, 23, 0, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 9, 23, 0, 0, 0, tzinfo=timezone.utc)


def test_parse_utc_date_range_accepts_mixed_bare_date_and_iso8601():
    start, end = cli._parse_utc_date_range("2026-08-01", "2026-09-23T12:30:00Z")
    assert start == datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 9, 23, 12, 30, 0, tzinfo=timezone.utc)

"""CLI/pipeline integration tests. Every Spotteron call is mocked with
`responses`; every SFTP/SSH interaction goes through FakeSshSftpTransport
(see conftest.py) — no test here ever makes a real Spotteron or Gadi call.
"""

from __future__ import annotations

import json
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
    # The default page limit (50) is far larger than this 2-item fixture
    # page, so pagination always terminates after exactly one request
    # (see test_spotteron_client.py for dedicated multi-page tests) —
    # only one response needs registering per main() invocation.
    responses.add(responses.GET, SPOTS_URL, json=load_fixture(page1_name), status=200)


def _mock_image_downloads():
    responses.add(responses.GET, IMAGE_URL_1001, body=SAMPLE_IMAGE_BYTES, status=200, content_type="image/jpeg")
    responses.add(responses.GET, IMAGE_URL_1002, body=SAMPLE_IMAGE_BYTES, status=200, content_type="image/jpeg")


def test_main_missing_config_exits_2_without_network_call(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SPOTTERON_BASE_URL", raising=False)
    monkeypatch.delenv("COASTSNAP_STAGING_DIR", raising=False)
    # Deliberately NOT using @responses.activate / not registering any
    # mock: if the code tried to reach the network it would raise a
    # connection error here rather than returning cleanly.
    exit_code = cli.main(["--root-id", "37", "--date-from", "2026-08-01", "--date-to", "2026-08-31"])
    assert exit_code == 2


@responses.activate
def test_dry_run_full_local_pipeline(base_env: Path, monkeypatch: pytest.MonkeyPatch):
    _mock_spots_page()
    _mock_image_downloads()
    monkeypatch.setattr(
        cli,
        "ParamikoSshSftpTransport",
        lambda options: (_ for _ in ()).throw(AssertionError("dry-run must never construct a transport")),
    )

    exit_code = cli.main(
        ["--root-id", "37", "--date-from", "2026-08-01", "--date-to", "2026-08-31", "--dry-run", "--max-images", "2"]
    )

    assert exit_code == 0
    level0_file = base_env / "level-0" / "37" / "2026" / "08" / "01" / "images" / "1001.jpg"
    level1_file = base_env / "level-1" / "37" / "2026" / "08" / "01" / "images" / "1001.jpg"
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
def test_real_transfer_verifies_and_renames(base_env: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _mock_spots_page()
    _mock_image_downloads()
    key_path = tmp_path / "id_ed25519"
    key_path.write_text("not a real key")
    monkeypatch.setenv("GADI_SFTP_HOST", "gadi.example.test")
    monkeypatch.setenv("GADI_SFTP_USERNAME", "ausc-ingest")
    monkeypatch.setenv("GADI_SFTP_PRIVATE_KEY_PATH", str(key_path))

    fake_transport = FakeSshSftpTransport()
    monkeypatch.setattr(cli, "ParamikoSshSftpTransport", lambda options: fake_transport)

    exit_code = cli.main(
        ["--root-id", "37", "--date-from", "2026-08-01", "--date-to", "2026-08-31", "--max-images", "1"]
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
    _mock_spots_page()  # registered twice: one page-set consumed per main() call
    _mock_image_downloads()
    key_path = tmp_path / "id_ed25519"
    key_path.write_text("not a real key")
    monkeypatch.setenv("GADI_SFTP_HOST", "gadi.example.test")
    monkeypatch.setenv("GADI_SFTP_USERNAME", "ausc-ingest")
    monkeypatch.setenv("GADI_SFTP_PRIVATE_KEY_PATH", str(key_path))

    args = ["--root-id", "37", "--date-from", "2026-08-01", "--date-to", "2026-08-31", "--max-images", "1"]

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
def test_max_images_limits_processed_count(base_env: Path):
    _mock_spots_page()
    _mock_image_downloads()

    exit_code = cli.main(
        ["--root-id", "37", "--date-from", "2026-08-01", "--date-to", "2026-08-31", "--dry-run", "--max-images", "1"]
    )

    assert exit_code == 0
    manifest = json.loads((base_env / "manifests" / "37.json").read_text())
    assert len(manifest["entries"]) == 1


@responses.activate
def test_delete_after_success_does_not_delete_anything(
    base_env: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
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
            "--max-images", "1", "--delete-after-success",
        ]
    )

    assert exit_code == 0
    assert "not implemented" in capsys.readouterr().err.lower()
    level0_file = base_env / "level-0" / "37" / "2026" / "08" / "01" / "images" / "1001.jpg"
    assert level0_file.exists()  # never deleted


def test_parse_args_defaults():
    args = cli.parse_args(["--root-id", "37", "--date-from", "2026-08-01", "--date-to", "2026-08-31"])
    assert args.max_images == 5
    assert args.no_delete is False
    assert args.delete_after_success is False
    assert args.dry_run is False


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

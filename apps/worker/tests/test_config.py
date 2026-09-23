from __future__ import annotations

from pathlib import Path

import pytest

from coastsnap_import.config import ConfigError, WorkerConfig


def test_from_env_builds_config_with_defaults(tmp_path: Path):
    env = {
        "SPOTTERON_BASE_URL": "https://example-spotteron.test",
        "COASTSNAP_STAGING_DIR": str(tmp_path),
    }
    config = WorkerConfig.from_env(env=env)
    assert config.spotteron_base_url == "https://example-spotteron.test"
    assert config.spotteron_api_version == "v2.4"
    assert config.spotteron_topic_id == 37
    assert config.spotteron_bearer_token is None
    assert config.remote_root == "/g/data/qu34/AusCIN/coastsnap-test"
    assert config.staging_dir == tmp_path


def test_from_env_missing_base_url_raises(tmp_path: Path):
    with pytest.raises(ConfigError, match="SPOTTERON_BASE_URL"):
        WorkerConfig.from_env(env={"COASTSNAP_STAGING_DIR": str(tmp_path)})


def test_from_env_missing_staging_dir_raises():
    with pytest.raises(ConfigError, match="COASTSNAP_STAGING_DIR"):
        WorkerConfig.from_env(env={"SPOTTERON_BASE_URL": "https://example-spotteron.test"})


def test_from_env_rejects_non_http_base_url(tmp_path: Path):
    with pytest.raises(ConfigError):
        WorkerConfig.from_env(
            env={"SPOTTERON_BASE_URL": "ftp://example-spotteron.test", "COASTSNAP_STAGING_DIR": str(tmp_path)}
        )


def test_cli_overrides_take_precedence_over_env(tmp_path: Path):
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    config = WorkerConfig.from_env(
        env={"SPOTTERON_BASE_URL": "https://example-spotteron.test", "COASTSNAP_STAGING_DIR": str(tmp_path)},
        staging_dir=other_dir,
    )
    assert config.staging_dir == other_dir


def test_repr_never_leaks_bearer_token(tmp_path: Path):
    config = WorkerConfig.from_env(
        env={
            "SPOTTERON_BASE_URL": "https://example-spotteron.test",
            "COASTSNAP_STAGING_DIR": str(tmp_path),
            "SPOTTERON_BEARER_TOKEN": "super-secret-value-must-not-appear",
        }
    )
    rendered = repr(config)
    assert "super-secret-value-must-not-appear" not in rendered
    assert "<redacted>" in rendered
    assert "super-secret-value-must-not-appear" not in str(config)


def test_require_transfer_fields_raises_when_missing(sample_config: WorkerConfig):
    with pytest.raises(ConfigError, match="gadi_sftp_host"):
        sample_config.require_transfer_fields()


def test_require_transfer_fields_passes_when_present(tmp_path: Path):
    key_path = tmp_path / "id_ed25519"
    key_path.write_text("not a real key, just needs to exist")
    config = WorkerConfig.from_env(
        env={"SPOTTERON_BASE_URL": "https://example-spotteron.test", "COASTSNAP_STAGING_DIR": str(tmp_path)},
        gadi_sftp_host="gadi.example.test",
        gadi_sftp_username="ausc-ingest",
        gadi_sftp_private_key_path=key_path,
    )
    config.require_transfer_fields()  # must not raise


def test_require_transfer_fields_raises_when_key_file_missing(tmp_path: Path):
    config = WorkerConfig.from_env(
        env={"SPOTTERON_BASE_URL": "https://example-spotteron.test", "COASTSNAP_STAGING_DIR": str(tmp_path)},
        gadi_sftp_host="gadi.example.test",
        gadi_sftp_username="ausc-ingest",
        gadi_sftp_private_key_path=tmp_path / "does-not-exist",
    )
    with pytest.raises(ConfigError, match="does not exist"):
        config.require_transfer_fields()

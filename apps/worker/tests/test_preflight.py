"""Preflight check tests. subprocess/requests are mocked throughout —
no test here ever runs a real exiftool binary or makes a real network
call. See test_cli.py for the --preflight CLI-integration tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import responses

from coastsnap_import.preflight import (
    check_bearer_token_configured,
    check_exiftool_available,
    check_exiftool_namespace_config,
    check_exiftool_version,
    check_gadi_configuration_status,
    check_python_dependencies,
    check_python_version,
    check_spotteron_reachable,
    check_staging_dir_disk_space,
    check_staging_dir_writable,
)

BASE_URL = "https://example-spotteron.test"
SPOTS_URL = f"{BASE_URL}/api/v2.4/spots"


def test_python_version_passes_on_supported_version(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sys, "version_info", (3, 12, 1, "final", 0))
    check = check_python_version(minimum=(3, 11))
    assert check.ok is True


def test_python_version_fails_below_minimum(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sys, "version_info", (3, 9, 0, "final", 0))
    check = check_python_version(minimum=(3, 11))
    assert check.ok is False


def test_python_dependencies_reports_installed_versions():
    checks = check_python_dependencies(("pydantic", "requests", "paramiko"))
    assert all(c.ok for c in checks)
    assert all("installed" in c.detail for c in checks)


def test_python_dependencies_reports_missing_package():
    checks = check_python_dependencies(("this-package-does-not-exist",))
    assert checks[0].ok is False
    assert "not installed" in checks[0].detail


def test_exiftool_available_when_on_path(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/exiftool")
    check = check_exiftool_available("exiftool")
    assert check.ok is True
    assert check.detail == "/usr/bin/exiftool"


def test_exiftool_unavailable_when_not_found(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    check = check_exiftool_available("exiftool-does-not-exist")
    assert check.ok is False


@patch("coastsnap_import.preflight.subprocess.run")
def test_exiftool_version_success(mock_run: MagicMock):
    mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="13.57\n", stderr="")
    check = check_exiftool_version("exiftool")
    assert check.ok is True
    assert check.detail == "13.57"


@patch("coastsnap_import.preflight.subprocess.run", side_effect=FileNotFoundError("no such file"))
def test_exiftool_version_fails_when_binary_missing(_mock_run: MagicMock):
    check = check_exiftool_version("exiftool-does-not-exist")
    assert check.ok is False


@patch("coastsnap_import.preflight.subprocess.run")
def test_exiftool_namespace_config_loads_ok(mock_run: MagicMock, tmp_path: Path):
    config_path = tmp_path / "auscin.config"
    config_path.write_text("1;", encoding="utf-8")
    mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="13.57\n", stderr="")

    check = check_exiftool_namespace_config("exiftool", config_path=config_path)

    assert check.ok is True
    called_args = mock_run.call_args[0][0]
    assert "-config" in called_args
    assert str(config_path) in called_args


def test_exiftool_namespace_config_fails_when_file_missing(tmp_path: Path):
    check = check_exiftool_namespace_config("exiftool", config_path=tmp_path / "does-not-exist.config")
    assert check.ok is False
    assert "not found" in check.detail


@patch("coastsnap_import.preflight.subprocess.run")
def test_exiftool_namespace_config_fails_on_perl_syntax_error(mock_run: MagicMock, tmp_path: Path):
    config_path = tmp_path / "auscin.config"
    config_path.write_text("this is not valid perl {{{", encoding="utf-8")
    mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="Error: syntax error")

    check = check_exiftool_namespace_config("exiftool", config_path=config_path)

    assert check.ok is False
    assert "syntax error" in check.detail.lower() or "failed to load" in check.detail.lower()


def test_staging_dir_writable_creates_and_cleans_up_probe_file(tmp_path: Path):
    staging_dir = tmp_path / "staging"
    check = check_staging_dir_writable(staging_dir)
    assert check.ok is True
    assert staging_dir.exists()
    assert list(staging_dir.iterdir()) == []  # probe file cleaned up, nothing left behind


def test_staging_dir_writable_fails_when_path_is_a_file(tmp_path: Path):
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("x", encoding="utf-8")
    check = check_staging_dir_writable(blocked / "staging")
    assert check.ok is False


def test_staging_dir_disk_space_reports_free_bytes(tmp_path: Path):
    check = check_staging_dir_disk_space(tmp_path, minimum_free_bytes=0)
    assert check.ok is True
    assert "MB free" in check.detail


def test_staging_dir_disk_space_fails_below_minimum(tmp_path: Path):
    check = check_staging_dir_disk_space(tmp_path, minimum_free_bytes=10**18)  # absurdly high floor
    assert check.ok is False


@responses.activate
def test_spotteron_reachable_ok_on_200():
    responses.add(responses.GET, SPOTS_URL, json={"data": []}, status=200)
    check = check_spotteron_reachable(BASE_URL, "v2.4", 37, bearer_token=None)
    assert check.ok is True
    assert "200" in check.detail


@responses.activate
def test_spotteron_reachable_still_ok_on_4xx():
    # A 4xx still proves the host answers as an API; only a network
    # failure or a 5xx should fail this check.
    responses.add(responses.GET, SPOTS_URL, status=401)
    check = check_spotteron_reachable(BASE_URL, "v2.4", 37, bearer_token=None)
    assert check.ok is True


@responses.activate
def test_spotteron_reachable_fails_on_5xx():
    responses.add(responses.GET, SPOTS_URL, status=503)
    check = check_spotteron_reachable(BASE_URL, "v2.4", 37, bearer_token=None)
    assert check.ok is False


def test_spotteron_reachable_fails_on_connection_error():
    # Deliberately no @responses.activate / no mock: a real, unmocked
    # request to an unroutable host will raise a ConnectionError.
    check = check_spotteron_reachable("https://this-host-does-not-resolve.invalid", "v2.4", 37, bearer_token=None, timeout_seconds=2)
    assert check.ok is False


@responses.activate
def test_spotteron_reachable_never_downloads_an_image_or_contacts_gadi():
    responses.add(responses.GET, SPOTS_URL, json={"data": []}, status=200)
    check_spotteron_reachable(BASE_URL, "v2.4", 37, bearer_token=None)
    assert len(responses.calls) == 1
    assert responses.calls[0].request.url.startswith(SPOTS_URL)


def test_bearer_token_check_never_prints_the_token_value():
    check = check_bearer_token_configured("super-secret-token-value")
    assert check.ok is True
    assert "super-secret-token-value" not in check.detail


def test_bearer_token_check_passes_when_not_set():
    check = check_bearer_token_configured(None)
    assert check.ok is True
    assert "not set" in check.detail


def test_gadi_configuration_status_is_informational_when_absent():
    check = check_gadi_configuration_status(None, None)
    assert check.ok is True
    assert "absent" in check.detail


def test_gadi_configuration_status_is_informational_when_present():
    # Presence must never fail the check: --process-local ignores Gadi
    # config entirely regardless of whether it happens to be set.
    check = check_gadi_configuration_status("gadi.example.test", "ausc-ingest")
    assert check.ok is True
    assert "present" in check.detail
    assert "gadi.example.test" not in check.detail  # host value itself isn't echoed back, just presence

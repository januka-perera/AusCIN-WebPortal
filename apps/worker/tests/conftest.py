"""Shared test fixtures.

No test in this suite makes a real network call to Spotteron or Gadi:
HTTP is mocked with `responses`, and SFTP/SSH is faked with an
in-memory object implementing SshSftpTransport (see
tests/test_sftp_publisher.py and tests/test_cli.py).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from coastsnap_import.config import WorkerConfig

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


class FakeSshSftpTransport:
    """A complete in-memory stand-in for SshSftpTransport. No test using
    this ever opens a real network/SSH connection — see test_sftp_publisher.py
    and test_cli.py."""

    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.uploaded: list[str] = []
        self.renamed: list[tuple[str, str]] = []
        self.closed = False
        self.corrupt_checksum_for: set[str] = set()

    def upload_file(self, local_path: Path, remote_path: str) -> None:
        self.files[remote_path] = Path(local_path).read_bytes()
        self.uploaded.append(remote_path)

    def exec_sha256sum(self, remote_path: str):
        if remote_path not in self.files:
            return None
        if remote_path in self.corrupt_checksum_for:
            return "0" * 64
        return hashlib.sha256(self.files[remote_path]).hexdigest()

    def rename(self, remote_from: str, remote_to: str) -> None:
        self.files[remote_to] = self.files.pop(remote_from)
        self.renamed.append((remote_from, remote_to))

    def remote_exists(self, remote_path: str) -> bool:
        return remote_path in self.files

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def staging_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "staging"
    directory.mkdir()
    return directory


@pytest.fixture
def sample_config(staging_dir: Path) -> WorkerConfig:
    return WorkerConfig(
        spotteron_base_url="https://example-spotteron.test",
        spotteron_api_version="v2.4",
        spotteron_topic_id=37,
        spotteron_page_limit=2,
        staging_dir=staging_dir,
    )

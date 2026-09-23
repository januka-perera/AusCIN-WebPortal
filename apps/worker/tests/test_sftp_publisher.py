"""SFTP publisher tests. No real network/SSH connection is ever made —
FakeSshSftpTransport below is a complete in-memory stand-in for
SshSftpTransport, used everywhere a transport is needed."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest

from coastsnap_import.models import ChecksumInfo, TransferState
from coastsnap_import.sftp_publisher import RemoteConflictError, SftpPublisher
from tests.conftest import FakeSshSftpTransport


def _checksum(data: bytes) -> ChecksumInfo:
    return ChecksumInfo(sha256=hashlib.sha256(data).hexdigest(), computed_at_utc=datetime.now(timezone.utc))


def test_publish_happy_path_uploads_part_then_renames(tmp_path: Path):
    local = tmp_path / "1001.jpg"
    local.write_bytes(b"hello world")
    transport = FakeSshSftpTransport()
    publisher = SftpPublisher(transport, remote_root="/g/data/qu34/AusCIN/coastsnap-test")

    result = publisher.publish(local, "level-0/S/2026/08/01/images/1001.jpg", _checksum(b"hello world"), "1001-L0")

    assert result.state == TransferState.VERIFIED
    assert transport.uploaded == ["/g/data/qu34/AusCIN/coastsnap-test/level-0/S/2026/08/01/images/1001.jpg.part"]
    assert transport.renamed == [
        (
            "/g/data/qu34/AusCIN/coastsnap-test/level-0/S/2026/08/01/images/1001.jpg.part",
            "/g/data/qu34/AusCIN/coastsnap-test/level-0/S/2026/08/01/images/1001.jpg",
        )
    ]
    assert result.remote_checksum == hashlib.sha256(b"hello world").hexdigest()


def test_checksum_mismatch_on_part_never_renames(tmp_path: Path):
    local = tmp_path / "1001.jpg"
    local.write_bytes(b"hello world")
    transport = FakeSshSftpTransport()
    remote_part = "/g/data/qu34/AusCIN/coastsnap-test/level-0/S/2026/08/01/images/1001.jpg.part"
    transport.corrupt_checksum_for.add(remote_part)
    publisher = SftpPublisher(transport, remote_root="/g/data/qu34/AusCIN/coastsnap-test")

    result = publisher.publish(local, "level-0/S/2026/08/01/images/1001.jpg", _checksum(b"hello world"), "1001-L0")

    assert result.state == TransferState.FAILED
    assert "mismatch" in result.error_message.lower()
    assert transport.renamed == []  # never renamed on mismatch


def test_conflicting_existing_file_raises_and_does_not_upload(tmp_path: Path):
    local = tmp_path / "1001.jpg"
    local.write_bytes(b"hello world")
    transport = FakeSshSftpTransport()
    final = "/g/data/qu34/AusCIN/coastsnap-test/level-0/S/2026/08/01/images/1001.jpg"
    transport.files[final] = b"different pre-existing content"
    publisher = SftpPublisher(transport, remote_root="/g/data/qu34/AusCIN/coastsnap-test")

    with pytest.raises(RemoteConflictError):
        publisher.publish(local, "level-0/S/2026/08/01/images/1001.jpg", _checksum(b"hello world"), "1001-L0")

    assert transport.uploaded == []  # never attempted an upload


def test_existing_file_with_matching_checksum_is_skipped(tmp_path: Path):
    local = tmp_path / "1001.jpg"
    local.write_bytes(b"hello world")
    transport = FakeSshSftpTransport()
    final = "/g/data/qu34/AusCIN/coastsnap-test/level-0/S/2026/08/01/images/1001.jpg"
    transport.files[final] = b"hello world"  # already correct
    publisher = SftpPublisher(transport, remote_root="/g/data/qu34/AusCIN/coastsnap-test")

    result = publisher.publish(local, "level-0/S/2026/08/01/images/1001.jpg", _checksum(b"hello world"), "1001-L0")

    assert result.state == TransferState.SKIPPED_EXISTING
    assert transport.uploaded == []


def test_idempotent_rerun_second_publish_skips(tmp_path: Path):
    local = tmp_path / "1001.jpg"
    local.write_bytes(b"hello world")
    transport = FakeSshSftpTransport()
    publisher = SftpPublisher(transport, remote_root="/g/data/qu34/AusCIN/coastsnap-test")

    first = publisher.publish(local, "level-0/S/2026/08/01/images/1001.jpg", _checksum(b"hello world"), "1001-L0")
    second = publisher.publish(local, "level-0/S/2026/08/01/images/1001.jpg", _checksum(b"hello world"), "1001-L0")

    assert first.state == TransferState.VERIFIED
    assert second.state == TransferState.SKIPPED_EXISTING
    assert transport.uploaded == [
        "/g/data/qu34/AusCIN/coastsnap-test/level-0/S/2026/08/01/images/1001.jpg.part"
    ]  # only uploaded once


def test_final_checksum_mismatch_after_rename_is_reported_failed(tmp_path: Path):
    local = tmp_path / "1001.jpg"
    local.write_bytes(b"hello world")
    transport = FakeSshSftpTransport()
    final = "/g/data/qu34/AusCIN/coastsnap-test/level-0/S/2026/08/01/images/1001.jpg"
    transport.corrupt_checksum_for.add(final)  # only the FINAL path reports a wrong checksum
    publisher = SftpPublisher(transport, remote_root="/g/data/qu34/AusCIN/coastsnap-test")

    result = publisher.publish(local, "level-0/S/2026/08/01/images/1001.jpg", _checksum(b"hello world"), "1001-L0")

    assert result.state == TransferState.FAILED
    assert "after rename" in result.error_message.lower()


def test_publisher_never_deletes_anything():
    """Structural guarantee: there is no delete/remove method on SftpPublisher at all."""
    assert not hasattr(SftpPublisher, "delete")
    assert not hasattr(SftpPublisher, "remove")

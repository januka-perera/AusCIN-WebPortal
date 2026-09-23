"""Transport-level tests for both Gadi checksum-verification strategies
("ssh-exec" and "read-back"), with `paramiko` itself faked out — no
real SSH/SFTP connection is ever attempted, and Gadi is never contacted.

FakeSshClient/FakeSftpClient below are a minimal in-memory stand-in for
paramiko's SSHClient/SFTPClient, just enough to exercise
ParamikoSshSftpTransport and ParamikoReadBackSftpTransport end to end.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import paramiko
import pytest

from coastsnap_import.sftp_publisher import (
    ParamikoReadBackSftpTransport,
    ParamikoSshSftpOptions,
    ParamikoSshSftpTransport,
)


class _FakeSftpFile:
    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            chunk, self._pos = self._data[self._pos:], len(self._data)
            return chunk
        chunk = self._data[self._pos : self._pos + size]
        self._pos += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc_info) -> bool:
        return False


class FakeSftpClient:
    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.dirs: set[str] = set()
        self.mkdir_calls: list[str] = []
        self.closed = False

    def put(self, local_path: str, remote_path: str) -> None:
        self.files[remote_path] = Path(local_path).read_bytes()

    def stat(self, path: str):
        if path in self.files or path in self.dirs:
            return object()
        raise FileNotFoundError(path)

    def mkdir(self, path: str) -> None:
        self.mkdir_calls.append(path)
        self.dirs.add(path)

    def posix_rename(self, remote_from: str, remote_to: str) -> None:
        self.files[remote_to] = self.files.pop(remote_from)

    def open(self, path: str, mode: str = "rb"):
        return _FakeSftpFile(self.files[path])

    def close(self) -> None:
        self.closed = True


class _FakeStream:
    def __init__(self, text: str):
        self._data = text.encode("utf-8")

    def read(self):
        return self._data


class FakeSshClient:
    """Records connect() kwargs so tests can assert SSH-key-only auth."""

    instances: list["FakeSshClient"] = []

    def __init__(self):
        self.connect_kwargs: dict = {}
        self.host_key_policy = None
        self.sftp = FakeSftpClient()
        self.closed = False
        FakeSshClient.instances.append(self)

    def set_missing_host_key_policy(self, policy) -> None:
        self.host_key_policy = policy

    def load_system_host_keys(self) -> None:
        pass

    def connect(self, **kwargs) -> None:
        self.connect_kwargs = kwargs

    def open_sftp(self):
        return self.sftp

    def exec_command(self, command: str, timeout=None):
        # Real command shape: "sha256sum -- '<path>' 2>/dev/null || echo MISSING"
        path = command.split("'")[1]
        data = self.sftp.files.get(path)
        output = f"{hashlib.sha256(data).hexdigest()}  {path}\n" if data is not None else "MISSING\n"
        return _FakeStream(""), _FakeStream(output), _FakeStream("")

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def _reset_fake_instances():
    FakeSshClient.instances.clear()
    yield
    FakeSshClient.instances.clear()


@pytest.fixture(autouse=True)
def _fake_paramiko_ssh_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(paramiko, "SSHClient", FakeSshClient)


def _options(tmp_path: Path) -> ParamikoSshSftpOptions:
    key_path = tmp_path / "id_ed25519"
    key_path.write_text("not a real key")
    return ParamikoSshSftpOptions(host="gadi.example.test", port=22, username="ausc-ingest", private_key_path=key_path)


def test_connect_uses_ssh_key_only_no_password(tmp_path: Path):
    options = _options(tmp_path)
    transport = ParamikoSshSftpTransport(options)

    kwargs = FakeSshClient.instances[0].connect_kwargs
    assert kwargs["key_filename"] == str(options.private_key_path)
    assert "password" not in kwargs
    assert kwargs["look_for_keys"] is False
    assert kwargs["allow_agent"] is False
    transport.close()


def test_ssh_exec_checksum_strategy_runs_sha256sum_over_exec_command(tmp_path: Path):
    transport = ParamikoSshSftpTransport(_options(tmp_path))
    local_file = tmp_path / "1001.jpg"
    local_file.write_bytes(b"hello world")

    transport.upload_file(local_file, "/remote/level-0/1001.jpg.part")
    checksum = transport.exec_sha256sum("/remote/level-0/1001.jpg.part")

    assert checksum == hashlib.sha256(b"hello world").hexdigest()
    assert transport.exec_sha256sum("/remote/does-not-exist") is None
    transport.close()


def test_read_back_checksum_strategy_never_uses_exec_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    transport = ParamikoReadBackSftpTransport(_options(tmp_path))
    local_file = tmp_path / "1001.jpg"
    local_file.write_bytes(b"hello world")
    transport.upload_file(local_file, "/remote/level-0/1001.jpg.part")

    def _no_exec_command(*_args, **_kwargs):
        raise AssertionError("read-back strategy must never call exec_command")

    monkeypatch.setattr(FakeSshClient.instances[0], "exec_command", _no_exec_command)

    checksum = transport.exec_sha256sum("/remote/level-0/1001.jpg.part")

    assert checksum == hashlib.sha256(b"hello world").hexdigest()
    assert transport.exec_sha256sum("/remote/does-not-exist") is None
    transport.close()


def test_both_strategies_agree_on_the_same_checksum(tmp_path: Path):
    """Both checksum strategies must be interchangeable from the
    publisher's point of view: same upload, same resulting digest."""
    ssh_exec_transport = ParamikoSshSftpTransport(_options(tmp_path))
    local_file = tmp_path / "1001.jpg"
    local_file.write_bytes(b"cross-strategy-consistency-check")
    ssh_exec_transport.upload_file(local_file, "/remote/1001.jpg.part")
    ssh_exec_checksum = ssh_exec_transport.exec_sha256sum("/remote/1001.jpg.part")
    ssh_exec_transport.close()

    read_back_transport = ParamikoReadBackSftpTransport(_options(tmp_path))
    read_back_transport.upload_file(local_file, "/remote/1001.jpg.part")
    read_back_checksum = read_back_transport.exec_sha256sum("/remote/1001.jpg.part")
    read_back_transport.close()

    assert ssh_exec_checksum == read_back_checksum == hashlib.sha256(b"cross-strategy-consistency-check").hexdigest()


def test_upload_then_rename_then_remote_exists(tmp_path: Path):
    transport = ParamikoSshSftpTransport(_options(tmp_path))
    local_file = tmp_path / "1001.jpg"
    local_file.write_bytes(b"data")
    transport.upload_file(local_file, "/remote/1001.jpg.part")

    assert transport.remote_exists("/remote/1001.jpg.part") is True
    assert transport.remote_exists("/remote/1001.jpg") is False

    transport.rename("/remote/1001.jpg.part", "/remote/1001.jpg")

    assert transport.remote_exists("/remote/1001.jpg") is True
    assert transport.remote_exists("/remote/1001.jpg.part") is False
    transport.close()


def test_upload_creates_missing_parent_directories(tmp_path: Path):
    transport = ParamikoSshSftpTransport(_options(tmp_path))
    local_file = tmp_path / "1001.jpg"
    local_file.write_bytes(b"data")

    transport.upload_file(local_file, "/remote/level-0/S/2026/08/01/images/1001.jpg.part")

    sftp = FakeSshClient.instances[0].sftp
    assert sftp.files["/remote/level-0/S/2026/08/01/images/1001.jpg.part"] == b"data"
    assert len(sftp.mkdir_calls) > 0  # parent directories were created, not assumed to pre-exist
    transport.close()


def test_close_closes_both_sftp_and_ssh_session(tmp_path: Path):
    transport = ParamikoSshSftpTransport(_options(tmp_path))
    fake_client = FakeSshClient.instances[0]

    transport.close()

    assert fake_client.sftp.closed is True
    assert fake_client.closed is True

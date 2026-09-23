"""SFTP transfer to Gadi, with SSH-exec checksum verification.

Flow for one file, exactly per the approved design:
  1. If the final remote path already exists, verify it (SSH sha256sum)
     before doing anything else. Matching checksum -> skip (idempotent
     rerun). Mismatched checksum -> refuse to overwrite, raise.
  2. Upload to ``<remote_path>.part``.
  3. Run ``sha256sum`` over SSH against the ``.part`` file.
  4. Rename ``.part`` -> final name ONLY if that checksum matches.
  5. Verify the checksum of the FINAL (renamed) file too.
  6. Never deletes anything, locally or remotely — there is no delete
     method on this class at all in this version.

The real network/SSH work lives behind the ``SshSftpTransport``
protocol so tests can inject a fully in-memory fake and never touch a
real host — see tests/test_sftp_publisher.py.

SSH-key authentication only: ``ParamikoSshSftpTransport`` takes a
private-key path. There is no password parameter anywhere in this
module, by design (requirement: "do not implement password storage").
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Optional, Protocol

from .models import ChecksumInfo, TransferResult, TransferState


class SftpTransferError(Exception):
    """Base class for SFTP transfer failures. A checksum mismatch is
    reported as a FAILED TransferResult (see SftpPublisher.publish),
    not raised as an exception, so the CLI can record it per-file and
    continue with other observations."""


class RemoteConflictError(SftpTransferError):
    """A different file already exists at the final remote path; refusing to overwrite."""


class SshSftpTransport(Protocol):
    """Everything the publisher needs from an SSH/SFTP connection.

    Implemented for real by ParamikoSshSftpTransport, and faked
    entirely in-memory for tests, so no test ever opens a real network
    connection.
    """

    def upload_file(self, local_path: Path, remote_path: str) -> None: ...

    def exec_sha256sum(self, remote_path: str) -> Optional[str]:
        """Returns the lowercase hex sha256 digest of the remote file, or
        None if the remote path does not exist."""
        ...

    def rename(self, remote_from: str, remote_to: str) -> None: ...

    def remote_exists(self, remote_path: str) -> bool: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class ParamikoSshSftpOptions:
    host: str
    port: int
    username: str
    private_key_path: Path
    timeout_seconds: float = 30.0


class ParamikoSshSftpTransport:
    """Real transport: one SSH connection used for both an SFTP session
    (upload/rename/stat) and ``exec_command`` (remote sha256sum).
    SSH-key authentication only — no password parameter exists here.
    """

    def __init__(self, options: ParamikoSshSftpOptions):
        import paramiko  # imported lazily so the rest of the package has no hard paramiko import at module load time for unit tests

        self._options = options
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.RejectPolicy())
        self._client.load_system_host_keys()
        self._client.connect(
            hostname=options.host,
            port=options.port,
            username=options.username,
            key_filename=str(options.private_key_path),
            timeout=options.timeout_seconds,
            allow_agent=False,
            look_for_keys=False,
        )
        self._sftp = self._client.open_sftp()

    def upload_file(self, local_path: Path, remote_path: str) -> None:
        remote_dir = str(PurePosixPath(remote_path).parent)
        self._mkdir_p(remote_dir)
        self._sftp.put(str(local_path), remote_path)

    def _mkdir_p(self, remote_dir: str) -> None:
        parts = PurePosixPath(remote_dir).parts
        current = ""
        for part in parts:
            current = f"{current}/{part}" if current else part
            try:
                self._sftp.stat(current)
            except FileNotFoundError:
                self._sftp.mkdir(current)

    def exec_sha256sum(self, remote_path: str) -> Optional[str]:
        # Quote defensively; remote paths are built entirely by this
        # codebase from known-safe components (site IDs, dates,
        # observation IDs), never from unsanitised external input.
        command = f"sha256sum -- '{remote_path}' 2>/dev/null || echo MISSING"
        _stdin, stdout, _stderr = self._client.exec_command(command, timeout=self._options.timeout_seconds)
        output = stdout.read().decode("utf-8", errors="replace").strip()
        if not output or output == "MISSING":
            return None
        return output.split()[0].lower()

    def rename(self, remote_from: str, remote_to: str) -> None:
        self._sftp.posix_rename(remote_from, remote_to)

    def remote_exists(self, remote_path: str) -> bool:
        try:
            self._sftp.stat(remote_path)
            return True
        except FileNotFoundError:
            return False

    def close(self) -> None:
        self._sftp.close()
        self._client.close()


class SftpPublisher:
    def __init__(self, transport: SshSftpTransport, remote_root: str):
        self._transport = transport
        self._remote_root = remote_root.rstrip("/")

    def _absolute(self, relative_path: str) -> str:
        return f"{self._remote_root}/{relative_path}"

    def publish(
        self,
        local_path: Path,
        remote_relative_path: str,
        local_checksum: ChecksumInfo,
        product_id: str,
    ) -> TransferResult:
        remote_final = self._absolute(remote_relative_path)
        remote_part = f"{remote_final}.part"
        remote_part_relative = f"{remote_relative_path}.part"
        now = datetime.now(timezone.utc)

        # Step 1: idempotent skip / conflict check.
        if self._transport.remote_exists(remote_final):
            existing_checksum = self._transport.exec_sha256sum(remote_final)
            if existing_checksum == local_checksum.sha256:
                return TransferResult(
                    product_id=product_id,
                    remote_relative_path=remote_relative_path,
                    remote_part_relative_path=remote_part_relative,
                    state=TransferState.SKIPPED_EXISTING,
                    attempts=0,
                    last_attempt_at_utc=now,
                    remote_checksum=existing_checksum,
                )
            raise RemoteConflictError(
                f"Remote file already exists with a different checksum: {remote_final} "
                f"(local={local_checksum.sha256}, remote={existing_checksum}). Refusing to overwrite."
            )

        # Step 2: upload to .part
        self._transport.upload_file(local_path, remote_part)

        # Step 3: verify the .part checksum before ever renaming.
        part_checksum = self._transport.exec_sha256sum(remote_part)
        if part_checksum != local_checksum.sha256:
            return TransferResult(
                product_id=product_id,
                remote_relative_path=remote_relative_path,
                remote_part_relative_path=remote_part_relative,
                state=TransferState.FAILED,
                attempts=1,
                last_attempt_at_utc=now,
                remote_checksum=part_checksum,
                error_message=(
                    f"Checksum mismatch on uploaded .part file (local={local_checksum.sha256}, "
                    f"remote={part_checksum}); not renamed."
                ),
            )

        # Step 4: rename only after checksum success.
        self._transport.rename(remote_part, remote_final)

        # Step 5: verify the final (renamed) file's checksum too.
        final_checksum = self._transport.exec_sha256sum(remote_final)
        if final_checksum != local_checksum.sha256:
            return TransferResult(
                product_id=product_id,
                remote_relative_path=remote_relative_path,
                remote_part_relative_path=remote_part_relative,
                state=TransferState.FAILED,
                attempts=1,
                last_attempt_at_utc=now,
                remote_checksum=final_checksum,
                error_message=(
                    f"Checksum mismatch AFTER rename (local={local_checksum.sha256}, "
                    f"remote={final_checksum}); investigate before retrying."
                ),
            )

        return TransferResult(
            product_id=product_id,
            remote_relative_path=remote_relative_path,
            remote_part_relative_path=remote_part_relative,
            state=TransferState.VERIFIED,
            attempts=1,
            last_attempt_at_utc=now,
            remote_checksum=final_checksum,
        )

    # Deliberately no delete/remove method: "no automatic deletion by
    # default" is implemented by this capability not existing yet,
    # not by a flag that could be flipped on accident.

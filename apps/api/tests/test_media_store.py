from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from auscin_api.media_store import LocalMediaStore, MediaUnavailableError


@pytest.fixture
def store_root(tmp_path: Path) -> Path:
    root = tmp_path / "root"
    (root / "level-1" / "a").mkdir(parents=True)
    (root / "level-1" / "a" / "image.jpg").write_bytes(b"inside")
    (tmp_path / "outside.jpg").write_bytes(b"outside")
    return root


def test_resolves_file_inside_root(store_root):
    store = LocalMediaStore(store_root)
    path = store.resolve("level-1/a/image.jpg")
    assert path.read_bytes() == b"inside"
    assert path.is_relative_to(store_root.resolve())


def test_missing_root_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        LocalMediaStore(tmp_path / "does-not-exist")


def test_root_must_be_a_directory(store_root):
    with pytest.raises(ValueError):
        LocalMediaStore(store_root / "level-1" / "a" / "image.jpg")


@pytest.mark.parametrize(
    "value",
    [
        # POSIX absolute and traversal
        "/etc/passwd",
        "../outside.jpg",
        "level-1/../../outside.jpg",
        "level-1/a/../../../outside.jpg",
        "level-1/./a/image.jpg",
        "level-1//a/image.jpg",
        "",
        "level-1/a/image.jpg\x00",
    ],
)
def test_absolute_and_traversal_paths_are_rejected(store_root, value):
    with pytest.raises(MediaUnavailableError):
        LocalMediaStore(store_root).resolve(value)


@pytest.mark.parametrize(
    "value",
    [
        "C:/Windows/win.ini",
        "C:\\Windows\\win.ini",
        "c:outside.jpg",
        "\\\\server\\share\\image.jpg",
        "//server/share/image.jpg",
        "\\\\?\\C:\\Windows\\win.ini",
        "level-1\\..\\..\\outside.jpg",
        "level-1/a/image.jpg:Zone.Identifier",
        "level-1/a./image.jpg",
        "level-1/a /image.jpg",
    ],
)
def test_windows_drive_unc_and_backslash_paths_are_rejected(store_root, value):
    with pytest.raises(MediaUnavailableError):
        LocalMediaStore(store_root).resolve(value)


def test_absolute_path_to_real_file_outside_root_is_rejected(store_root, tmp_path):
    outside = (tmp_path / "outside.jpg").resolve()
    with pytest.raises(MediaUnavailableError):
        LocalMediaStore(store_root).resolve(str(outside))
    with pytest.raises(MediaUnavailableError):
        LocalMediaStore(store_root).resolve(outside.as_posix())


def test_missing_file_is_unavailable(store_root):
    with pytest.raises(MediaUnavailableError):
        LocalMediaStore(store_root).resolve("level-1/a/missing.jpg")


def test_directory_is_not_served(store_root):
    with pytest.raises(MediaUnavailableError):
        LocalMediaStore(store_root).resolve("level-1/a")


def _symlink_or_skip(link: Path, target: Path, *, target_is_directory: bool = False) -> None:
    try:
        os.symlink(target, link, target_is_directory=target_is_directory)
    except (OSError, NotImplementedError) as exc:
        # Windows needs Developer Mode or SeCreateSymbolicLinkPrivilege to create symlinks.
        pytest.skip(f"symlinks cannot be created on this platform/account: {exc}")


def test_file_symlink_escaping_root_is_rejected(store_root, tmp_path):
    _symlink_or_skip(store_root / "level-1" / "a" / "escape.jpg", tmp_path / "outside.jpg")
    with pytest.raises(MediaUnavailableError):
        LocalMediaStore(store_root).resolve("level-1/a/escape.jpg")


@pytest.fixture
def outside_dir(tmp_path: Path) -> Path:
    # A sibling of the media root, not its parent, so a directory link to it
    # can't create a recursive loop that later tools (git, cleanup) walk into.
    directory = tmp_path / "outside-dir"
    directory.mkdir()
    (directory / "outside.jpg").write_bytes(b"outside")
    return directory


def test_directory_symlink_escaping_root_is_rejected(store_root, outside_dir):
    link = store_root / "level-1" / "linked"
    _symlink_or_skip(link, outside_dir, target_is_directory=True)
    try:
        with pytest.raises(MediaUnavailableError):
            LocalMediaStore(store_root).resolve("level-1/linked/outside.jpg")
    finally:
        os.rmdir(link)  # removes the link only, never the target's contents


@pytest.mark.skipif(sys.platform != "win32", reason="NTFS directory junctions are Windows-only")
def test_directory_junction_escaping_root_is_rejected(store_root, outside_dir):
    # Junctions need no special privilege on Windows, so this escape case always runs there.
    import _winapi

    junction = store_root / "level-1" / "junction"
    _winapi.CreateJunction(str(outside_dir), str(junction))
    try:
        assert (junction / "outside.jpg").read_bytes() == b"outside"  # the escape route really exists
        with pytest.raises(MediaUnavailableError):
            LocalMediaStore(store_root).resolve("level-1/junction/outside.jpg")
    finally:
        os.rmdir(junction)  # removes the junction only, never the target's contents


def test_symlink_inside_root_is_allowed(store_root):
    _symlink_or_skip(store_root / "level-1" / "alias.jpg", store_root / "level-1" / "a" / "image.jpg")
    assert LocalMediaStore(store_root).resolve("level-1/alias.jpg").read_bytes() == b"inside"

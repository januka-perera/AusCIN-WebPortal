from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

import pytest
from fastapi.testclient import TestClient

from auscin_api.main import create_app
from auscin_api.settings import Settings

API_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures" / "coastsnap"
REGISTRY_PATH = FIXTURES / "sites-registry.json"
MANIFEST_PATH = FIXTURES / "manifest.json"
DERIVATIVES_INDEX_PATH = FIXTURES / "derivatives-index.json"

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
from synthetic_media import build_media_root  # noqa: E402

PUBLIC_SITE_ID = "CS-TEST-SITE"
HIDDEN_SITE_ID = "CS-TEST-HIDDEN"

TEST_TEMP_ROOT = API_ROOT / ".pytest-tmp"
"""Repository-local, git-ignored base for pytest's tmp_path.

Used instead of pytest's default under %TEMP%\\pytest-of-<user>, which can raise
PermissionError on locked-down Windows machines when an earlier run's
directories are left behind with restrictive ACLs. pytest clears this
directory at the start of every run, so it must stay dedicated to tests.
Only applied when --basetemp isn't given explicitly."""


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    if config.option.basetemp is None:
        config.option.basetemp = str(TEST_TEMP_ROOT)


def fixture_settings(
    registry: Path = REGISTRY_PATH,
    manifest: Path = MANIFEST_PATH,
    derivatives_index: Path | None = DERIVATIVES_INDEX_PATH,
    media_root: Path | None = None,
    media_base_url: str = "",
) -> Settings:
    return Settings(
        environment="test",
        site_registry_path=registry,
        manifest_path=manifest,
        derivatives_index_path=derivatives_index,
        media_root=media_root,
        media_base_url=media_base_url,
    )


@pytest.fixture
def media_root(tmp_path: Path) -> Path:
    """A fresh synthetic media root for each test, generated at runtime (no committed images)."""
    return build_media_root(tmp_path / "media", MANIFEST_PATH, DERIVATIVES_INDEX_PATH)


@pytest.fixture
def client(media_root: Path) -> TestClient:
    return TestClient(create_app(fixture_settings(media_root=media_root)))


@pytest.fixture
def client_without_media() -> TestClient:
    return TestClient(create_app(fixture_settings(derivatives_index=None, media_root=None)))


@pytest.fixture
def manifest_data() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def registry_data() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def derivatives_data() -> dict[str, Any]:
    return json.loads(DERIVATIVES_INDEX_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def write_json(tmp_path: Path) -> Callable[[str, dict[str, Any]], Path]:
    def _write(name: str, data: dict[str, Any]) -> Path:
        path = tmp_path / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    return _write

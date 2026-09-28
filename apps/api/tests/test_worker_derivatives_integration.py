"""End-to-end: the real worker derivatives command produces the index the API serves.

The worker command runs over the synthetic media root (Level 1 JPEGs whose
checksums match the fixture manifest). Its output index and derivative files
are then consumed by the API through a separate derivatives root. The public
URLs and JSON shape must be exactly what the hand-authored fixture produces.

Needs Pillow, installed via the worker's `derivatives` extra
(`pip install -e ..\\worker[derivatives]`). The test is skipped if Pillow is absent.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("PIL", reason="Pillow (worker 'derivatives' extra) is required for this integration test")

from coastsnap_import.derivatives import run as run_derivatives  # noqa: E402

from auscin_api.catalogue import build_media_id  # noqa: E402
from auscin_api.main import create_app  # noqa: E402
from conftest import DERIVATIVES_INDEX_PATH, MANIFEST_PATH, PUBLIC_SITE_ID, fixture_settings  # noqa: E402
from synthetic_media import build_media_root  # noqa: E402

PRESENTABLE = ["TEST_OBS_0001", "TEST_OBS_0002", "TEST_OBS_0003", "TEST_OBS_0004", "TEST_OBS_0005"]


@pytest.fixture
def worker_output(tmp_path: Path) -> tuple[Path, Path, Path]:
    staging = build_media_root(tmp_path / "staging", MANIFEST_PATH, DERIVATIVES_INDEX_PATH)
    output_root = tmp_path / "derivatives-out"
    index_path = output_root / "derivatives-index.json"
    summary = run_derivatives(
        manifest_path=MANIFEST_PATH, input_root=staging, output_root=output_root, index_output=index_path,
        out=io.StringIO(), err=io.StringIO(),
    )
    # TEST_OBS_0006 has no Level 1 product and is skipped. Every other entry has a verified source.
    assert (summary.processed, summary.skipped, summary.failed) == (5, 1, 0)
    return staging, output_root, index_path


def test_api_serves_worker_generated_derivatives(worker_output):
    staging, output_root, index_path = worker_output
    client = TestClient(create_app(fixture_settings(
        derivatives_index=index_path, media_root=staging, derivatives_root=output_root,
    )))
    index = json.loads(index_path.read_text(encoding="utf-8"))
    recorded = {e["observation_id"]: e for e in index["derivatives"]}

    for observation_id in PRESENTABLE:
        mid = build_media_id(PUBLIC_SITE_ID, observation_id)
        item = client.get(f"/api/v1/coastsnap/sites/{PUBLIC_SITE_ID}/observations/{mid}").json()
        assert item["thumbnailUrl"] == f"/media/coastsnap/{mid}/thumbnail"
        assert item["previewUrl"] == f"/media/coastsnap/{mid}/preview"
        for kind in ("thumbnail", "preview"):
            response = client.get(f"/media/coastsnap/{mid}/{kind}")
            assert response.status_code == 200
            assert response.headers["content-type"] == "image/jpeg"
            assert response.content[:3] == b"\xff\xd8\xff"
            expected = recorded[observation_id][kind]["sha256"]
            assert response.headers["etag"] == f'"{expected}"'
            assert hashlib.sha256(response.content).hexdigest() == expected


def test_worker_index_keeps_the_public_json_shape_unchanged(worker_output, media_root):
    staging, output_root, index_path = worker_output
    worker_client = TestClient(create_app(fixture_settings(
        derivatives_index=index_path, media_root=staging, derivatives_root=output_root,
    )))
    fixture_client = TestClient(create_app(fixture_settings(media_root=media_root)))
    url = f"/api/v1/coastsnap/sites/{PUBLIC_SITE_ID}/observations?pageSize=100"
    worker_items = worker_client.get(url).json()["items"]
    fixture_items = fixture_client.get(url).json()["items"]
    assert [set(i) for i in worker_items] == [set(i) for i in fixture_items]
    assert [i["id"] for i in worker_items] == [i["id"] for i in fixture_items]


def test_worker_index_contains_no_paths_outside_the_derivatives_tree(worker_output, tmp_path):
    _, _, index_path = worker_output
    text = index_path.read_text(encoding="utf-8")
    for forbidden in (str(tmp_path), tmp_path.as_posix(), "\\\\", "/g/data", "level-1/", "example.invalid"):
        assert forbidden not in text

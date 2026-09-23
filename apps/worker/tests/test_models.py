from __future__ import annotations

from datetime import datetime, timezone

from coastsnap_import.models import (
    ProductLevel,
    SourceSite,
    build_level_relative_path,
    build_manifest_relative_path,
    build_site_directory_id,
    build_source_record_paths,
)


def test_level0_path_matches_required_structure():
    captured_at = datetime(2026, 8, 1, 2, 15, tzinfo=timezone.utc)
    path = build_level_relative_path(ProductLevel.LEVEL_0, "CS-DRIFTWOOD", captured_at, "1001.jpg")
    assert path == "level-0/CS-DRIFTWOOD/2026/08/01/images/1001.jpg"


def test_level1_path_matches_required_structure():
    captured_at = datetime(2026, 8, 1, 2, 15, tzinfo=timezone.utc)
    path = build_level_relative_path(ProductLevel.LEVEL_1, "CS-DRIFTWOOD", captured_at, "1001.jpg")
    assert path == "level-1/CS-DRIFTWOOD/2026/08/01/images/1001.jpg"


def test_paths_are_posix_style_regardless_of_host_os():
    captured_at = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)
    path = build_level_relative_path(ProductLevel.LEVEL_0, "CS-SITE", captured_at, "x.jpg")
    assert "\\" not in path
    assert path == "level-0/CS-SITE/2026/01/05/images/x.jpg"


def test_source_record_paths():
    ref = build_source_record_paths("37", "1001")
    assert ref.site_record_relative_path == "metadata/source-records/sites/37.json"
    assert ref.observation_record_relative_path == "metadata/source-records/observations/1001.json"


def test_manifest_path():
    assert build_manifest_relative_path("37") == "manifests/37.json"


def test_relative_paths_never_absolute():
    captured_at = datetime(2026, 8, 1, tzinfo=timezone.utc)
    assert not build_level_relative_path(ProductLevel.LEVEL_0, "S", captured_at, "a.jpg").startswith("/")
    assert not build_source_record_paths("r", "o").site_record_relative_path.startswith("/")
    assert not build_manifest_relative_path("r").startswith("/")


def test_site_directory_id_is_deterministic_and_root_id_based():
    # Matches the real root_id observed in live testing (see the task's
    # confirmed example: root_id 487447, observation 1351374).
    assert build_site_directory_id("487447") == "root-487447"
    assert build_site_directory_id("487447") == build_site_directory_id("487447")


def test_site_directory_id_does_not_depend_on_site_name():
    """SourceSite.name is always None in practice (no confirmed, stable
    Spotteron field for it — dynamic fields like "fld_01_00001214" are
    never treated as schema; see spotteron_client.py). The directory
    identity must stay valid and deterministic regardless."""
    site = SourceSite(root_id="487447")
    assert site.name is None
    assert build_site_directory_id(site.root_id) == "root-487447"


def test_level_path_valid_when_site_name_is_none():
    captured_at = datetime(2026, 9, 23, tzinfo=timezone.utc)
    site_directory_id = build_site_directory_id("487447")
    path = build_level_relative_path(ProductLevel.LEVEL_0, site_directory_id, captured_at, "1351374.jpg")
    assert path == "level-0/root-487447/2026/09/23/images/1351374.jpg"

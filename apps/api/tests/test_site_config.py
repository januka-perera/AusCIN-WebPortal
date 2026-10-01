"""Tests for the offline real-site configuration validator (auscin_api.site_config).

Nothing here touches the network, Spotteron, Gadi or NCI. All values are
synthetic. Paths are built under pytest's temp directory with an explicit
"repository root", so the outside-the-repository rule can be tested either
way.
"""

from __future__ import annotations

import io
import json
import shutil
import tempfile
from datetime import date
from pathlib import Path

import pytest

from auscin_api.schemas import SiteRegistry
from auscin_api.site_config import (
    ALL_FIELDS,
    IGNORED_COORDINATE_FIELDS,
    REQUIRED_FIELDS,
    EnvFileError,
    RegistryConflictError,
    build_combined_registry,
    build_registry,
    registry_json,
    main,
    read_env_file,
    validate_site_config,
)

TEMPLATE = Path(__file__).resolve().parents[1] / "config" / "coastsnap-site.env.example"
TODAY = date(2026, 9, 28)


def synthetic_config(base: Path) -> dict[str, str]:
    """A complete, placeholder-free, synthetic configuration. Not a real site."""
    staging = base / "staging"
    derivatives = base / "derivatives"
    return {
        "SPOTTERON_ROOT_ID": "TEST_ROOT_ID",
        "COASTSNAP_SITE_SLUG": "CS-SYNTHETIC-BEACH",
        "COASTSNAP_SITE_NAME": "Synthetic Beach CoastSnap",
        "COASTSNAP_SITE_STATE": "NSW",
        "COASTSNAP_SITE_REGION": "Synthetic test region",
        "COASTSNAP_SITE_DESCRIPTION": "A synthetic CoastSnap site used only to test the configuration validator.",
        "COASTSNAP_SITE_TIME_ZONE": "Australia/Sydney",
        "COASTSNAP_SITE_ESTABLISHED_SINCE": "2025-01-15",
        "COASTSNAP_SITE_ATTRIBUTION_TEXT": "CoastSnap community photo (synthetic)",
        "COASTSNAP_SITE_PUBLICATION_STATUS": "embargoed",
        "COASTSNAP_SITE_LEVEL0_DOWNLOAD_PERMITTED": "false",
        "COASTSNAP_SITE_LEVEL1_DOWNLOAD_PERMITTED": "false",
        "COASTSNAP_STAGING_DIR": str(staging),
        "COASTSNAP_DERIVATIVES_ROOT": str(derivatives),
        "COASTSNAP_MANIFEST_PATH": str(staging / "manifests" / "TEST_ROOT_ID.json"),
        "COASTSNAP_DERIVATIVES_INDEX_PATH": str(derivatives / "derivatives-index.json"),
        "NCI_PUBLICATION_ROOT": "/g/data/example-project/AusCIN/coastsnap-test",
    }


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    return root


@pytest.fixture
def config(tmp_path: Path) -> dict[str, str]:
    return synthetic_config(tmp_path / "outside")


def validate(env: dict[str, str], repo: Path, **kwargs):
    return validate_site_config(env, repository_roots=[repo], today=TODAY, **kwargs)


# --- Valid configuration -------------------------------------------------------------------


def test_valid_placeholder_free_synthetic_configuration_passes(config, repo):
    report = validate(config, repo)
    assert report.ok, report.errors


def test_valid_configuration_passes_for_transfer(config, repo):
    report = validate(config, repo, for_transfer=True)
    assert report.ok, report.errors


def test_registry_is_built_from_explicit_values_only(config):
    registry = build_registry(config)
    assert isinstance(registry, SiteRegistry)
    (site,) = registry.sites
    assert site.site_id == "CS-SYNTHETIC-BEACH"
    assert site.spotteron_root_id == "TEST_ROOT_ID"
    assert site.publication_status == "embargoed"
    assert site.level0_download_permitted is False
    assert site.level1_download_permitted is False
    assert site.is_synthetic is False
    both = build_registry({
        **config,
        "COASTSNAP_SITE_PUBLICATION_STATUS": "public",
        "COASTSNAP_SITE_LEVEL0_DOWNLOAD_PERMITTED": "true",
        "COASTSNAP_SITE_LEVEL1_DOWNLOAD_PERMITTED": "true",
    })
    assert both.sites[0].publication_status == "public"
    assert (both.sites[0].level0_download_permitted, both.sites[0].level1_download_permitted) == (True, True)


@pytest.mark.parametrize(("level0", "level1"), [("true", "false"), ("false", "true")])
def test_each_level_permission_is_independent(config, level0, level1):
    registry = build_registry({
        **config,
        "COASTSNAP_SITE_LEVEL0_DOWNLOAD_PERMITTED": level0,
        "COASTSNAP_SITE_LEVEL1_DOWNLOAD_PERMITTED": level1,
    })
    site = registry.sites[0]
    assert (site.level0_download_permitted, site.level1_download_permitted) == (level0 == "true", level1 == "true")


def test_retired_single_download_permission_is_refused(config, repo):
    config["COASTSNAP_SITE_DOWNLOAD_PERMITTED"] = "true"
    report = validate(config, repo)
    assert not report.ok
    assert any("LEVEL0_DOWNLOAD_PERMITTED" in m and "LEVEL1_DOWNLOAD_PERMITTED" in m
               for m in report.errors["COASTSNAP_SITE_DOWNLOAD_PERMITTED"])


def test_retired_single_download_permission_is_reported_by_the_cli(outside_repo):
    config = {**synthetic_config(outside_repo), "COASTSNAP_SITE_DOWNLOAD_PERMITTED": "true"}
    out = io.StringIO()
    assert main(["validate"], environ=config, out=out) == 1
    assert "[FAIL] COASTSNAP_SITE_DOWNLOAD_PERMITTED has been replaced" in out.getvalue()


# --- Missing and placeholder values -----------------------------------------------------------


@pytest.mark.parametrize("name", REQUIRED_FIELDS)
def test_each_missing_required_value_is_refused(config, repo, name):
    del config[name]
    report = validate(config, repo)
    assert not report.ok
    assert any("required" in message for message in report.errors[name])


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_blank_site_metadata_is_refused(config, repo, blank):
    config["COASTSNAP_SITE_NAME"] = blank
    config["COASTSNAP_SITE_DESCRIPTION"] = blank
    report = validate(config, repo)
    assert "COASTSNAP_SITE_NAME" in report.errors and "COASTSNAP_SITE_DESCRIPTION" in report.errors


def test_publication_root_is_required_only_for_transfer(config, repo):
    del config["NCI_PUBLICATION_ROOT"]
    assert validate(config, repo).ok
    report = validate(config, repo, for_transfer=True)
    assert "NCI_PUBLICATION_ROOT" in report.errors


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("SPOTTERON_ROOT_ID", "<SPOTTERON_ROOT_ID>"),
        ("COASTSNAP_SITE_SLUG", "<COASTSNAP_SITE_SLUG>"),
        ("COASTSNAP_SITE_NAME", "<site name here>"),
        ("COASTSNAP_SITE_DESCRIPTION", "TODO describe the alignment mark and the beach it frames"),
        ("COASTSNAP_SITE_ATTRIBUTION_TEXT", "CHANGE_ME"),
        ("COASTSNAP_SITE_REGION", "REPLACE_ME"),
        ("COASTSNAP_SITE_ESTABLISHED_SINCE", "TBC"),
        ("COASTSNAP_STAGING_DIR", "<COASTSNAP_STAGING_DIR>"),
        ("NCI_PUBLICATION_ROOT", "<NCI_PUBLICATION_ROOT>"),
    ],
)
def test_unresolved_placeholders_are_refused(config, repo, name, value):
    config[name] = value
    report = validate(config, repo, for_transfer=True)
    assert any("placeholder" in message for message in report.errors[name])


def test_ordinary_prose_is_not_mistaken_for_a_placeholder(config, repo):
    config["COASTSNAP_SITE_DESCRIPTION"] = "A new alignment mark installed to replace the old one on the northern headland."
    assert validate(config, repo).ok


def test_the_committed_template_contains_only_placeholders(repo):
    values = read_env_file(TEMPLATE)
    assert set(values) == set(ALL_FIELDS)
    for name, value in values.items():
        assert value == f"<{name}>", f"{name} in the committed template must stay a placeholder"
    report = validate(values, repo, for_transfer=True)
    assert set(report.errors) == set(ALL_FIELDS)


# --- Slug, identifiers, coordinates, time zone, dates, policy ---------------------------------------


@pytest.mark.parametrize(
    "slug",
    ["cs-lowercase", "EXAMPLE-BEACH", "CS-", "CS--DOUBLE", "CS-TRAILING-", "CS-HAS SPACE", "CS-HAS_UNDERSCORE",
     "CS-" + "A" * 70, "CS-../ETC", "CS-É"],
)
def test_invalid_site_slug_is_refused(config, repo, slug):
    config["COASTSNAP_SITE_SLUG"] = slug
    assert "COASTSNAP_SITE_SLUG" in validate(config, repo).errors


@pytest.mark.parametrize("root_id", ["12 34", "../1", "a/b", "x" * 65])
def test_invalid_root_id_is_refused(config, repo, root_id):
    config["SPOTTERON_ROOT_ID"] = root_id
    assert "SPOTTERON_ROOT_ID" in validate(config, repo).errors


@pytest.mark.parametrize(
    ("latitude", "longitude", "field"),
    [
        ("-91", "151", "COASTSNAP_SITE_LATITUDE"),
        ("90.5", "151", "COASTSNAP_SITE_LATITUDE"),
        ("-33", "181", "COASTSNAP_SITE_LONGITUDE"),
        ("-33", "-180.1", "COASTSNAP_SITE_LONGITUDE"),
        ("south", "151", "COASTSNAP_SITE_LATITUDE"),
        ("nan", "151", "COASTSNAP_SITE_LATITUDE"),
        ("-33", "inf", "COASTSNAP_SITE_LONGITUDE"),
        ("0", "0", "COASTSNAP_SITE_LATITUDE"),
    ],
)
def test_invalid_legacy_coordinates_are_still_refused_when_present(config, repo, latitude, longitude, field):
    config["COASTSNAP_SITE_LATITUDE"] = latitude
    config["COASTSNAP_SITE_LONGITUDE"] = longitude
    assert field in validate(config, repo).errors


def test_northern_latitude_is_allowed_but_noted(config, repo):
    config["COASTSNAP_SITE_LATITUDE"] = "12.5"
    report = validate(config, repo)
    assert report.ok
    assert any("northern hemisphere" in note for note in report.notes)


@pytest.mark.parametrize("zone", ["AEST", "Australia/Nowhere", "UTC+10", "../etc/passwd", "Australia/"])
def test_invalid_time_zone_is_refused(config, repo, zone):
    config["COASTSNAP_SITE_TIME_ZONE"] = zone
    assert "COASTSNAP_SITE_TIME_ZONE" in validate(config, repo).errors


@pytest.mark.parametrize("value", ["15/01/2025", "2025-13-01", "2026-09-29"])
def test_invalid_or_future_established_date_is_refused(config, repo, value):
    config["COASTSNAP_SITE_ESTABLISHED_SINCE"] = value
    assert "COASTSNAP_SITE_ESTABLISHED_SINCE" in validate(config, repo).errors


@pytest.mark.parametrize("state", ["New South Wales", "nsw", "NZ"])
def test_invalid_state_is_refused(config, repo, state):
    config["COASTSNAP_SITE_STATE"] = state
    assert "COASTSNAP_SITE_STATE" in validate(config, repo).errors


@pytest.mark.parametrize("status", ["published", "Public", "private"])
def test_invalid_publication_status_is_refused(config, repo, status):
    config["COASTSNAP_SITE_PUBLICATION_STATUS"] = status
    assert "COASTSNAP_SITE_PUBLICATION_STATUS" in validate(config, repo).errors


@pytest.mark.parametrize("name", ["COASTSNAP_SITE_LEVEL0_DOWNLOAD_PERMITTED", "COASTSNAP_SITE_LEVEL1_DOWNLOAD_PERMITTED"])
@pytest.mark.parametrize("value", ["yes", "1", "True", "TRUE", "on"])
def test_each_level_permission_must_be_an_explicit_true_or_false(config, repo, name, value):
    config[name] = value
    assert name in validate(config, repo).errors


def test_short_description_is_refused(config, repo):
    config["COASTSNAP_SITE_DESCRIPTION"] = "A beach."
    assert "COASTSNAP_SITE_DESCRIPTION" in validate(config, repo).errors


# --- Paths ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["COASTSNAP_STAGING_DIR", "COASTSNAP_DERIVATIVES_ROOT", "COASTSNAP_DERIVATIVES_INDEX_PATH"])
def test_repository_contained_paths_are_refused(config, repo, name):
    config[name] = str(repo / "apps" / "worker" / "staging" / ("index.json" if name.endswith("PATH") else "dir"))
    report = validate(config, repo)
    assert any("outside the git repository" in message for message in report.errors[name])


def test_repository_contained_staging_and_manifest_are_refused_together(tmp_path, repo):
    config = synthetic_config(repo)  # every local path inside the repository
    report = validate(config, repo)
    for name in ("COASTSNAP_STAGING_DIR", "COASTSNAP_DERIVATIVES_ROOT", "COASTSNAP_MANIFEST_PATH", "COASTSNAP_DERIVATIVES_INDEX_PATH"):
        assert name in report.errors


@pytest.mark.parametrize(
    "name", ["COASTSNAP_STAGING_DIR", "COASTSNAP_DERIVATIVES_ROOT", "COASTSNAP_MANIFEST_PATH", "COASTSNAP_DERIVATIVES_INDEX_PATH"],
)
@pytest.mark.parametrize("value", ["/g/data/qu34/AusCIN/staging", "/g/data", "\\g\\data\\qu34\\x"])
def test_local_g_data_paths_are_refused(config, repo, name, value):
    config[name] = value
    report = validate(config, repo)
    assert any("/g/data" in message for message in report.errors[name])


@pytest.mark.parametrize("value", ["relative/staging", "./staging", "staging"])
def test_relative_local_paths_are_refused(config, repo, value):
    config["COASTSNAP_STAGING_DIR"] = value
    assert "COASTSNAP_STAGING_DIR" in validate(config, repo).errors


def test_manifest_must_be_the_workers_default_path(config, repo, tmp_path):
    config["COASTSNAP_MANIFEST_PATH"] = str(tmp_path / "outside" / "staging" / "manifests" / "OTHER_ROOT.json")
    assert "COASTSNAP_MANIFEST_PATH" in validate(config, repo).errors


def test_derivatives_root_must_differ_from_staging(config, repo):
    config["COASTSNAP_DERIVATIVES_ROOT"] = config["COASTSNAP_STAGING_DIR"]
    assert "COASTSNAP_DERIVATIVES_ROOT" in validate(config, repo).errors


def test_staging_path_that_is_a_file_is_refused(config, repo, tmp_path):
    staging = Path(config["COASTSNAP_STAGING_DIR"])
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.write_text("not a directory", encoding="utf-8")
    assert "COASTSNAP_STAGING_DIR" in validate(config, repo).errors


@pytest.mark.parametrize(
    "value",
    ["relative/path", "C:\\nci\\root", "/g/data/x/../qu34", "/g/data//x", "/g/data/x/", "/g/data/x y", "/", "/g/data", "/g/data/qu34"],
)
def test_invalid_publication_root_is_refused(config, repo, value):
    config["NCI_PUBLICATION_ROOT"] = value
    assert "NCI_PUBLICATION_ROOT" in validate(config, repo, for_transfer=True).errors


def test_publication_root_is_remote_and_may_be_under_g_data(config, repo):
    config["NCI_PUBLICATION_ROOT"] = "/g/data/example-project/AusCIN/coastsnap-staging-test"
    assert validate(config, repo, for_transfer=True).ok


# --- Env file and CLI ----------------------------------------------------------------------------


def test_env_file_parser(tmp_path):
    path = tmp_path / "site.env"
    path.write_text(
        "# comment\n\nexport COASTSNAP_SITE_NAME=\"Quoted Name\"\nCOASTSNAP_SITE_REGION='Single quoted'\nCOASTSNAP_SITE_STATE=NSW\n",
        encoding="utf-8",
    )
    assert read_env_file(path) == {
        "COASTSNAP_SITE_NAME": "Quoted Name",
        "COASTSNAP_SITE_REGION": "Single quoted",
        "COASTSNAP_SITE_STATE": "NSW",
    }
    path.write_text("not a key value line\n", encoding="utf-8")
    with pytest.raises(EnvFileError):
        read_env_file(path)


@pytest.fixture
def outside_repo():
    """A directory in the system temp dir, outside this repository, for the CLI's real repository detection."""
    directory = Path(tempfile.mkdtemp(prefix="auscin-site-config-test-"))
    yield directory
    shutil.rmtree(directory, ignore_errors=True)


def write_env(path: Path, values: dict[str, str]) -> Path:
    path.write_text("".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8")
    return path


def test_cli_validate_passes_for_valid_env_file(outside_repo):
    env_file = write_env(outside_repo / "coastsnap-site.env", synthetic_config(outside_repo))
    out = io.StringIO()
    assert main(["validate", "--env-file", str(env_file)], environ={}, out=out) == 0
    assert "Configuration is valid" in out.getvalue()
    assert "No network or storage was accessed" in out.getvalue()


def test_cli_validate_fails_and_lists_every_problem_for_the_template():
    out = io.StringIO()
    assert main(["validate", "--env-file", str(TEMPLATE), "--for-transfer"], environ={}, out=out) == 1
    text = out.getvalue()
    for name in ALL_FIELDS:
        assert f"[FAIL] {name}" in text


def test_cli_refuses_a_filled_in_env_file_inside_the_repository():
    out = io.StringIO()
    inside = Path(__file__).resolve().parent / "fixtures" / "coastsnap-site.env"
    assert main(["validate", "--env-file", str(inside)], environ={}, out=out) == 2
    assert "outside the repository" in out.getvalue()


def test_cli_write_registry_writes_the_reviewed_entry(outside_repo):
    config = synthetic_config(outside_repo)
    env_file = write_env(outside_repo / "coastsnap-site.env", config)
    output = outside_repo / "registry" / "site-registry.json"
    out = io.StringIO()
    assert main(["write-registry", "--env-file", str(env_file), "--output", str(output)], environ={}, out=out) == 0
    registry = SiteRegistry.model_validate(json.loads(output.read_text(encoding="utf-8")))
    assert registry.sites[0].site_id == "CS-SYNTHETIC-BEACH"
    assert "publication_status          = embargoed" in out.getvalue()
    assert "level0_download_permitted   = false" in out.getvalue()
    assert "level1_download_permitted   = false" in out.getvalue()


def test_cli_write_registry_refuses_invalid_config_and_writes_nothing(outside_repo):
    config = synthetic_config(outside_repo)
    config["COASTSNAP_SITE_SLUG"] = "<COASTSNAP_SITE_SLUG>"
    env_file = write_env(outside_repo / "coastsnap-site.env", config)
    output = outside_repo / "site-registry.json"
    assert main(["write-registry", "--env-file", str(env_file), "--output", str(output)], environ={}, out=io.StringIO()) == 1
    assert not output.exists()


def test_cli_write_registry_refuses_output_inside_the_repository(outside_repo):
    env_file = write_env(outside_repo / "coastsnap-site.env", synthetic_config(outside_repo))
    inside = Path(__file__).resolve().parent / "fixtures" / "generated-registry.json"
    out = io.StringIO()
    assert main(["write-registry", "--env-file", str(env_file), "--output", str(inside)], environ={}, out=out) == 2
    assert not inside.exists()


def test_cli_reads_values_from_the_environment_without_an_env_file(outside_repo):
    assert main(["validate"], environ=synthetic_config(outside_repo), out=io.StringIO()) == 0


# --- Coordinates are discovered by the worker, never entered ------------------------------------


def test_coordinates_are_not_required_or_in_the_template(config, repo):
    assert not set(IGNORED_COORDINATE_FIELDS) & set(ALL_FIELDS)
    assert not set(IGNORED_COORDINATE_FIELDS) & set(read_env_file(TEMPLATE))
    assert "COASTSNAP_SITE_LATITUDE" not in config
    report = validate(config, repo)
    assert report.ok, report.errors
    assert not any("LATITUDE" in note for note in report.notes)


def test_registry_never_contains_coordinates(config):
    (site,) = build_registry(config).sites
    assert site.latitude is None and site.longitude is None
    legacy = build_registry({**config, "COASTSNAP_SITE_LATITUDE": "-33.5", "COASTSNAP_SITE_LONGITUDE": "151.3"})
    assert legacy.sites[0].latitude is None and legacy.sites[0].longitude is None


def test_legacy_coordinates_are_accepted_but_noted_as_ignored(config, repo):
    report = validate({**config, "COASTSNAP_SITE_LATITUDE": "-33.5", "COASTSNAP_SITE_LONGITUDE": "151.3"}, repo)
    assert report.ok, report.errors
    assert any("ignored" in note and "worker derives" in note for note in report.notes)


def test_cli_reports_an_invalid_legacy_coordinate(outside_repo):
    config = {**synthetic_config(outside_repo), "COASTSNAP_SITE_LATITUDE": "-91", "COASTSNAP_SITE_LONGITUDE": "151"}
    out = io.StringIO()
    assert main(["validate"], environ=config, out=out) == 1
    assert "[FAIL] COASTSNAP_SITE_LATITUDE must be between -90 and 90" in out.getvalue()


def test_cli_written_registry_has_no_coordinates(outside_repo):
    config = {**synthetic_config(outside_repo), "COASTSNAP_SITE_LATITUDE": "-33.5", "COASTSNAP_SITE_LONGITUDE": "151.3"}
    output = outside_repo / "registry" / "site-registry.json"
    assert main(["write-registry", "--output", str(output)], environ=config, out=io.StringIO()) == 0
    written = json.loads(output.read_text(encoding="utf-8"))
    assert "latitude" not in written["sites"][0] and "longitude" not in written["sites"][0]
    assert SiteRegistry.model_validate(written).sites[0].latitude is None


# --- Several sites, one reviewed registry -------------------------------------------------------


def second_site_config(base: Path) -> dict[str, str]:
    """Another synthetic site sharing the first site's staging and derivatives roots, with its own policy."""
    config = synthetic_config(base)
    staging = Path(config["COASTSNAP_STAGING_DIR"])
    derivatives = Path(config["COASTSNAP_DERIVATIVES_ROOT"])
    config.update({
        "SPOTTERON_ROOT_ID": "TEST_ROOT_ID_B",
        "COASTSNAP_SITE_SLUG": "CS-ANOTHER-BEACH",
        "COASTSNAP_SITE_NAME": "Another Beach CoastSnap",
        "COASTSNAP_SITE_PUBLICATION_STATUS": "public",
        "COASTSNAP_SITE_LEVEL0_DOWNLOAD_PERMITTED": "true",
        "COASTSNAP_SITE_LEVEL1_DOWNLOAD_PERMITTED": "false",
        "COASTSNAP_MANIFEST_PATH": str(staging / "manifests" / "TEST_ROOT_ID_B.json"),
        "COASTSNAP_DERIVATIVES_INDEX_PATH": str(derivatives / "TEST_ROOT_ID_B-index.json"),
    })
    return config


def write_registry_cli(outside: Path, *env_files: Path, environ: dict[str, str] | None = None) -> tuple[int, str, Path]:
    output = outside / "registry" / "site-registry.json"
    args = ["write-registry"]
    for env_file in env_files:
        args += ["--env-file", str(env_file)]
    out = io.StringIO()
    code = main([*args, "--output", str(output)], environ=environ or {}, out=out)
    return code, out.getvalue(), output


@pytest.fixture
def two_env_files(outside_repo: Path) -> tuple[Path, Path]:
    first = write_env(outside_repo / "site-a.env", synthetic_config(outside_repo))
    second = write_env(outside_repo / "site-b.env", second_site_config(outside_repo))
    return first, second


def test_one_env_file_writes_the_same_registry_as_before(outside_repo):
    config = synthetic_config(outside_repo)
    code, text, output = write_registry_cli(outside_repo, write_env(outside_repo / "site.env", config))
    assert code == 0
    assert output.read_text(encoding="utf-8") == registry_json(build_registry(config))
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["schema_version"] == 1 and len(written["sites"]) == 1
    assert "1 site entry: CS-SYNTHETIC-BEACH" in text


def test_two_env_files_write_one_registry_with_both_sites_and_their_own_policies(outside_repo, two_env_files):
    code, text, output = write_registry_cli(outside_repo, *two_env_files)
    assert code == 0, text
    sites = {s.site_id: s for s in SiteRegistry.model_validate_json(output.read_text(encoding="utf-8")).sites}
    assert list(sites) == ["CS-ANOTHER-BEACH", "CS-SYNTHETIC-BEACH"]  # sorted by site ID
    a, b = sites["CS-SYNTHETIC-BEACH"], sites["CS-ANOTHER-BEACH"]
    assert (a.spotteron_root_id, a.publication_status, a.level0_download_permitted, a.level1_download_permitted) == (
        "TEST_ROOT_ID", "embargoed", False, False)
    assert (b.spotteron_root_id, b.publication_status, b.level0_download_permitted, b.level1_download_permitted) == (
        "TEST_ROOT_ID_B", "public", True, False)
    assert "2 site entries: CS-ANOTHER-BEACH, CS-SYNTHETIC-BEACH" in text
    assert "coordinate comes from its worker manifest" in text
    assert "explicit settings" in text


def test_output_bytes_do_not_depend_on_env_file_order(outside_repo, two_env_files):
    first, second = two_env_files
    _, _, output = write_registry_cli(outside_repo, first, second)
    forward = output.read_bytes()
    _, _, output = write_registry_cli(outside_repo, second, first)
    assert output.read_bytes() == forward


def test_generated_entries_never_contain_coordinates(outside_repo):
    legacy = {**second_site_config(outside_repo), "COASTSNAP_SITE_LATITUDE": "-33.5", "COASTSNAP_SITE_LONGITUDE": "151.3"}
    files = (write_env(outside_repo / "a.env", synthetic_config(outside_repo)), write_env(outside_repo / "b.env", legacy))
    code, _, output = write_registry_cli(outside_repo, *files)
    assert code == 0
    for site in json.loads(output.read_text(encoding="utf-8"))["sites"]:
        assert "latitude" not in site and "longitude" not in site


@pytest.mark.parametrize(
    ("field", "label"),
    [
        ("COASTSNAP_SITE_SLUG", "site ID"),
        ("SPOTTERON_ROOT_ID", "Spotteron root ID"),
        ("COASTSNAP_DERIVATIVES_INDEX_PATH", "derivatives index path"),
    ],
)
def test_conflicting_sites_are_refused_and_nothing_is_written(outside_repo, field, label):
    first = synthetic_config(outside_repo)
    second = {**second_site_config(outside_repo), field: first[field]}
    if field == "SPOTTERON_ROOT_ID":  # keep the manifest at the worker's default path for that root
        second["COASTSNAP_MANIFEST_PATH"] = first["COASTSNAP_MANIFEST_PATH"]
    files = (write_env(outside_repo / "a.env", first), write_env(outside_repo / "b.env", second))
    code, text, output = write_registry_cli(outside_repo, *files)
    assert code == 1
    assert f"same {label}" in text and "nothing was written" in text
    assert not output.exists()


def test_one_invalid_site_writes_nothing_and_leaves_an_existing_registry_untouched(outside_repo, two_env_files):
    first, _second = two_env_files
    broken = write_env(outside_repo / "broken.env", {**second_site_config(outside_repo), "COASTSNAP_SITE_STATE": "ZZ"})
    output = outside_repo / "registry" / "site-registry.json"
    output.parent.mkdir(parents=True)
    output.write_text("previous reviewed registry\n", encoding="utf-8")

    code, text, _ = write_registry_cli(outside_repo, first, broken)
    assert code == 1
    assert "== broken.env" in text and "[FAIL] COASTSNAP_SITE_STATE" in text
    assert "nothing was written" in text
    assert output.read_text(encoding="utf-8") == "previous reviewed registry\n"
    assert not list(output.parent.glob("*.tmp"))


def test_several_env_files_ignore_the_environment(outside_repo, two_env_files):
    environ = {"COASTSNAP_SITE_PUBLICATION_STATUS": "public", "COASTSNAP_SITE_LEVEL1_DOWNLOAD_PERMITTED": "true"}
    code, _, output = write_registry_cli(outside_repo, *two_env_files, environ=environ)
    assert code == 0
    registry = SiteRegistry.model_validate_json(output.read_text("utf-8"))
    site = next(s for s in registry.sites if s.site_id == "CS-SYNTHETIC-BEACH")
    assert site.publication_status == "embargoed" and site.level1_download_permitted is False

    incomplete = {k: v for k, v in second_site_config(outside_repo).items() if k != "COASTSNAP_SITE_PUBLICATION_STATUS"}
    files = (two_env_files[0], write_env(outside_repo / "incomplete.env", incomplete))
    code, text, _ = write_registry_cli(outside_repo, *files, environ=environ)
    assert code == 1  # the environment never fills a value missing from one of several files
    assert "[FAIL] COASTSNAP_SITE_PUBLICATION_STATUS is required" in text


def test_one_env_file_is_still_overlaid_on_the_environment(outside_repo):
    config = synthetic_config(outside_repo)
    status = config.pop("COASTSNAP_SITE_PUBLICATION_STATUS")
    env_file = write_env(outside_repo / "site.env", config)
    code, _, output = write_registry_cli(outside_repo, env_file, environ={"COASTSNAP_SITE_PUBLICATION_STATUS": status})
    assert code == 0 and output.exists()


def test_the_same_env_file_twice_is_refused(outside_repo, two_env_files):
    first, _ = two_env_files
    code, text, output = write_registry_cli(outside_repo, first, first)
    assert code == 2 and "given more than once" in text
    assert not output.exists()


def test_validate_checks_every_site_including_transfer_settings(outside_repo, two_env_files):
    first, second = two_env_files
    out = io.StringIO()
    assert main(["validate", "--env-file", str(first), "--env-file", str(second)], environ={}, out=out) == 0
    assert "== site-a.env" in out.getvalue() and "== site-b.env" in out.getvalue()

    no_root = {k: v for k, v in second_site_config(outside_repo).items() if k != "NCI_PUBLICATION_ROOT"}
    third = write_env(outside_repo / "no-root.env", no_root)
    out = io.StringIO()
    args = ["validate", "--for-transfer", "--env-file", str(first), "--env-file", str(third)]
    assert main(args, environ={}, out=out) == 1
    assert "[FAIL] NCI_PUBLICATION_ROOT is required" in out.getvalue()


def test_combined_registry_requires_at_least_one_site():
    with pytest.raises(RegistryConflictError, match="at least one"):
        build_combined_registry([])

from pathlib import Path

import pytest

from auscin_api.settings import Settings, SettingsError


def test_from_env_reads_required_paths():
    settings = Settings.from_env(
        {"COASTSNAP_SITE_REGISTRY_PATH": "registry.json", "COASTSNAP_MANIFEST_PATH": "manifest.json"}
    )
    assert settings.environment == "development"
    assert settings.site_registry_path == Path("registry.json")
    assert settings.manifest_path == Path("manifest.json")


@pytest.mark.parametrize("missing", ["COASTSNAP_SITE_REGISTRY_PATH", "COASTSNAP_MANIFEST_PATH"])
def test_missing_required_path_is_rejected(missing):
    env = {"COASTSNAP_SITE_REGISTRY_PATH": "r.json", "COASTSNAP_MANIFEST_PATH": "m.json"}
    env[missing] = ""
    with pytest.raises(SettingsError, match=missing):
        Settings.from_env(env)


def test_unknown_environment_is_rejected():
    with pytest.raises(SettingsError, match="AUSCIN_API_ENV"):
        Settings.from_env(
            {"AUSCIN_API_ENV": "staging", "COASTSNAP_SITE_REGISTRY_PATH": "r.json", "COASTSNAP_MANIFEST_PATH": "m.json"}
        )


@pytest.mark.parametrize("environment", ["development", "test"])
def test_production_storage_paths_are_refused_outside_production(environment):
    with pytest.raises(SettingsError, match="/g/data"):
        Settings.from_env(
            {
                "AUSCIN_API_ENV": environment,
                "COASTSNAP_SITE_REGISTRY_PATH": "r.json",
                "COASTSNAP_MANIFEST_PATH": "/g/data/qu34/anything/manifest.json",
            }
        )


def test_optional_media_settings_are_read():
    settings = Settings.from_env(
        {
            "COASTSNAP_SITE_REGISTRY_PATH": "r.json",
            "COASTSNAP_MANIFEST_PATH": "m.json",
            "COASTSNAP_DERIVATIVES_INDEX_PATH": "d.json",
            "COASTSNAP_MEDIA_ROOT": "media",
            "AUSCIN_MEDIA_BASE_URL": "http://localhost:8000/",
        }
    )
    assert settings.derivatives_index_path == Path("d.json")
    assert settings.media_root == Path("media")
    assert settings.media_base_url == "http://localhost:8000"


def test_media_settings_default_to_disabled():
    settings = Settings.from_env({"COASTSNAP_SITE_REGISTRY_PATH": "r.json", "COASTSNAP_MANIFEST_PATH": "m.json"})
    assert settings.media_root is None
    assert settings.derivatives_index_path is None
    assert settings.media_base_url == ""


@pytest.mark.parametrize("name", ["COASTSNAP_MEDIA_ROOT", "COASTSNAP_DERIVATIVES_INDEX_PATH"])
def test_media_paths_under_production_storage_are_refused(name):
    with pytest.raises(SettingsError, match="/g/data"):
        Settings.from_env(
            {"COASTSNAP_SITE_REGISTRY_PATH": "r.json", "COASTSNAP_MANIFEST_PATH": "m.json", name: "/g/data/qu34/x"}
        )


@pytest.mark.parametrize(
    "value", ["localhost:8000", "ftp://example.test", "http://localhost:8000/api", "http://x.test/?a=1", "http://"]
)
def test_media_base_url_must_be_an_http_origin(value):
    with pytest.raises(SettingsError, match="AUSCIN_MEDIA_BASE_URL"):
        Settings.from_env(
            {"COASTSNAP_SITE_REGISTRY_PATH": "r.json", "COASTSNAP_MANIFEST_PATH": "m.json", "AUSCIN_MEDIA_BASE_URL": value}
        )


def test_missing_media_root_fails_at_startup(tmp_path):
    from auscin_api.main import create_app
    from conftest import fixture_settings

    with pytest.raises(SettingsError, match="COASTSNAP_MEDIA_ROOT"):
        create_app(fixture_settings(media_root=tmp_path / "missing"))


def test_derivatives_root_is_read_and_requires_media_root():
    base = {"COASTSNAP_SITE_REGISTRY_PATH": "r.json", "COASTSNAP_MANIFEST_PATH": "m.json"}
    settings = Settings.from_env({**base, "COASTSNAP_MEDIA_ROOT": "staging", "COASTSNAP_DERIVATIVES_ROOT": "derivatives"})
    assert settings.derivatives_root == Path("derivatives")
    with pytest.raises(SettingsError, match="COASTSNAP_DERIVATIVES_ROOT requires COASTSNAP_MEDIA_ROOT"):
        Settings.from_env({**base, "COASTSNAP_DERIVATIVES_ROOT": "derivatives"})
    with pytest.raises(SettingsError, match="/g/data"):
        Settings.from_env({**base, "COASTSNAP_MEDIA_ROOT": "staging", "COASTSNAP_DERIVATIVES_ROOT": "/g/data/qu34/d"})

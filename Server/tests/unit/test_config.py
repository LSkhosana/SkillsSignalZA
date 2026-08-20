"""Unit tests for environment configuration."""

import pytest

from app.core.config import Settings, parse_cors_origins


def test_parse_cors_origins_from_comma_separated_string() -> None:
    origins = parse_cors_origins("http://localhost:8081, http://localhost:19006")
    assert origins == ["http://localhost:8081", "http://localhost:19006"]


def test_settings_parse_cors_origins_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:8081,http://localhost:19006")
    settings = Settings(_env_file=None)
    assert settings.cors_origins == [
        "http://localhost:8081",
        "http://localhost:19006",
    ]
    assert settings.allow_credentials is True


def test_settings_load_without_supabase_variables() -> None:
    settings = Settings(
        _env_file=None,
        supabase_url=None,
        supabase_publishable_key=None,
        supabase_secret_key=None,
    )
    assert settings.supabase_url is None
    assert settings.supabase_publishable_key is None
    assert settings.supabase_secret_key is None


def test_wildcard_cors_disables_credentials() -> None:
    settings = Settings(_env_file=None, cors_origins=["*"])
    assert settings.cors_allow_origins == ["*"]
    assert settings.allow_credentials is False


def test_secret_is_not_exposed_in_settings_repr() -> None:
    settings = Settings(_env_file=None, supabase_secret_key="super-secret-test-key")
    rendered = repr(settings)
    assert "super-secret-test-key" not in rendered

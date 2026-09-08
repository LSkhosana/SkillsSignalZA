"""Unit tests for environment configuration."""

import pytest
from pydantic import ValidationError

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


def test_settings_load_without_persistence_variables() -> None:
    settings = Settings(
        _env_file=None,
        supabase_url=None,
        supabase_publishable_key=None,
        supabase_secret_key=None,
        database_url=None,
    )
    assert settings.supabase_url is None
    assert settings.database_url is None
    assert settings.db_pool_min_size == 0
    assert settings.db_pool_max_size == 5
    assert settings.supabase_storage_bucket == "candidate-evidence"


def test_wildcard_cors_disables_credentials() -> None:
    settings = Settings(_env_file=None, cors_origins=["*"])
    assert settings.cors_allow_origins == ["*"]
    assert settings.allow_credentials is False


def test_secret_is_not_exposed_in_settings_repr() -> None:
    settings = Settings(
        _env_file=None,
        supabase_secret_key="super-secret-test-key",
        database_url="postgresql://user:super-db-secret@localhost/db",
        paystack_secret_key="sk_test_fake_not_for_storage",
    )
    rendered = repr(settings)
    assert "super-secret-test-key" not in rendered
    assert "super-db-secret" not in rendered
    assert "sk_test_fake_not_for_storage" not in rendered


def test_settings_load_without_paystack_variables() -> None:
    settings = Settings(_env_file=None)
    assert settings.paystack_secret_key is None
    assert settings.paystack_callback_url is None


def test_empty_paystack_secret_is_treated_as_missing() -> None:
    settings = Settings(_env_file=None, paystack_secret_key="  ", paystack_callback_url="")
    assert settings.paystack_secret_key is None
    assert settings.paystack_callback_url is None


def test_pool_bounds_are_validated() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, db_pool_min_size=6, db_pool_max_size=5)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, db_pool_max_size=0)

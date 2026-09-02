"""HTTP tests for health and root endpoints."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_health_returns_http_200(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_status_is_ok(client: TestClient) -> None:
    payload = client.get("/api/v1/health").json()
    assert payload["status"] == "ok"


def test_health_includes_service_metadata(client: TestClient) -> None:
    payload = client.get("/api/v1/health").json()
    assert payload["service"] == "SkillSignalZA API"
    assert payload["version"] == "0.1.0"
    assert payload["environment"] == "development"


def test_root_returns_service_metadata(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "SkillSignalZA API"
    assert payload["version"] == "0.1.0"
    assert payload["environment"] == "development"
    assert payload["health"] == "/api/v1/health"
    assert payload["docs"] == "/docs"


def test_app_starts_without_supabase_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_PUBLISHABLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        response = test_client.get("/api/v1/health")
    get_settings.cache_clear()
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_secrets_are_not_present_in_health_or_root_responses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "super-secret-test-key-do-not-leak"
    publishable = "publishable-test-key-do-not-leak"
    monkeypatch.setenv("SUPABASE_SECRET_KEY", secret)
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", publishable)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        bodies = [test_client.get("/").text, test_client.get("/api/v1/health").text]
    get_settings.cache_clear()
    for body in bodies:
        assert secret not in body
        assert publishable not in body
        assert "SUPABASE_SECRET_KEY" not in body
        assert "https://example.supabase.co" not in body

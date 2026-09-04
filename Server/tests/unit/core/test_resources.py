"""Application resource lifecycle tests. No real database or Storage network."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.core.resources import (
    bind_production_resources,
    close_app_resources,
    init_app_resource_state,
    persistence_configured,
    resolve_claim_resources,
    resolve_submission_resources,
)
from app.main import create_app


class _FakeSettings:
    database_url = SecretStr("postgresql://skillsignalza:test@localhost/skillsignalza_test")
    supabase_url = "https://example.invalid.supabase.co"
    supabase_secret_key = SecretStr("test-secret-not-for-production")
    supabase_publishable_key = None
    supabase_storage_bucket = "candidate-evidence"
    db_pool_min_size = 0
    db_pool_max_size = 5


class _FakePostgres:
    def __init__(self) -> None:
        self.closed = False

    @classmethod
    async def connect(cls, dsn: str, *, min_size: int = 0, max_size: int = 5) -> _FakePostgres:
        assert "example.invalid" not in dsn
        return cls()

    async def close(self) -> None:
        self.closed = True


class _FakeClient:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


class _FakeStorage:
    created: list[dict[str, Any]] = []

    def __init__(self, **kwargs: Any) -> None:
        type(self).created.append(kwargs)


def test_persistence_configured_requires_database_and_storage() -> None:
    empty = Settings(_env_file=None)
    assert persistence_configured(empty) is False
    assert persistence_configured(_FakeSettings()) is True  # type: ignore[arg-type]


def test_production_resource_lifecycle_closes_pool_and_http_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.core.resources as resources

    monkeypatch.setattr(resources, "PostgresAssessmentRepository", _FakePostgres)
    monkeypatch.setattr(resources, "SupabaseDocumentStorage", _FakeStorage)
    monkeypatch.setattr(resources.httpx, "AsyncClient", _FakeClient)
    _FakeStorage.created = []

    async def scenario() -> None:
        application = FastAPI()
        init_app_resource_state(application)
        await bind_production_resources(application, settings=_FakeSettings())  # type: ignore[arg-type]
        repository, storage = await resolve_submission_resources(application)
        assert repository is not None
        assert storage is not None
        postgres = application.state.postgres_repository
        client = application.state.http_client
        assert postgres is not None
        assert client is not None
        await close_app_resources(application)
        assert postgres.closed is True
        assert client.closed is True
        assert application.state.repository is None
        assert application.state.storage is None
        assert application.state.auth_verifier is None

    asyncio.run(scenario())
    assert _FakeStorage.created
    assert "test-secret-not-for-production" == _FakeStorage.created[0]["secret_key"]
    assert _FakeStorage.created[0]["supabase_url"] == "https://example.invalid.supabase.co"


def test_app_starts_without_persistence_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: Settings(_env_file=None),
    )
    monkeypatch.setattr(
        "app.core.resources.get_settings",
        lambda: Settings(_env_file=None),
    )
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        application = client.app
        application.state.auto_bind_resources = False
        missing = client.post(
            "/api/v1/assessments",
            data={"track": "software_engineering"},
            files={"cv": ("cv.pdf", b"%PDF-1.4 test", "application/pdf")},
        )
        claim_missing = client.post(
            "/api/v1/assessments/assessment-1/claim",
            json={"claim_token": "token"},
            headers={"Authorization": "Bearer access-token"},
        )
    get_settings.cache_clear()
    assert missing.status_code == 503
    assert missing.json()["error_code"] == "ASSESSMENT_SERVICE_UNAVAILABLE"
    assert claim_missing.status_code == 503
    assert claim_missing.json()["error_code"] == "CLAIM_SERVICE_UNAVAILABLE"


def test_bind_is_a_noop_when_unconfigured() -> None:
    async def scenario() -> None:
        application = FastAPI()
        init_app_resource_state(application)
        application.state.auto_bind_resources = False
        await bind_production_resources(application, settings=Settings(_env_file=None))
        repository, storage = await resolve_submission_resources(application)
        assert repository is None
        assert storage is None
        await close_app_resources(application)

    asyncio.run(scenario())


def test_resolve_lazy_binds_through_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.core.resources as resources

    async def fake_bind(application: FastAPI, settings: Settings | None = None) -> None:
        application.state.repository = "repo"
        application.state.storage = "store"

    monkeypatch.setattr(resources, "bind_production_resources", fake_bind)

    async def scenario() -> None:
        application = FastAPI()
        init_app_resource_state(application)
        repository, storage = await resolve_submission_resources(application)
        assert repository == "repo"
        assert storage == "store"
        again = await resolve_submission_resources(application)
        assert again == ("repo", "store")

    asyncio.run(scenario())


def test_storage_adapter_failure_closes_partial_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.core.resources as resources

    closed = {"repo": False, "http": False}

    class OkPostgres:
        @classmethod
        async def connect(cls, dsn: str, *, min_size: int = 0, max_size: int = 5) -> OkPostgres:
            return cls()

        async def close(self) -> None:
            closed["repo"] = True

    class BoomStorage:
        def __init__(self, **kwargs: Any) -> None:
            raise RuntimeError("adapter failed")

    class FakeClient:
        async def aclose(self) -> None:
            closed["http"] = True

    monkeypatch.setattr(resources, "PostgresAssessmentRepository", OkPostgres)
    monkeypatch.setattr(resources, "SupabaseDocumentStorage", BoomStorage)
    monkeypatch.setattr(resources.httpx, "AsyncClient", FakeClient)

    async def scenario() -> None:
        application = FastAPI()
        init_app_resource_state(application)
        await bind_production_resources(application, settings=_FakeSettings())  # type: ignore[arg-type]
        assert application.state.repository is None
        assert closed["repo"] is True
        assert closed["http"] is True

    asyncio.run(scenario())


def test_bind_failure_does_not_crash_or_leave_resources(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.core.resources as resources

    class BoomPostgres:
        @classmethod
        async def connect(cls, dsn: str, *, min_size: int = 0, max_size: int = 5) -> BoomPostgres:
            raise RuntimeError("connect failed")

    monkeypatch.setattr(resources, "PostgresAssessmentRepository", BoomPostgres)

    async def scenario() -> None:
        application = FastAPI()
        init_app_resource_state(application)
        application.state.auto_bind_resources = False
        await bind_production_resources(application, settings=_FakeSettings())  # type: ignore[arg-type]
        assert application.state.repository is None
        assert application.state.storage is None

    asyncio.run(scenario())


def test_resolve_returns_none_without_lock() -> None:
    async def scenario() -> None:
        application = FastAPI()
        application.state.repository = None
        application.state.storage = None
        application.state.auto_bind_resources = True
        repository, storage = await resolve_submission_resources(application)
        assert repository is None
        assert storage is None

    asyncio.run(scenario())


def test_close_swallows_resource_close_errors() -> None:
    class Boom:
        async def close(self) -> None:
            raise RuntimeError("pool close failed")

        async def aclose(self) -> None:
            raise RuntimeError("http close failed")

    async def scenario() -> None:
        application = FastAPI()
        init_app_resource_state(application)
        boom = Boom()
        application.state.postgres_repository = boom
        application.state.http_client = boom
        await close_app_resources(application)
        assert application.state.repository is None
        assert application.state.auth_verifier is None

    asyncio.run(scenario())


def test_bind_auth_verifier_without_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.core.resources as resources

    monkeypatch.setattr(resources, "PostgresAssessmentRepository", _FakePostgres)
    monkeypatch.setattr(resources.httpx, "AsyncClient", _FakeClient)
    _FakeStorage.created = []

    class AuthSettings:
        database_url = SecretStr("postgresql://skillsignalza:test@localhost/skillsignalza_test")
        supabase_url = "https://example.invalid.supabase.co"
        supabase_secret_key = None
        supabase_publishable_key = "publishable-not-secret"
        supabase_storage_bucket = "candidate-evidence"
        db_pool_min_size = 0
        db_pool_max_size = 5

    async def scenario() -> None:
        application = FastAPI()
        init_app_resource_state(application)
        application.state.auto_bind_resources = False
        await bind_production_resources(application, settings=AuthSettings())  # type: ignore[arg-type]
        assert application.state.storage is None
        assert application.state.repository is not None
        verifier = application.state.auth_verifier
        assert verifier is not None
        assert verifier._publishable_key == "publishable-not-secret"
        repository, auth = await resolve_claim_resources(application)
        assert repository is not None
        assert auth is verifier
        submission = await resolve_submission_resources(application)
        assert submission == (None, None)
        await close_app_resources(application)
        assert application.state.auth_verifier is None

    asyncio.run(scenario())
    assert _FakeStorage.created == []


def test_resolve_claim_lazy_binds_through_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.core.resources as resources

    async def fake_bind(application: FastAPI, settings: Settings | None = None) -> None:
        application.state.repository = "repo"
        application.state.auth_verifier = "verifier"

    monkeypatch.setattr(resources, "bind_production_resources", fake_bind)

    async def scenario() -> None:
        application = FastAPI()
        init_app_resource_state(application)
        repository, verifier = await resolve_claim_resources(application)
        assert repository == "repo"
        assert verifier == "verifier"
        again = await resolve_claim_resources(application)
        assert again == ("repo", "verifier")

    asyncio.run(scenario())


def test_resolve_claim_returns_none_without_lock() -> None:
    async def scenario() -> None:
        application = FastAPI()
        application.state.repository = None
        application.state.auth_verifier = None
        application.state.auto_bind_resources = True
        repository, verifier = await resolve_claim_resources(application)
        assert repository is None
        assert verifier is None

    asyncio.run(scenario())

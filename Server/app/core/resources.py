"""Process-lifetime assessment repository, private-storage, and auth resources.

Connections are opened on first use, never at import or application-factory
time. Secrets, DSNs, bearer tokens, and CV bytes are never logged.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from fastapi import FastAPI

from app.auth.supabase import SupabaseAuthVerifier
from app.core.auth import AuthVerifier
from app.core.config import Settings, get_settings
from app.repositories.interfaces import AssessmentRepository, DocumentStorage
from app.repositories.postgres import PostgresAssessmentRepository
from app.repositories.supabase import SupabaseDocumentStorage

logger = logging.getLogger(__name__)


def persistence_configured(settings: Settings | None = None) -> bool:
    """Return True when both PostgreSQL and Storage settings are present."""
    current = settings if settings is not None else get_settings()
    return (
        current.database_url is not None
        and bool(current.supabase_url)
        and current.supabase_secret_key is not None
    )


def claim_auth_configured(settings: Settings | None = None) -> bool:
    """Return True when Supabase Auth user verification can be bound."""
    current = settings if settings is not None else get_settings()
    return bool(getattr(current, "supabase_url", None)) and bool(
        getattr(current, "supabase_publishable_key", None)
    )


def init_app_resource_state(application: FastAPI) -> None:
    """Attach empty resource slots. Must not open sockets or pools."""
    application.state.repository = None
    application.state.storage = None
    application.state.http_client = None
    application.state.postgres_repository = None
    application.state.auth_verifier = None
    application.state.resource_lock = asyncio.Lock()
    application.state.auto_bind_resources = True


async def bind_production_resources(application: FastAPI, settings: Settings | None = None) -> None:
    """Open missing PostgreSQL, Storage, and Auth adapters without replacing owned ones."""
    current = settings if settings is not None else get_settings()
    database_url = getattr(current, "database_url", None)
    supabase_url = getattr(current, "supabase_url", None)
    secret_key = getattr(current, "supabase_secret_key", None)
    publishable_key = getattr(current, "supabase_publishable_key", None)

    existing_postgres = getattr(application.state, "postgres_repository", None)
    existing_repository = getattr(application.state, "repository", None)
    existing_client = getattr(application.state, "http_client", None)
    existing_storage = getattr(application.state, "storage", None)
    existing_verifier = getattr(application.state, "auth_verifier", None)

    need_postgres = (
        database_url is not None and existing_postgres is None and existing_repository is None
    )
    need_storage = bool(supabase_url) and secret_key is not None and existing_storage is None
    need_auth = bool(supabase_url) and bool(publishable_key) and existing_verifier is None
    if not need_postgres and not need_storage and not need_auth:
        return

    created_repository = None
    created_client = None
    storage = None
    auth_verifier = None

    if need_postgres:
        try:
            created_repository = await PostgresAssessmentRepository.connect(
                database_url.get_secret_value(),
                min_size=current.db_pool_min_size,
                max_size=current.db_pool_max_size,
            )
        except Exception:
            logger.error("failed to open assessment repository")
            return

    repository = existing_postgres or existing_repository or created_repository
    client = existing_client
    if (need_storage or need_auth) and client is None:
        created_client = httpx.AsyncClient()
        client = created_client

    if need_storage and repository is not None and client is not None:
        try:
            storage = SupabaseDocumentStorage(
                supabase_url=str(supabase_url),
                secret_key=secret_key.get_secret_value(),
                bucket=current.supabase_storage_bucket,
                client=client,
            )
        except Exception:
            logger.error("failed to create document storage adapter")
            await _close_created_resources(created_repository, created_client)
            return

    if need_auth and client is not None:
        try:
            auth_verifier = SupabaseAuthVerifier(
                supabase_url=str(supabase_url),
                publishable_key=str(publishable_key),
                client=client,
            )
        except Exception:
            logger.error("failed to create auth verifier")
            await _close_created_resources(created_repository, created_client)
            return

    if created_repository is not None:
        application.state.postgres_repository = created_repository
        application.state.repository = created_repository
    if created_client is not None:
        application.state.http_client = created_client
    if storage is not None:
        application.state.storage = storage
    if auth_verifier is not None:
        application.state.auth_verifier = auth_verifier


async def resolve_submission_resources(
    application: FastAPI,
) -> tuple[AssessmentRepository | None, DocumentStorage | None]:
    """Return injected or lazily bound production adapters."""
    repository = getattr(application.state, "repository", None)
    storage = getattr(application.state, "storage", None)
    if repository is not None and storage is not None:
        return repository, storage
    if not getattr(application.state, "auto_bind_resources", True):
        return None, None
    lock = getattr(application.state, "resource_lock", None)
    if lock is None:
        return None, None
    async with lock:
        repository = getattr(application.state, "repository", None)
        storage = getattr(application.state, "storage", None)
        if repository is not None and storage is not None:
            return repository, storage
        await bind_production_resources(application)
        repository = getattr(application.state, "repository", None)
        storage = getattr(application.state, "storage", None)
        if repository is not None and storage is not None:
            return repository, storage
        return None, None


async def resolve_claim_resources(
    application: FastAPI,
) -> tuple[AssessmentRepository | None, AuthVerifier | None]:
    """Return injected or lazily bound claim repository and auth verifier."""
    repository = getattr(application.state, "repository", None)
    verifier = getattr(application.state, "auth_verifier", None)
    if repository is not None and verifier is not None:
        return repository, verifier
    if not getattr(application.state, "auto_bind_resources", True):
        return None, None
    lock = getattr(application.state, "resource_lock", None)
    if lock is None:
        return None, None
    async with lock:
        repository = getattr(application.state, "repository", None)
        verifier = getattr(application.state, "auth_verifier", None)
        if repository is not None and verifier is not None:
            return repository, verifier
        if not claim_auth_configured():
            return None, None
        await bind_production_resources(application)
        repository = getattr(application.state, "repository", None)
        verifier = getattr(application.state, "auth_verifier", None)
        if repository is not None and verifier is not None:
            return repository, verifier
        return None, None


async def close_app_resources(application: FastAPI) -> None:
    """Close owned pool and HTTP client without leaking connection details."""
    postgres = getattr(application.state, "postgres_repository", None)
    client = getattr(application.state, "http_client", None)
    application.state.repository = None
    application.state.storage = None
    application.state.postgres_repository = None
    application.state.http_client = None
    application.state.auth_verifier = None
    if postgres is not None:
        try:
            await postgres.close()
        except Exception:
            logger.error("failed to close assessment repository")
    if client is not None:
        try:
            await client.aclose()
        except Exception:
            logger.error("failed to close storage HTTP client")


def submission_overrides(application: FastAPI) -> dict[str, Any]:
    """Optional test/runtime injections for the anonymous submission service."""
    names = (
        "assessed_at",
        "submitted_at",
        "identity_factory",
        "claim_token_factory",
        "retrieve_link",
        "run_pipeline",
        "load_report",
    )
    overrides: dict[str, Any] = {}
    for name in names:
        value = getattr(application.state, name, None)
        if value is not None:
            overrides[name] = value
    return overrides


async def _close_created_resources(repository: Any | None, client: Any | None) -> None:
    """Close resources created by the current bind attempt only."""
    if client is not None:
        try:
            await client.aclose()
        except Exception:
            logger.error("failed to close storage HTTP client")
    if repository is not None:
        try:
            await repository.close()
        except Exception:
            logger.error("failed to close assessment repository")

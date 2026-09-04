"""Process-lifetime assessment repository and private-storage resources.

Connections are opened on first anonymous-submission use, never at import
or application-factory time. Secrets, DSNs, and CV bytes are never logged.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from fastapi import FastAPI

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


def init_app_resource_state(application: FastAPI) -> None:
    """Attach empty resource slots. Must not open sockets or pools."""
    application.state.repository = None
    application.state.storage = None
    application.state.http_client = None
    application.state.postgres_repository = None
    application.state.resource_lock = asyncio.Lock()
    application.state.auto_bind_resources = True


async def bind_production_resources(application: FastAPI, settings: Settings | None = None) -> None:
    """Open a shared PostgreSQL pool and Storage HTTP client when configured."""
    current = settings if settings is not None else get_settings()
    if not persistence_configured(current):
        return
    assert current.database_url is not None
    assert current.supabase_secret_key is not None
    assert current.supabase_url is not None
    try:
        repository = await PostgresAssessmentRepository.connect(
            current.database_url.get_secret_value(),
            min_size=current.db_pool_min_size,
            max_size=current.db_pool_max_size,
        )
    except Exception:
        logger.error("failed to open assessment repository")
        return
    client = httpx.AsyncClient()
    try:
        storage = SupabaseDocumentStorage(
            supabase_url=current.supabase_url,
            secret_key=current.supabase_secret_key.get_secret_value(),
            bucket=current.supabase_storage_bucket,
            client=client,
        )
    except Exception:
        logger.error("failed to create document storage adapter")
        await client.aclose()
        await repository.close()
        return
    application.state.postgres_repository = repository
    application.state.repository = repository
    application.state.http_client = client
    application.state.storage = storage


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


async def close_app_resources(application: FastAPI) -> None:
    """Close owned pool and HTTP client without leaking connection details."""
    postgres = getattr(application.state, "postgres_repository", None)
    client = getattr(application.state, "http_client", None)
    application.state.repository = None
    application.state.storage = None
    application.state.postgres_repository = None
    application.state.http_client = None
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

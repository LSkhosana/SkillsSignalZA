"""Vendor-neutral persistence ports.

Domain and engine code may depend on these protocols. Adapters must not
leak psycopg, Supabase, or HTTP client types through this module.
"""

from __future__ import annotations

from typing import Any, Protocol

from app.repositories.records import (
    AssessmentRecord,
    AssessmentRunRecord,
    PersistenceBundle,
    PersistWriteResult,
)


class AssessmentRepository(Protocol):
    """PostgreSQL-backed assessment persistence port."""

    async def persist_bundle(self, bundle: PersistenceBundle) -> PersistWriteResult:
        """Insert or no-op one complete assessment/run bundle in one transaction."""

    async def get_assessment(self, assessment_id: str) -> AssessmentRecord | None:
        """Return assessment lifecycle metadata."""

    async def get_run(self, run_id: str) -> AssessmentRunRecord | None:
        """Return one immutable run with sources, evidence, and document metadata."""

    async def get_latest_run(self, assessment_id: str) -> AssessmentRunRecord | None:
        """Return the run referenced by assessments.latest_run_id."""


class DocumentStorage(Protocol):
    """Private object-storage port for original CV bytes."""

    async def put_private_document(
        self,
        *,
        assessment_id: str,
        document_id: str,
        file_bytes: bytes,
        media_type: str,
        original_filename: str,
    ) -> dict[str, Any]:
        """Store exact CV bytes under an opaque key and return document metadata."""

    async def get_private_document(self, storage_path: str) -> bytes:
        """Return previously stored exact bytes."""

    async def delete_private_document(self, storage_path: str) -> None:
        """Delete one private object. Used for compensation and future retention."""

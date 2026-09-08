"""Vendor-neutral persistence ports.

Domain and engine code may depend on these protocols. Adapters must not
leak psycopg, Supabase, or HTTP client types through this module.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from app.repositories.records import (
    AssessmentRecord,
    AssessmentRunRecord,
    CheckoutBeginResult,
    ClaimWriteResult,
    FulfillmentResult,
    PaymentRecord,
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

    async def claim_assessment(
        self,
        *,
        assessment_id: str,
        authenticated_user_id: str,
        presented_claim_token_hash: str,
        claimed_at: datetime,
    ) -> ClaimWriteResult:
        """Atomically attach a verified user as owner of one unclaimed assessment."""

    async def begin_checkout_attempt(
        self,
        *,
        assessment_id: str,
        owner_user_id: str,
        payment_id: str,
        provider_reference: str,
        product_id: str,
        billing_model: str,
        provider: str,
        amount_minor: int,
        currency: str,
    ) -> CheckoutBeginResult:
        """Atomically create one INITIALIZING attempt or return the existing active checkout."""

    async def mark_checkout_initialized(
        self,
        *,
        payment_id: str,
        authorization_url: str,
    ) -> PaymentRecord | None:
        """Persist INITIALIZED plus the provider authorization URL."""

    async def mark_checkout_initialization_failed(self, *, payment_id: str) -> PaymentRecord | None:
        """Retain a failed attempt without leaving an active customer checkout."""

    async def get_payment_by_provider_reference(
        self, provider_reference: str
    ) -> PaymentRecord | None:
        """Return the local payment attempt for a provider reference."""

    async def fulfill_payment_and_unlock(
        self,
        *,
        payment_id: str,
        provider_reference: str,
        provider_transaction_id: str,
        verified_amount_minor: int,
        verified_currency: str,
        paid_at: datetime,
    ) -> FulfillmentResult:
        """Atomically mark payment SUCCEEDED and transition PREVIEW to UNLOCKED."""


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

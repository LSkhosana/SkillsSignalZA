"""Package P checkout service tests. Fakes only; no Paystack or Supabase."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from app.commerce.errors import PaymentProviderError, PaymentProviderRejected
from app.repositories.records import AssessmentRecord, AssessmentRunRecord
from app.services.assessment_payment import (
    ERROR_PAYMENT_EMAIL_REQUIRED,
    fulfill_verified_paystack_payment,
    initialize_readiness_checkout,
    usable_verified_email,
)
from tests.integration.test_payment_checkout import EMAIL, FakePaymentProvider
from tests.unit.services.test_anonymous_assessment import IDENTITY, RecordingRepository

CLAIMED_AT = datetime(2026, 9, 4, 13, 0, tzinfo=UTC)
USER_A = "user-verified-a"


def _seed(repo: RecordingRepository) -> None:
    repo.assessments[IDENTITY.assessment_id] = AssessmentRecord(
        assessment_id=IDENTITY.assessment_id,
        candidate_ref=IDENTITY.candidate_ref,
        track="software_engineering",
        access_state="PREVIEW",
        claim_token_hash=None,
        claimed_at=CLAIMED_AT,
        latest_run_id=IDENTITY.run_id,
        expires_at=None,
        created_at=CLAIMED_AT,
        updated_at=CLAIMED_AT,
        owner_user_id=USER_A,
    )
    repo.runs[IDENTITY.run_id] = AssessmentRunRecord(
        run_id=IDENTITY.run_id,
        assessment_id=IDENTITY.assessment_id,
        state="COMPLETED",
        error_code=None,
        pipeline_version="assessment.pipeline.v1",
        contract_version="1.2.0",
        rubric_version="V2",
        track="software_engineering",
        assessment_input={},
        scoring_context={},
        assessment_result={},
        review_flags=[],
        stages=[],
        assessed_at=CLAIMED_AT,
        created_at=CLAIMED_AT,
        source_records=[],
        evidence_facts=[],
        document=None,
    )


def test_usable_verified_email_rejects_blank_values() -> None:
    assert usable_verified_email(EMAIL) == EMAIL
    assert usable_verified_email(None) is None
    assert usable_verified_email(" ") is None
    assert usable_verified_email("not-an-email") is None


def test_initialize_requires_verified_email() -> None:
    repo = RecordingRepository()
    _seed(repo)
    outcome = asyncio.run(
        initialize_readiness_checkout(
            repository=repo,
            provider=FakePaymentProvider(),
            assessment_id=IDENTITY.assessment_id,
            owner_user_id=USER_A,
            email="",
        )
    )
    assert outcome["error_code"] == ERROR_PAYMENT_EMAIL_REQUIRED


def test_fulfill_requires_provider_verify_before_unlock() -> None:
    repo = RecordingRepository()
    _seed(repo)
    provider = FakePaymentProvider()
    checkout = asyncio.run(
        initialize_readiness_checkout(
            repository=repo,
            provider=provider,
            assessment_id=IDENTITY.assessment_id,
            owner_user_id=USER_A,
            email=EMAIL,
            payment_id_factory=lambda: "pay_fixed_test_id",
            reference_factory=lambda: "psk_fixed_test_reference",
        )
    )
    assert checkout["state"] == "PAYMENT_INITIALIZED"
    provider.verify_error = PaymentProviderRejected()
    denied = asyncio.run(
        fulfill_verified_paystack_payment(
            repository=repo,
            provider=provider,
            provider_reference="psk_fixed_test_reference",
        )
    )
    assert denied == "conflict"
    assert repo.assessments[IDENTITY.assessment_id].access_state == "PREVIEW"
    provider.verify_error = None
    unlocked = asyncio.run(
        fulfill_verified_paystack_payment(
            repository=repo,
            provider=provider,
            provider_reference="psk_fixed_test_reference",
        )
    )
    assert unlocked == "unlocked"
    assert repo.assessments[IDENTITY.assessment_id].access_state == "UNLOCKED"
    replay = asyncio.run(
        fulfill_verified_paystack_payment(
            repository=repo,
            provider=provider,
            provider_reference="psk_fixed_test_reference",
        )
    )
    assert replay == "idempotent"


def test_initialize_covers_validation_and_provider_branches() -> None:
    repo = RecordingRepository()
    _seed(repo)
    provider = FakePaymentProvider()
    empty = asyncio.run(
        initialize_readiness_checkout(
            repository=repo,
            provider=provider,
            assessment_id="  ",
            owner_user_id=USER_A,
            email=EMAIL,
        )
    )
    assert empty["error_code"] == "ASSESSMENT_NOT_FOUND"
    invalid_owner = asyncio.run(
        initialize_readiness_checkout(
            repository=repo,
            provider=provider,
            assessment_id=IDENTITY.assessment_id,
            owner_user_id="  ",
            email=EMAIL,
        )
    )
    assert invalid_owner["error_code"] == "AUTH_INVALID"
    repo.begin_checkout_error = RuntimeError("db")
    unavailable = asyncio.run(
        initialize_readiness_checkout(
            repository=repo,
            provider=provider,
            assessment_id=IDENTITY.assessment_id,
            owner_user_id=USER_A,
            email=EMAIL,
        )
    )
    assert unavailable["error_code"] == "PAYMENT_SERVICE_UNAVAILABLE"
    repo.begin_checkout_error = None
    provider.initialize_error = PaymentProviderError()
    rejected = asyncio.run(
        initialize_readiness_checkout(
            repository=repo,
            provider=provider,
            assessment_id=IDENTITY.assessment_id,
            owner_user_id=USER_A,
            email=EMAIL,
            payment_id_factory=lambda: "pay_err",
            reference_factory=lambda: "psk_err",
        )
    )
    assert rejected["error_code"] == "PAYMENT_INITIALIZATION_FAILED"
    provider.initialize_error = RuntimeError("boom")
    crashed = asyncio.run(
        initialize_readiness_checkout(
            repository=repo,
            provider=provider,
            assessment_id=IDENTITY.assessment_id,
            owner_user_id=USER_A,
            email=EMAIL,
            payment_id_factory=lambda: "pay_crash",
            reference_factory=lambda: "psk_crash",
        )
    )
    assert crashed["error_code"] == "PAYMENT_SERVICE_UNAVAILABLE"


def test_fulfill_covers_retry_and_conflict_paths() -> None:
    repo = RecordingRepository()
    provider = FakePaymentProvider()
    assert (
        asyncio.run(
            fulfill_verified_paystack_payment(
                repository=repo, provider=provider, provider_reference="  "
            )
        )
        == "ignored"
    )
    assert (
        asyncio.run(
            fulfill_verified_paystack_payment(
                repository=repo, provider=provider, provider_reference="missing"
            )
        )
        == "retry"
    )
    _seed(repo)
    asyncio.run(
        initialize_readiness_checkout(
            repository=repo,
            provider=provider,
            assessment_id=IDENTITY.assessment_id,
            owner_user_id=USER_A,
            email=EMAIL,
            payment_id_factory=lambda: "pay_fixed_test_id",
            reference_factory=lambda: "psk_fixed_test_reference",
        )
    )
    provider.verify_error = RuntimeError("boom")
    assert (
        asyncio.run(
            fulfill_verified_paystack_payment(
                repository=repo,
                provider=provider,
                provider_reference="psk_fixed_test_reference",
            )
        )
        == "retry"
    )
    provider.verify_error = PaymentProviderError()
    assert (
        asyncio.run(
            fulfill_verified_paystack_payment(
                repository=repo,
                provider=provider,
                provider_reference="psk_fixed_test_reference",
            )
        )
        == "conflict"
    )
    provider.verify_error = None
    repo.fulfill_error = RuntimeError("db")
    assert (
        asyncio.run(
            fulfill_verified_paystack_payment(
                repository=repo,
                provider=provider,
                provider_reference="psk_fixed_test_reference",
            )
        )
        == "retry"
    )

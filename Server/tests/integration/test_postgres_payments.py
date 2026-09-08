"""PostgreSQL payment entitlement integration tests.

Requires DATABASE_URL. GitHub Actions supplies ordinary PostgreSQL 16.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from psycopg import AsyncConnection, errors
from psycopg.rows import dict_row

from app.repositories.postgres import MIGRATION_0004_PATH, PostgresAssessmentRepository
from tests.integration.test_postgres_claim import USER_A, USER_B, _digest, _seed
from tests.integration.test_postgres_persistence import DATABASE_URL, _run_with_repository

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL is required")

CLAIMED_AT = datetime(2026, 9, 4, 13, 0, tzinfo=UTC)
PAID_AT = datetime(2026, 9, 8, 9, 0, tzinfo=UTC)


async def _owned(repository: PostgresAssessmentRepository) -> str:
    suffix = uuid4().hex
    outcome = await _seed(
        repository,
        assessment_id=f"pay-assessment-{suffix}",
        run_id=f"pay-run-{suffix}",
    )
    assessment_id = outcome["assessment_id"]
    claimed = await repository.claim_assessment(
        assessment_id=assessment_id,
        authenticated_user_id=USER_A,
        presented_claim_token_hash=_digest(),
        claimed_at=CLAIMED_AT,
    )
    assert claimed.status == "claimed"
    return assessment_id


def test_migration_0004_creates_server_only_payment_table() -> None:
    async def body(repository: PostgresAssessmentRepository) -> None:
        assert DATABASE_URL is not None
        sql = MIGRATION_0004_PATH.read_text(encoding="utf-8")
        assert "assessment_payments" in sql
        assert "auth.users" not in sql
        assert "PAYSTACK" not in sql
        async with await AsyncConnection.connect(DATABASE_URL, row_factory=dict_row) as connection:
            table = await connection.execute(
                """
                SELECT c.relrowsecurity
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relname = 'assessment_payments'
                """
            )
            row = await table.fetchone()
            assert row is not None
            assert row["relrowsecurity"] is True
            policies = await connection.execute(
                "SELECT tablename FROM pg_policies WHERE tablename = 'assessment_payments'"
            )
            assert await policies.fetchall() == []
            indexes = await connection.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public' AND tablename = 'assessment_payments'
                """
            )
            names = {item["indexname"] for item in await indexes.fetchall()}
            assert "assessment_payments_provider_reference_uidx" in names
            assert "assessment_payments_provider_transaction_id_uidx" in names
            assert "assessment_payments_one_active_checkout_uidx" in names

    _run_with_repository(body)


def test_failed_initialization_is_retained_and_allows_retry() -> None:
    async def body(repository: PostgresAssessmentRepository) -> None:
        assessment_id = await _owned(repository)
        first = await repository.begin_checkout_attempt(
            assessment_id=assessment_id,
            owner_user_id=USER_A,
            payment_id="pay-fail-1",
            provider_reference="psk-fail-1",
            product_id="readiness_report_v1",
            billing_model="one_time",
            provider="paystack",
            amount_minor=15900,
            currency="ZAR",
        )
        assert first.status == "created"
        failed = await repository.mark_checkout_initialization_failed(payment_id="pay-fail-1")
        assert failed is not None
        assert failed.status == "INITIALIZATION_FAILED"
        second = await repository.begin_checkout_attempt(
            assessment_id=assessment_id,
            owner_user_id=USER_A,
            payment_id="pay-retry-1",
            provider_reference="psk-retry-1",
            product_id="readiness_report_v1",
            billing_model="one_time",
            provider="paystack",
            amount_minor=15900,
            currency="ZAR",
        )
        assert second.status == "created"
        assert second.payment is not None
        assert second.payment.payment_id == "pay-retry-1"

    _run_with_repository(body)


def test_one_active_checkout_and_unique_provider_ids() -> None:
    async def body(repository: PostgresAssessmentRepository) -> None:
        assessment_id = await _owned(repository)
        first = await repository.begin_checkout_attempt(
            assessment_id=assessment_id,
            owner_user_id=USER_A,
            payment_id="pay-active-1",
            provider_reference="psk-active-1",
            product_id="readiness_report_v1",
            billing_model="one_time",
            provider="paystack",
            amount_minor=15900,
            currency="ZAR",
        )
        assert first.status == "created"
        busy = await repository.begin_checkout_attempt(
            assessment_id=assessment_id,
            owner_user_id=USER_A,
            payment_id="pay-active-2",
            provider_reference="psk-active-2",
            product_id="readiness_report_v1",
            billing_model="one_time",
            provider="paystack",
            amount_minor=15900,
            currency="ZAR",
        )
        assert busy.status == "initializing"
        initialized = await repository.mark_checkout_initialized(
            payment_id="pay-active-1",
            authorization_url="https://checkout.paystack.com/test",
        )
        assert initialized is not None
        reuse = await repository.begin_checkout_attempt(
            assessment_id=assessment_id,
            owner_user_id=USER_A,
            payment_id="pay-active-3",
            provider_reference="psk-active-3",
            product_id="readiness_report_v1",
            billing_model="one_time",
            provider="paystack",
            amount_minor=15900,
            currency="ZAR",
        )
        assert reuse.status == "existing_initialized"
        assert reuse.payment is not None
        assert reuse.payment.provider_reference == "psk-active-1"
        assert DATABASE_URL is not None
        async with await AsyncConnection.connect(DATABASE_URL, row_factory=dict_row) as connection:
            with pytest.raises(errors.UniqueViolation):
                await connection.execute(
                    """
                    INSERT INTO assessment_payments (
                        payment_id, assessment_id, owner_user_id, product_id, billing_model,
                        provider, provider_reference, amount_minor, currency, status
                    )
                    VALUES (
                        'pay-dup-ref', %s, %s, 'readiness_report_v1', 'one_time',
                        'paystack', 'psk-active-1', 15900, 'ZAR', 'INITIALIZATION_FAILED'
                    )
                    """,
                    (assessment_id, USER_A),
                )
            await connection.rollback()

    _run_with_repository(body)


def test_atomic_fulfillment_unlocks_without_mutating_history() -> None:
    async def body(repository: PostgresAssessmentRepository) -> None:
        assessment_id = await _owned(repository)
        before = await repository.get_assessment(assessment_id)
        before_run = await repository.get_latest_run(assessment_id)
        assert before is not None
        assert before_run is not None
        began = await repository.begin_checkout_attempt(
            assessment_id=assessment_id,
            owner_user_id=USER_A,
            payment_id="pay-unlock-1",
            provider_reference="psk-unlock-1",
            product_id="readiness_report_v1",
            billing_model="one_time",
            provider="paystack",
            amount_minor=15900,
            currency="ZAR",
        )
        assert began.status == "created"
        await repository.mark_checkout_initialized(
            payment_id="pay-unlock-1",
            authorization_url="https://checkout.paystack.com/unlock",
        )
        result = await repository.fulfill_payment_and_unlock(
            payment_id="pay-unlock-1",
            provider_reference="psk-unlock-1",
            provider_transaction_id="9001",
            verified_amount_minor=15900,
            verified_currency="ZAR",
            paid_at=PAID_AT,
        )
        assert result.status == "unlocked"
        after = await repository.get_assessment(assessment_id)
        after_run = await repository.get_latest_run(assessment_id)
        assert after is not None
        assert after_run is not None
        assert after.access_state == "UNLOCKED"
        assert after.candidate_ref == before.candidate_ref
        assert after.owner_user_id == USER_A
        assert after.claimed_at == before.claimed_at
        assert after.latest_run_id == before.latest_run_id
        assert after_run.assessment_result == before_run.assessment_result
        assert after_run.scoring_context == before_run.scoring_context
        assert after_run.source_records == before_run.source_records
        assert after_run.evidence_facts == before_run.evidence_facts
        replay = await repository.fulfill_payment_and_unlock(
            payment_id="pay-unlock-1",
            provider_reference="psk-unlock-1",
            provider_transaction_id="9001",
            verified_amount_minor=15900,
            verified_currency="ZAR",
            paid_at=PAID_AT,
        )
        assert replay.status == "idempotent"

    _run_with_repository(body)


def test_fulfillment_fails_closed_on_owner_amount_and_duplicate_transaction() -> None:
    async def body(repository: PostgresAssessmentRepository) -> None:
        first_id = await _owned(repository)
        began = await repository.begin_checkout_attempt(
            assessment_id=first_id,
            owner_user_id=USER_A,
            payment_id="pay-closed-1",
            provider_reference="psk-closed-1",
            product_id="readiness_report_v1",
            billing_model="one_time",
            provider="paystack",
            amount_minor=15900,
            currency="ZAR",
        )
        assert began.status == "created"
        await repository.mark_checkout_initialized(
            payment_id="pay-closed-1",
            authorization_url="https://checkout.paystack.com/closed",
        )
        wrong_amount = await repository.fulfill_payment_and_unlock(
            payment_id="pay-closed-1",
            provider_reference="psk-closed-1",
            provider_transaction_id="9002",
            verified_amount_minor=1,
            verified_currency="ZAR",
            paid_at=PAID_AT,
        )
        assert wrong_amount.status == "conflict"
        wrong_currency = await repository.fulfill_payment_and_unlock(
            payment_id="pay-closed-1",
            provider_reference="psk-closed-1",
            provider_transaction_id="9002",
            verified_amount_minor=15900,
            verified_currency="NGN",
            paid_at=PAID_AT,
        )
        assert wrong_currency.status == "conflict"
        wrong_reference = await repository.fulfill_payment_and_unlock(
            payment_id="pay-closed-1",
            provider_reference="other-ref",
            provider_transaction_id="9002",
            verified_amount_minor=15900,
            verified_currency="ZAR",
            paid_at=PAID_AT,
        )
        assert wrong_reference.status == "conflict"
        unlocked = await repository.fulfill_payment_and_unlock(
            payment_id="pay-closed-1",
            provider_reference="psk-closed-1",
            provider_transaction_id="9002",
            verified_amount_minor=15900,
            verified_currency="ZAR",
            paid_at=PAID_AT,
        )
        assert unlocked.status == "unlocked"
        second_id = await _owned(repository)
        second = await repository.begin_checkout_attempt(
            assessment_id=second_id,
            owner_user_id=USER_A,
            payment_id="pay-closed-2",
            provider_reference="psk-closed-2",
            product_id="readiness_report_v1",
            billing_model="one_time",
            provider="paystack",
            amount_minor=15900,
            currency="ZAR",
        )
        assert second.status == "created"
        await repository.mark_checkout_initialized(
            payment_id="pay-closed-2",
            authorization_url="https://checkout.paystack.com/closed-2",
        )
        duplicate = await repository.fulfill_payment_and_unlock(
            payment_id="pay-closed-2",
            provider_reference="psk-closed-2",
            provider_transaction_id="9002",
            verified_amount_minor=15900,
            verified_currency="ZAR",
            paid_at=PAID_AT,
        )
        assert duplicate.status == "conflict"
        second_assessment = await repository.get_assessment(second_id)
        assert second_assessment is not None
        assert second_assessment.access_state == "PREVIEW"
        wrong_owner = await repository.begin_checkout_attempt(
            assessment_id=second_id,
            owner_user_id=USER_B,
            payment_id="pay-closed-3",
            provider_reference="psk-closed-3",
            product_id="readiness_report_v1",
            billing_model="one_time",
            provider="paystack",
            amount_minor=15900,
            currency="ZAR",
        )
        assert wrong_owner.status == "not_owned"

    _run_with_repository(body)


def test_concurrent_fulfillment_cannot_double_apply() -> None:
    async def body(repository: PostgresAssessmentRepository) -> None:
        assessment_id = await _owned(repository)
        began = await repository.begin_checkout_attempt(
            assessment_id=assessment_id,
            owner_user_id=USER_A,
            payment_id="pay-race-1",
            provider_reference="psk-race-1",
            product_id="readiness_report_v1",
            billing_model="one_time",
            provider="paystack",
            amount_minor=15900,
            currency="ZAR",
        )
        assert began.status == "created"
        await repository.mark_checkout_initialized(
            payment_id="pay-race-1",
            authorization_url="https://checkout.paystack.com/race",
        )

        async def fulfill() -> str:
            result = await repository.fulfill_payment_and_unlock(
                payment_id="pay-race-1",
                provider_reference="psk-race-1",
                provider_transaction_id="9003",
                verified_amount_minor=15900,
                verified_currency="ZAR",
                paid_at=PAID_AT,
            )
            return result.status

        statuses = await asyncio.gather(fulfill(), fulfill())
        assert set(statuses) <= {"unlocked", "idempotent"}
        assert "unlocked" in statuses
        assessment = await repository.get_assessment(assessment_id)
        assert assessment is not None
        assert assessment.access_state == "UNLOCKED"

    _run_with_repository(body)

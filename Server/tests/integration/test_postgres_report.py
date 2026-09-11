"""PostgreSQL unlocked-report delivery integration tests.

Requires DATABASE_URL. GitHub Actions supplies ordinary PostgreSQL 16.
Never points at live Supabase.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from psycopg import AsyncConnection

from app.engine.schema_registry import draft_validator
from app.repositories.postgres import PostgresAssessmentRepository
from app.services.assessment_report import (
    ERROR_REPORT_LOCKED,
    deliver_unlocked_readiness_report,
)
from tests.integration.test_postgres_claim import USER_A, USER_B, _digest, _seed
from tests.integration.test_postgres_persistence import DATABASE_URL, _run_with_repository

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL is required")

CLAIMED_AT = datetime(2026, 9, 4, 13, 0, tzinfo=UTC)


async def _owned_completed(repository: PostgresAssessmentRepository) -> str:
    suffix = uuid4().hex
    outcome = await _seed(
        repository,
        assessment_id=f"report-assessment-{suffix}",
        run_id=f"report-run-{suffix}",
    )
    assessment_id = outcome["assessment_id"]
    claimed = await repository.claim_assessment(
        assessment_id=assessment_id,
        authenticated_user_id=USER_A,
        presented_claim_token_hash=_digest(),
        claimed_at=CLAIMED_AT,
    )
    assert claimed.status == "claimed"
    assert claimed.access_state == "PREVIEW"
    assert DATABASE_URL is not None
    async with await AsyncConnection.connect(DATABASE_URL, autocommit=True) as connection:
        await connection.execute(
            "UPDATE assessments SET access_state = 'UNLOCKED' WHERE assessment_id = %s",
            (assessment_id,),
        )
    unlocked = await repository.get_assessment(assessment_id)
    assert unlocked is not None
    assert unlocked.access_state == "UNLOCKED"
    return assessment_id


def test_unlocked_owner_reads_persisted_report_without_writes() -> None:
    async def body(repository: PostgresAssessmentRepository) -> None:
        assessment_id = await _owned_completed(repository)
        before = await repository.get_assessment(assessment_id)
        before_run = await repository.get_latest_run(assessment_id)
        assert before is not None
        assert before_run is not None
        first = await deliver_unlocked_readiness_report(
            repository=repository,
            assessment_id=assessment_id,
            owner_user_id=USER_A,
        )
        draft_validator("readiness_report.schema.json").validate(first)
        assert first["assessment_id"] == assessment_id
        assert first["run_id"] == before_run.run_id
        second = await deliver_unlocked_readiness_report(
            repository=repository,
            assessment_id=assessment_id,
            owner_user_id=USER_A,
        )
        assert first == second
        after = await repository.get_assessment(assessment_id)
        after_run = await repository.get_latest_run(assessment_id)
        assert after is not None
        assert after_run is not None
        assert after.access_state == "UNLOCKED"
        assert after.owner_user_id == USER_A
        assert after.updated_at == before.updated_at
        assert after_run.assessment_result == before_run.assessment_result

    _run_with_repository(body)


def test_preview_owner_and_wrong_owner_do_not_receive_report() -> None:
    async def body(repository: PostgresAssessmentRepository) -> None:
        suffix = uuid4().hex
        outcome = await _seed(
            repository,
            assessment_id=f"locked-assessment-{suffix}",
            run_id=f"locked-run-{suffix}",
        )
        assessment_id = outcome["assessment_id"]
        claimed = await repository.claim_assessment(
            assessment_id=assessment_id,
            authenticated_user_id=USER_A,
            presented_claim_token_hash=_digest(),
            claimed_at=CLAIMED_AT,
        )
        assert claimed.status == "claimed"
        locked = await deliver_unlocked_readiness_report(
            repository=repository,
            assessment_id=assessment_id,
            owner_user_id=USER_A,
        )
        assert locked["error_code"] == ERROR_REPORT_LOCKED
        assert "category_breakdown" not in locked
        assert DATABASE_URL is not None
        async with await AsyncConnection.connect(DATABASE_URL, autocommit=True) as connection:
            await connection.execute(
                "UPDATE assessments SET access_state = 'UNLOCKED' WHERE assessment_id = %s",
                (assessment_id,),
            )
        denied = await deliver_unlocked_readiness_report(
            repository=repository,
            assessment_id=assessment_id,
            owner_user_id=USER_B,
        )
        assert denied["error_code"] == "ASSESSMENT_NOT_OWNED"
        assert "criterion_breakdown" not in denied
        still = await repository.get_assessment(assessment_id)
        assert still is not None
        assert still.access_state == "UNLOCKED"
        assert still.owner_user_id == USER_A

    _run_with_repository(body)

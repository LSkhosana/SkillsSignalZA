"""PostgreSQL ownership-claim integration tests.

Requires DATABASE_URL. GitHub Actions supplies ordinary PostgreSQL 16.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from psycopg import AsyncConnection
from psycopg.rows import dict_row

from app.repositories.postgres import MIGRATION_0003_PATH, PostgresAssessmentRepository
from app.services.anonymous_assessment import hash_claim_token
from tests.integration.test_postgres_persistence import (
    DATABASE_URL,
    _persist,
    _run_with_repository,
)
from tests.unit.services.test_assessment_pipeline import _pdf, _run

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL is required")

CLAIMED_AT = datetime(2026, 9, 4, 13, 0, tzinfo=UTC)
RAW_CLAIM = "postgres-claim-token-never-persisted-raw"
USER_A = "11111111-1111-4111-8111-111111111111"
USER_B = "22222222-2222-4222-8222-222222222222"


def _digest() -> str:
    return hash_claim_token(RAW_CLAIM)


async def _seed(repository: PostgresAssessmentRepository, **extra):
    lines = [
        "Summary",
        "Seeking a junior software engineer role",
        "Skills",
        "Experience",
        "Projects",
        "Education",
        "Built a Flask API in Python to solve a workflow problem",
    ]
    file_bytes = _pdf(lines)
    outcome = _run("software_engineering", lines)
    result = await _persist(
        outcome,
        file_bytes,
        repository,
        claim_token_hash=_digest(),
        **extra,
    )
    assert result["state"] == "PERSISTED"
    return outcome


def test_migration_0003_adds_nullable_owner_user_id_index_without_fk() -> None:
    async def body(repository: PostgresAssessmentRepository) -> None:
        assert DATABASE_URL is not None
        assert MIGRATION_0003_PATH.is_file()
        sql = MIGRATION_0003_PATH.read_text(encoding="utf-8")
        ddl = "\n".join(
            line for line in sql.splitlines() if line.strip() and not line.lstrip().startswith("--")
        )
        assert "owner_user_id TEXT NULL" in sql
        assert "auth.users" not in ddl
        assert "FOREIGN KEY" not in ddl.upper()
        async with await AsyncConnection.connect(DATABASE_URL, row_factory=dict_row) as connection:
            column = await connection.execute(
                """
                SELECT data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'assessments'
                  AND column_name = 'owner_user_id'
                """
            )
            row = await column.fetchone()
            assert row is not None
            assert row["data_type"] == "text"
            assert row["is_nullable"] == "YES"
            index = await connection.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'assessments'
                  AND indexname = 'assessments_owner_user_id_idx'
                """
            )
            assert await index.fetchone() is not None
            fks = await connection.execute(
                """
                SELECT conname, pg_get_constraintdef(c.oid) AS definition
                FROM pg_constraint c
                WHERE c.conrelid = 'public.assessments'::regclass
                  AND c.contype = 'f'
                  AND pg_get_constraintdef(c.oid) ILIKE '%owner_user_id%'
                """
            )
            assert await fks.fetchall() == []

    _run_with_repository(body)


def test_valid_claim_sets_owner_clears_hash_and_preserves_preview() -> None:
    async def body(repository: PostgresAssessmentRepository) -> None:
        outcome = await _seed(repository)
        assessment_id = outcome["assessment_id"]
        before = await repository.get_assessment(assessment_id)
        before_run = await repository.get_latest_run(assessment_id)
        assert before is not None
        assert before_run is not None
        candidate_ref = before.candidate_ref
        latest_run_id = before.latest_run_id
        result = await repository.claim_assessment(
            assessment_id=assessment_id,
            authenticated_user_id=USER_A,
            presented_claim_token_hash=_digest(),
            claimed_at=CLAIMED_AT,
        )
        assert result.status == "claimed"
        assert result.access_state == "PREVIEW"
        assert result.claimed_at == CLAIMED_AT
        after = await repository.get_assessment(assessment_id)
        after_run = await repository.get_latest_run(assessment_id)
        assert after is not None
        assert after_run is not None
        assert after.owner_user_id == USER_A
        assert after.claim_token_hash is None
        assert after.claimed_at is not None
        assert after.candidate_ref == candidate_ref
        assert after.access_state == "PREVIEW"
        assert after.latest_run_id == latest_run_id
        assert after_run.assessment_result == before_run.assessment_result
        assert after_run.scoring_context == before_run.scoring_context
        assert after_run.source_records == before_run.source_records
        assert after_run.evidence_facts == before_run.evidence_facts
        assert DATABASE_URL is not None
        async with await AsyncConnection.connect(DATABASE_URL, row_factory=dict_row) as connection:
            stored = await connection.execute(
                """
                SELECT owner_user_id, claim_token_hash, access_state, candidate_ref
                FROM assessments
                WHERE assessment_id = %s
                """,
                (assessment_id,),
            )
            row = await stored.fetchone()
            assert row is not None
            assert row["owner_user_id"] == USER_A
            assert row["claim_token_hash"] is None
            assert row["access_state"] == "PREVIEW"
            assert row["candidate_ref"] == candidate_ref
            assert RAW_CLAIM not in str(row)

    _run_with_repository(body)


def test_same_user_retry_is_idempotent_without_hash() -> None:
    async def body(repository: PostgresAssessmentRepository) -> None:
        outcome = await _seed(repository)
        first = await repository.claim_assessment(
            assessment_id=outcome["assessment_id"],
            authenticated_user_id=USER_A,
            presented_claim_token_hash=_digest(),
            claimed_at=CLAIMED_AT,
        )
        second = await repository.claim_assessment(
            assessment_id=outcome["assessment_id"],
            authenticated_user_id=USER_A,
            presented_claim_token_hash="0" * 64,
            claimed_at=CLAIMED_AT,
        )
        assert first.status == "claimed"
        assert second.status == "idempotent"
        meta = await repository.get_assessment(outcome["assessment_id"])
        assert meta is not None
        assert meta.owner_user_id == USER_A
        assert meta.access_state == "PREVIEW"

    _run_with_repository(body)


def test_different_user_conflicts_and_wrong_token_does_not_mutate() -> None:
    async def body(repository: PostgresAssessmentRepository) -> None:
        outcome = await _seed(repository)
        assessment_id = outcome["assessment_id"]
        wrong = await repository.claim_assessment(
            assessment_id=assessment_id,
            authenticated_user_id=USER_A,
            presented_claim_token_hash="1" * 64,
            claimed_at=CLAIMED_AT,
        )
        assert wrong.status == "token_invalid"
        unchanged = await repository.get_assessment(assessment_id)
        assert unchanged is not None
        assert unchanged.owner_user_id is None
        assert unchanged.claim_token_hash == _digest()
        first = await repository.claim_assessment(
            assessment_id=assessment_id,
            authenticated_user_id=USER_A,
            presented_claim_token_hash=_digest(),
            claimed_at=CLAIMED_AT,
        )
        conflict = await repository.claim_assessment(
            assessment_id=assessment_id,
            authenticated_user_id=USER_B,
            presented_claim_token_hash=_digest(),
            claimed_at=CLAIMED_AT,
        )
        assert first.status == "claimed"
        assert conflict.status == "conflict"
        owned = await repository.get_assessment(assessment_id)
        assert owned is not None
        assert owned.owner_user_id == USER_A
        missing = await repository.claim_assessment(
            assessment_id="missing-assessment",
            authenticated_user_id=USER_A,
            presented_claim_token_hash=_digest(),
            claimed_at=CLAIMED_AT,
        )
        assert missing.status == "not_found"

    _run_with_repository(body)


def test_non_null_past_expires_at_rejects_claim() -> None:
    async def body(repository: PostgresAssessmentRepository) -> None:
        outcome = await _seed(repository, expires_at="2020-01-01T00:00:00Z")
        result = await repository.claim_assessment(
            assessment_id=outcome["assessment_id"],
            authenticated_user_id=USER_A,
            presented_claim_token_hash=_digest(),
            claimed_at=CLAIMED_AT,
        )
        assert result.status == "expired"
        meta = await repository.get_assessment(outcome["assessment_id"])
        assert meta is not None
        assert meta.owner_user_id is None
        assert meta.claim_token_hash == _digest()
        assert meta.access_state == "PREVIEW"

    _run_with_repository(body)


def test_concurrent_claims_cannot_create_two_owners() -> None:
    async def body(repository: PostgresAssessmentRepository) -> None:
        outcome = await _seed(repository)
        assessment_id = outcome["assessment_id"]
        results = await asyncio.gather(
            repository.claim_assessment(
                assessment_id=assessment_id,
                authenticated_user_id=USER_A,
                presented_claim_token_hash=_digest(),
                claimed_at=CLAIMED_AT,
            ),
            repository.claim_assessment(
                assessment_id=assessment_id,
                authenticated_user_id=USER_B,
                presented_claim_token_hash=_digest(),
                claimed_at=CLAIMED_AT,
            ),
        )
        statuses = {item.status for item in results}
        assert "claimed" in statuses
        assert "conflict" in statuses
        assert statuses == {"claimed", "conflict"}
        meta = await repository.get_assessment(assessment_id)
        assert meta is not None
        assert meta.owner_user_id in {USER_A, USER_B}
        assert meta.access_state == "PREVIEW"
        assert meta.claim_token_hash is None
        assert DATABASE_URL is not None
        async with await AsyncConnection.connect(DATABASE_URL, row_factory=dict_row) as connection:
            owners = await connection.execute(
                "SELECT owner_user_id FROM assessments WHERE assessment_id = %s",
                (assessment_id,),
            )
            row = await owners.fetchone()
            assert row is not None
            assert row["owner_user_id"] in {USER_A, USER_B}

    _run_with_repository(body)

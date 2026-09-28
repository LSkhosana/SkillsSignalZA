"""PostgreSQL owner-scoped summary listing tests.

Requires DATABASE_URL. GitHub Actions supplies ordinary PostgreSQL 16.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.repositories.postgres import PostgresAssessmentRepository
from tests.integration.test_postgres_claim import USER_A, USER_B, _digest, _seed
from tests.integration.test_postgres_persistence import DATABASE_URL, _run_with_repository

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL is required")

CLAIMED_AT = datetime(2026, 9, 4, 13, 0, tzinfo=UTC)
OLDER = "2026-09-01T10:00:00Z"
NEWER = "2026-09-05T10:00:00Z"


async def _seed_owned(
    repository: PostgresAssessmentRepository,
    *,
    assessment_id: str,
    run_id: str,
    owner_user_id: str,
    assessed_at: str,
) -> dict:
    """Persist one unclaimed row, then claim it so the one-time hash can be reused."""
    outcome = await _seed(
        repository,
        assessment_id=assessment_id,
        run_id=run_id,
        assessed_at=assessed_at,
    )
    claimed = await repository.claim_assessment(
        assessment_id=outcome["assessment_id"],
        authenticated_user_id=owner_user_id,
        presented_claim_token_hash=_digest(),
        claimed_at=CLAIMED_AT,
    )
    assert claimed.status == "claimed"
    return outcome


def test_list_owned_summaries_excludes_other_owners_and_orders_newest_first() -> None:
    async def body(repository: PostgresAssessmentRepository) -> None:
        await _seed_owned(
            repository,
            assessment_id="sum-old",
            run_id="run-old",
            owner_user_id=USER_A,
            assessed_at=OLDER,
        )
        await _seed_owned(
            repository,
            assessment_id="sum-new",
            run_id="run-new",
            owner_user_id=USER_A,
            assessed_at=NEWER,
        )
        await _seed_owned(
            repository,
            assessment_id="sum-b",
            run_id="run-b",
            owner_user_id=USER_B,
            assessed_at=NEWER,
        )
        await _seed(
            repository,
            assessment_id="sum-anon",
            run_id="run-anon",
            assessed_at=NEWER,
        )
        rows = await repository.list_owned_assessment_summaries(
            owner_user_id=USER_A,
            limit=50,
            offset=0,
        )
        ids = [row.assessment_id for row in rows]
        assert ids == ["sum-new", "sum-old"]
        assert all(row.access_state == "PREVIEW" for row in rows)
        assert all(row.unlocked_at is None for row in rows)
        assert all(row.final_score is not None for row in rows)
        assert all(row.band is not None for row in rows)
        other_rows = await repository.list_owned_assessment_summaries(
            owner_user_id=USER_B,
            limit=50,
            offset=0,
        )
        assert [row.assessment_id for row in other_rows] == ["sum-b"]
        empty = await repository.list_owned_assessment_summaries(
            owner_user_id="user-nobody",
            limit=50,
            offset=0,
        )
        assert empty == []

    _run_with_repository(body)

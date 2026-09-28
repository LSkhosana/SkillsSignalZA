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


def test_list_owned_summaries_excludes_other_owners_and_orders_newest_first() -> None:
    async def body(repository: PostgresAssessmentRepository) -> None:
        older = await _seed(
            repository,
            assessment_id="sum-old",
            run_id="run-old",
            assessed_at=OLDER,
        )
        newer = await _seed(
            repository,
            assessment_id="sum-new",
            run_id="run-new",
            assessed_at=NEWER,
        )
        other = await _seed(
            repository,
            assessment_id="sum-b",
            run_id="run-b",
            assessed_at=NEWER,
        )
        await _seed(
            repository,
            assessment_id="sum-anon",
            run_id="run-anon",
            assessed_at=NEWER,
        )
        claimed_old = await repository.claim_assessment(
            assessment_id=older["assessment_id"],
            authenticated_user_id=USER_A,
            presented_claim_token_hash=_digest(),
            claimed_at=CLAIMED_AT,
        )
        claimed_new = await repository.claim_assessment(
            assessment_id=newer["assessment_id"],
            authenticated_user_id=USER_A,
            presented_claim_token_hash=_digest(),
            claimed_at=CLAIMED_AT,
        )
        claimed_other = await repository.claim_assessment(
            assessment_id=other["assessment_id"],
            authenticated_user_id=USER_B,
            presented_claim_token_hash=_digest(),
            claimed_at=CLAIMED_AT,
        )
        assert claimed_old.status == "claimed"
        assert claimed_new.status == "claimed"
        assert claimed_other.status == "claimed"
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

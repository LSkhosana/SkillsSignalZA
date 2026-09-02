"""PostgreSQL persistence integration tests.

Requires DATABASE_URL. GitHub Actions supplies ordinary PostgreSQL 16.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from copy import deepcopy
from datetime import UTC
from typing import Any

import pytest
from psycopg import AsyncConnection, errors
from psycopg.rows import dict_row

from app.engine.schema_registry import draft_validator
from app.repositories.postgres import (
    MIGRATION_PATH,
    PostgresAssessmentRepository,
    apply_postgres_migration,
)
from app.repositories.supabase import opaque_storage_path
from app.services.assessment_persistence import persist_assessment_outcome_async
from app.services.assessment_pipeline import run_assessment_pipeline
from tests.unit.services.test_assessment_pipeline import (
    ASSESSED_AT,
    _accessible_retrieve,
    _failed_retrieve,
    _input,
    _pdf,
    _run,
)

DATABASE_URL = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL is required")
V1_TABLES = {
    "assessments",
    "assessment_runs",
    "assessment_documents",
    "assessment_sources",
    "assessment_evidence",
}


def _document(
    assessment_id: str, assessment_input: dict[str, Any], byte_size: int
) -> dict[str, Any]:
    cv = assessment_input["cv"]
    return {
        "document_id": cv["document_id"],
        "storage_path": opaque_storage_path(assessment_id, cv["document_id"], cv["media_type"]),
        "original_filename": cv["original_filename"],
        "media_type": cv["media_type"],
        "sha256": str(cv["sha256"]).lower(),
        "byte_size": byte_size,
    }


async def _connect() -> PostgresAssessmentRepository:
    assert DATABASE_URL is not None
    await apply_postgres_migration(DATABASE_URL)
    return await PostgresAssessmentRepository.connect(DATABASE_URL, min_size=0, max_size=5)


async def _truncate(dsn: str) -> None:
    async with await AsyncConnection.connect(dsn, autocommit=True) as connection:
        await connection.execute("TRUNCATE assessments CASCADE")


async def _persist(
    outcome: dict[str, Any],
    file_bytes: bytes,
    repository: PostgresAssessmentRepository,
    **extra: Any,
):
    assessment_input = extra.pop("assessment_input", None) or _input(outcome["track"], file_bytes)
    document = extra.pop("document_metadata", None) or _document(
        outcome["assessment_id"], assessment_input, len(file_bytes)
    )
    return await persist_assessment_outcome_async(
        assessment_input=assessment_input,
        pipeline_outcome=outcome,
        document_metadata=document,
        assessed_at=extra.pop("assessed_at", ASSESSED_AT),
        repository=repository,
        **extra,
    )


def _run_with_repository(test_body: Any) -> None:
    """Open, use, and close the async pool on one event loop."""

    async def runner() -> None:
        assert DATABASE_URL is not None
        repository = await _connect()
        try:
            await _truncate(DATABASE_URL)
            await test_body(repository)
        finally:
            try:
                await _truncate(DATABASE_URL)
            finally:
                await repository.close()

    asyncio.run(runner())


def test_migration_creates_five_tables_with_rls_and_no_public_policies() -> None:
    async def body(repository: PostgresAssessmentRepository) -> None:
        assert DATABASE_URL is not None
        async with await AsyncConnection.connect(DATABASE_URL, row_factory=dict_row) as connection:
            tables = await connection.execute(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                  AND tablename LIKE 'assessment%'
                """
            )
            names = {row["tablename"] for row in await tables.fetchall()}
            assert names == V1_TABLES
            rls = await connection.execute(
                """
                SELECT c.relname, c.relrowsecurity
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relname = ANY(%s)
                """,
                (list(V1_TABLES),),
            )
            flags = {row["relname"]: row["relrowsecurity"] for row in await rls.fetchall()}
            assert flags == {name: True for name in V1_TABLES}
            policies = await connection.execute(
                "SELECT tablename FROM pg_policies WHERE tablename = ANY(%s)",
                (list(V1_TABLES),),
            )
            assert await policies.fetchall() == []

    _run_with_repository(body)
    assert MIGRATION_PATH.name == "0001_assessment_persistence.sql"


def test_persist_completed_review_required_not_scorable_and_inaccessible_link() -> None:
    async def body(repository: PostgresAssessmentRepository) -> None:
        se_lines = [
            "Summary",
            "Seeking a junior software engineer role",
            "Skills",
            "Experience",
            "Projects",
            "Education",
            "Built a Flask API in Python to solve a workflow problem",
        ]
        se_bytes = _pdf(se_lines)
        se = _run("software_engineering", se_lines)
        se_result = await _persist(se, se_bytes, repository)
        assert se_result["state"] == "PERSISTED"
        loaded = await repository.get_latest_run(se["assessment_id"])
        assert loaded is not None
        assert loaded.state == "COMPLETED"
        assert loaded.assessment_result == se["assessment_result"]
        assert loaded.scoring_context == se["scoring_context"]
        draft_validator("assessment_result.schema.json").validate(loaded.assessment_result)
        draft_validator("scoring_context.schema.json").validate(loaded.scoring_context)
        meta = await repository.get_assessment(se["assessment_id"])
        assert meta is not None
        assert meta.latest_run_id == se["run_id"]
        assert meta.access_state == "PREVIEW"
        assert loaded.document is not None
        assert loaded.document.document_id == "src-cv"

        da_lines = [
            "Summary",
            "Seeking a junior data analyst role",
            "Skills",
            "Experience",
            "Education",
            "Used SQL to analyse the sales dataset",
        ]
        da_bytes = _pdf(da_lines)
        da = _run("data_analytics", da_lines)
        da["assessment_id"] = "assessment-da"
        da["run_id"] = "run-da"
        da_input = _input("data_analytics", da_bytes)
        da_result = await _persist(da, da_bytes, repository, assessment_input=da_input)
        assert da_result["state"] == "PERSISTED"
        assert da_result["assessment_id"] == "assessment-da"

        review = _run(
            "software_engineering",
            ["Junior Software Engineer"],
            links=[
                {
                    "link_id": "link-1",
                    "submitted_url": "https://example.com/project",
                    "declared_type": "project",
                }
            ],
            retrieve_link=_accessible_retrieve,
        )
        review["assessment_id"] = "assessment-review"
        review["run_id"] = "run-review"
        review_bytes = _pdf(["Junior Software Engineer"])
        review_input = _input(
            "software_engineering",
            review_bytes,
            links=[
                {
                    "link_id": "link-1",
                    "submitted_url": "https://example.com/project",
                    "declared_type": "project",
                }
            ],
        )
        review_result = await _persist(
            review, review_bytes, repository, assessment_input=review_input
        )
        assert review_result["state"] == "PERSISTED"
        review_run = await repository.get_run("run-review")
        assert review_run is not None
        assert review_run.assessment_result is None
        assert review_run.scoring_context is not None
        assert review_run.review_flags

        unreadable_bytes = b"not-a-pdf"
        payload = _input("software_engineering", unreadable_bytes)
        payload["cv"]["document_id"] = "src-cv"
        unreadable = run_assessment_pipeline(
            assessment_input=payload,
            cv_file_bytes=unreadable_bytes,
            assessment_id="assessment-unreadable",
            run_id="run-unreadable",
            assessed_at=ASSESSED_AT,
            retrieve_link=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("network")
            ),
        )
        assert unreadable["state"] == "NOT_SCORABLE"
        unreadable_result = await _persist(
            unreadable, unreadable_bytes, repository, assessment_input=payload
        )
        assert unreadable_result["state"] == "PERSISTED"

        inaccessible = _run(
            "software_engineering",
            ["Junior Software Engineer"],
            links=[
                {
                    "link_id": "link-1",
                    "submitted_url": "https://example.com/private",
                    "declared_type": "project",
                }
            ],
            retrieve_link=_failed_retrieve,
        )
        inaccessible["assessment_id"] = "assessment-link"
        inaccessible["run_id"] = "run-link"
        link_bytes = _pdf(["Junior Software Engineer"])
        link_input = _input(
            "software_engineering",
            link_bytes,
            links=[
                {
                    "link_id": "link-1",
                    "submitted_url": "https://example.com/private",
                    "declared_type": "project",
                }
            ],
        )
        link_result = await _persist(
            inaccessible, link_bytes, repository, assessment_input=link_input
        )
        assert link_result["state"] == "PERSISTED"
        link_run = await repository.get_run("run-link")
        assert link_run is not None
        assert any(
            source["access_status"] != "accessible" or source["source_type"] != "cv"
            for source in link_run.source_records
        ) or any(source["source_id"] != "src-cv" for source in link_run.source_records)
        assert [fact["evidence_id"] for fact in link_run.evidence_facts] == sorted(
            fact["evidence_id"] for fact in link_run.evidence_facts
        )
        assert [source["source_id"] for source in link_run.source_records] == sorted(
            source["source_id"] for source in link_run.source_records
        )

    _run_with_repository(body)


def test_idempotency_conflict_immutability_and_cascade() -> None:
    async def body(repository: PostgresAssessmentRepository) -> None:
        lines = ["Junior Software Engineer"]
        file_bytes = _pdf(lines)
        outcome = _run("software_engineering", lines)
        first = await _persist(outcome, file_bytes, repository)
        assert first["state"] == "PERSISTED"
        second = await _persist(outcome, file_bytes, repository)
        assert second["state"] == "PERSISTENCE_NOOP"
        changed = deepcopy(outcome)
        if changed["assessment_result"] is not None:
            changed["assessment_result"] = dict(changed["assessment_result"])
            changed["assessment_result"]["final_score"] = 99
        conflict = await _persist(changed, file_bytes, repository)
        assert conflict["state"] == "PERSISTENCE_CONFLICT"
        original = await repository.get_run(outcome["run_id"])
        assert original is not None
        assert original.assessment_result == outcome["assessment_result"]

        da_on_se = deepcopy(outcome)
        da_on_se["track"] = "data_analytics"
        da_conflict = await persist_assessment_outcome_async(
            assessment_input=_input("data_analytics", file_bytes),
            pipeline_outcome=da_on_se,
            document_metadata=_document(
                outcome["assessment_id"], _input("data_analytics", file_bytes), len(file_bytes)
            ),
            assessed_at=ASSESSED_AT,
            repository=repository,
        )
        assert da_conflict["error_code"] in {"IDENTITY_MISMATCH", "PERSISTENCE_CONFLICT"}

        assert DATABASE_URL is not None
        async with await AsyncConnection.connect(DATABASE_URL, row_factory=dict_row) as connection:
            with pytest.raises(errors.RestrictViolation):
                await connection.execute("UPDATE assessment_runs SET state = state")
            await connection.rollback()
            with pytest.raises(errors.RestrictViolation):
                await connection.execute("UPDATE assessment_sources SET locator = locator")
            await connection.rollback()
            with pytest.raises(errors.RestrictViolation):
                await connection.execute("UPDATE assessment_evidence SET subject = subject")
            await connection.rollback()
            await connection.execute(
                "UPDATE assessments SET access_state = 'UNLOCKED' WHERE assessment_id = %s",
                (outcome["assessment_id"],),
            )
            await connection.commit()
            await connection.execute(
                "DELETE FROM assessments WHERE assessment_id = %s",
                (outcome["assessment_id"],),
            )
            await connection.commit()
            remaining = await connection.execute("SELECT count(*) AS n FROM assessment_runs")
            row = await remaining.fetchone()
            assert row is not None
            count = row["n"] if isinstance(row, dict) else row[0]
            assert int(count) == 0

    _run_with_repository(body)


def test_transaction_rollback_and_duplicate_children() -> None:
    async def body(repository: PostgresAssessmentRepository) -> None:
        lines = ["Junior Software Engineer"]
        file_bytes = _pdf(lines)
        outcome = _run("software_engineering", lines)
        broken = deepcopy(outcome)
        broken["assessment_id"] = "assessment-rollback"
        broken["run_id"] = "run-rollback"
        broken["source_records"] = list(broken["source_records"]) + [
            {
                **broken["source_records"][0],
                "source_type": "not-a-source",
                "source_id": "src-bad",
            }
        ]
        broken_input = _input(outcome["track"], file_bytes)
        result = await _persist(broken, file_bytes, repository, assessment_input=broken_input)
        assert result["state"] == "PERSISTENCE_FAILED"
        assert await repository.get_assessment("assessment-rollback") is None
        assert await repository.get_run("run-rollback") is None

        dup = deepcopy(outcome)
        dup["assessment_id"] = "assessment-dup"
        dup["run_id"] = "run-dup"
        dup["source_records"] = list(dup["source_records"]) + [deepcopy(dup["source_records"][0])]
        dup_result = await _persist(
            dup, file_bytes, repository, assessment_input=_input(outcome["track"], file_bytes)
        )
        assert dup_result["state"] == "PERSISTENCE_FAILED"
        assert await repository.get_run("run-dup") is None

        facts = deepcopy(outcome)
        facts["assessment_id"] = "assessment-facts"
        facts["run_id"] = "run-facts"
        if facts["evidence_facts"]:
            extra = deepcopy(facts["evidence_facts"][0])
            extra["source_id"] = "missing-source"
            extra["evidence_id"] = "ev-9999"
            facts["evidence_facts"] = list(facts["evidence_facts"]) + [extra]
            facts_result = await _persist(
                facts,
                file_bytes,
                repository,
                assessment_input=_input(outcome["track"], file_bytes),
            )
            assert facts_result["state"] == "PERSISTENCE_FAILED"
            assert await repository.get_run("run-facts") is None

    _run_with_repository(body)


def test_claim_token_and_expires_at_foundations() -> None:
    async def body(repository: PostgresAssessmentRepository) -> None:
        lines = ["Junior Software Engineer"]
        file_bytes = _pdf(lines)
        outcome = _run("software_engineering", lines)
        digest = hashlib.sha256(b"high-entropy-preview-token").hexdigest()
        result = await _persist(
            outcome,
            file_bytes,
            repository,
            claim_token_hash=digest,
            expires_at="2026-10-02T08:00:00Z",
        )
        assert result["state"] == "PERSISTED"
        meta = await repository.get_assessment(outcome["assessment_id"])
        assert meta is not None
        assert meta.claim_token_hash == digest
        assert meta.claimed_at is None
        assert meta.expires_at is not None
        assert meta.expires_at.tzinfo is not None or meta.expires_at.replace(tzinfo=UTC)

        assert DATABASE_URL is not None
        async with await AsyncConnection.connect(DATABASE_URL, row_factory=dict_row) as connection:
            rows = await connection.execute(
                "SELECT claim_token_hash FROM assessments WHERE assessment_id = %s",
                (outcome["assessment_id"],),
            )
            stored = await rows.fetchone()
            assert stored is not None
            assert "high-entropy-preview-token" not in str(stored)

    _run_with_repository(body)

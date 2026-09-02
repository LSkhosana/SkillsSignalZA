"""Fake-pool unit tests for the PostgreSQL adapter."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from app.repositories.postgres import PostgresAssessmentRepository
from app.repositories.records import DocumentMetadata, PersistenceBundle

EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


class _CM:
    def __init__(self, value: Any) -> None:
        self.value = value

    async def __aenter__(self) -> Any:
        return self.value

    async def __aexit__(self, *_args: object) -> bool:
        return False


class ScriptedCursor:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.executemany_calls = 0
        self.fetchone_queue: list[dict[str, Any] | None] = []
        self.fetchall_queue: list[list[dict[str, Any]]] = []
        self.fail_on_evidence = False

    async def execute(self, sql: str, _params: object = None) -> None:
        compact = " ".join(sql.split())
        self.statements.append(compact)

    async def executemany(self, sql: str, rows: list[tuple[object, ...]]) -> None:
        self.statements.append(" ".join(sql.split()))
        self.executemany_calls += 1
        if self.fail_on_evidence and "assessment_evidence" in sql:
            raise RuntimeError("forced evidence insert failure")

    async def fetchone(self) -> dict[str, Any] | None:
        if self.fetchone_queue:
            return self.fetchone_queue.pop(0)
        return None

    async def fetchall(self) -> list[dict[str, Any]]:
        if self.fetchall_queue:
            return self.fetchall_queue.pop(0)
        return []


class FakeConnection:
    def __init__(self, cursor: ScriptedCursor) -> None:
        self._cursor = cursor

    def transaction(self) -> _CM:
        return _CM(self)

    def cursor(self) -> _CM:
        return _CM(self._cursor)


class FakePool:
    def __init__(self, cursor: ScriptedCursor) -> None:
        self._cursor = cursor

    def connection(self) -> _CM:
        return _CM(FakeConnection(self._cursor))

    async def close(self) -> None:
        return None


def _bundle() -> PersistenceBundle:
    assessed = datetime(2026, 9, 2, 8, 0, tzinfo=UTC)
    return PersistenceBundle(
        assessment_id="assessment-1",
        run_id="run-1",
        candidate_ref="opaque-candidate",
        track="software_engineering",
        assessed_at=assessed,
        claim_token_hash=None,
        expires_at=None,
        document=DocumentMetadata(
            document_id="src-cv",
            storage_path="assessments/assessment-1/src-cv.pdf",
            original_filename="cv.pdf",
            media_type="application/pdf",
            sha256=EMPTY_SHA256,
            byte_size=12,
        ),
        assessment_input={"track": "software_engineering"},
        pipeline_outcome={
            "state": "NOT_SCORABLE",
            "error_code": "CV_UNREADABLE",
            "pipeline_version": "assessment.pipeline.v1",
            "contract_version": "1.2.0",
            "rubric_version": "V2",
            "track": "software_engineering",
            "scoring_context": None,
            "assessment_result": None,
            "review_flags": [],
            "stages": ["validate_input"],
            "source_records": [
                {
                    "source_id": "src-cv",
                    "source_type": "cv",
                    "submitted_by_candidate": True,
                    "access_status": "accessible",
                    "ownership_status": "attributed",
                    "retrieved_at": "2026-09-02T08:00:00Z",
                    "content_hash": EMPTY_SHA256,
                    "extractor_version": "extract.cv.v1",
                    "locator": "page 1",
                    "notes": "cv",
                }
            ],
            "evidence_facts": [],
        },
    )


def test_persist_bundle_uses_one_transaction_and_bulk_inserts() -> None:
    cursor = ScriptedCursor()
    repo = PostgresAssessmentRepository(FakePool(cursor))  # type: ignore[arg-type]
    result = asyncio.run(repo.persist_bundle(_bundle()))
    assert result.status == "inserted"
    assert cursor.executemany_calls == 1
    joined = "\n".join(cursor.statements)
    assert "INSERT INTO assessments" in joined
    assert "INSERT INTO assessment_runs" in joined
    assert "INSERT INTO assessment_sources" in joined
    assert joined.count("COMMIT") == 0


def test_forced_evidence_failure_does_not_commit_in_adapter() -> None:
    cursor = ScriptedCursor()
    cursor.fail_on_evidence = True
    bundle = _bundle()
    bundle.pipeline_outcome["evidence_facts"] = [
        {
            "evidence_id": "ev-0001",
            "source_id": "src-cv",
            "locator": "page 1",
            "fact_type": "skill_name",
            "subject": "python",
            "explicit_text": "Python",
            "evidence_level": "named_only",
            "attribution_status": "attributed",
            "rule_id": "normalize.v1.skill.python",
            "review_status": "accepted",
        }
    ]
    repo = PostgresAssessmentRepository(FakePool(cursor))  # type: ignore[arg-type]
    try:
        asyncio.run(repo.persist_bundle(bundle))
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected forced evidence failure")
    assert "COMMIT" not in "\n".join(cursor.statements)


def test_get_assessment_and_latest_run_use_mapped_rows() -> None:
    assessed = datetime(2026, 9, 2, 8, 0, tzinfo=UTC)
    cursor = ScriptedCursor()
    cursor.fetchone_queue = [
        {
            "assessment_id": "assessment-1",
            "candidate_ref": "opaque-candidate",
            "track": "software_engineering",
            "access_state": "PREVIEW",
            "claim_token_hash": None,
            "claimed_at": None,
            "latest_run_id": "run-1",
            "expires_at": None,
            "created_at": assessed,
            "updated_at": assessed,
        },
        {"latest_run_id": None},
    ]
    repo = PostgresAssessmentRepository(FakePool(cursor))  # type: ignore[arg-type]
    record = asyncio.run(repo.get_assessment("assessment-1"))
    assert record is not None
    assert record.assessment_id == "assessment-1"
    assert record.access_state == "PREVIEW"
    missing = asyncio.run(repo.get_latest_run("assessment-1"))
    assert missing is None
    empty = ScriptedCursor()
    empty_repo = PostgresAssessmentRepository(FakePool(empty))  # type: ignore[arg-type]
    assert asyncio.run(empty_repo.get_assessment("missing")) is None
    assert asyncio.run(empty_repo.get_run("missing")) is None


def test_get_run_reconstructs_sources_and_evidence() -> None:
    assessed = datetime(2026, 9, 2, 8, 0, tzinfo=UTC)
    cursor = ScriptedCursor()
    cursor.fetchone_queue = [
        {
            "run_id": "run-1",
            "assessment_id": "assessment-1",
            "state": "NOT_SCORABLE",
            "error_code": "CV_UNREADABLE",
            "pipeline_version": "assessment.pipeline.v1",
            "contract_version": "1.2.0",
            "rubric_version": "V2",
            "track": "software_engineering",
            "assessment_input": {"track": "software_engineering"},
            "scoring_context": None,
            "assessment_result": None,
            "review_flags": [],
            "stages": ["validate_input"],
            "assessed_at": assessed,
            "created_at": assessed,
        },
        {
            "document_id": "src-cv",
            "storage_path": "assessments/assessment-1/src-cv.pdf",
            "original_filename": "cv.pdf",
            "media_type": "application/pdf",
            "sha256": EMPTY_SHA256,
            "byte_size": 12,
        },
    ]
    cursor.fetchall_queue = [
        [
            {
                "source_id": "src-cv",
                "source_type": "cv",
                "submitted_by_candidate": True,
                "access_status": "accessible",
                "ownership_status": "attributed",
                "retrieved_at": assessed,
                "content_hash": EMPTY_SHA256,
                "extractor_version": "extract.cv.v1",
                "locator": "page 1",
                "notes": "cv",
            }
        ],
        [],
    ]
    repo = PostgresAssessmentRepository(FakePool(cursor))  # type: ignore[arg-type]
    loaded = asyncio.run(repo.get_run("run-1"))
    assert loaded is not None
    assert loaded.source_records[0]["source_id"] == "src-cv"
    assert loaded.document is not None
    assert loaded.evidence_facts == []


def test_run_owned_by_another_assessment_is_conflict() -> None:
    cursor = ScriptedCursor()
    cursor.fetchone_queue = [
        {
            "assessment_id": "assessment-1",
            "candidate_ref": "opaque-candidate",
            "track": "software_engineering",
            "latest_run_id": "run-1",
        },
        {
            "run_id": "run-1",
            "assessment_id": "other-assessment",
            "state": "NOT_SCORABLE",
            "error_code": "CV_UNREADABLE",
            "pipeline_version": "assessment.pipeline.v1",
            "contract_version": "1.2.0",
            "rubric_version": "V2",
            "track": "software_engineering",
            "assessment_input": {},
            "scoring_context": None,
            "assessment_result": None,
            "review_flags": [],
            "stages": [],
        },
    ]
    repo = PostgresAssessmentRepository(FakePool(cursor))  # type: ignore[arg-type]
    result = asyncio.run(repo.persist_bundle(_bundle()))
    assert result.status == "conflict"

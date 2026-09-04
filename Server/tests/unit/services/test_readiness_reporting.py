"""Package M persisted-assessment reporting service tests. No database or network."""

from __future__ import annotations

import ast
import asyncio
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.engine.reporting.outcomes import (
    ERROR_ASSESSMENT_NOT_COMPLETED,
    ERROR_ASSESSMENT_NOT_FOUND,
    ERROR_ASSESSMENT_RESULT_MISSING,
    ERROR_REPORT_BUILD_FAILED,
    ERROR_REPORT_RULESET_INVALID,
    REPORTING_VERSION,
)
from app.engine.schema_registry import draft_validator
from app.repositories.records import AssessmentRecord, AssessmentRunRecord, PersistWriteResult
from app.services.readiness_reporting import get_readiness_report, get_readiness_report_async
from tests.unit.engine.test_readiness_report import _golden

SERVICE_PATH = Path(__file__).resolve().parents[3] / "app" / "services" / "readiness_reporting.py"
ASSESSED_AT = datetime(2026, 9, 2, 8, 0, tzinfo=UTC)


class MemoryRepository:
    def __init__(
        self,
        assessment: AssessmentRecord | None = None,
        run: AssessmentRunRecord | None = None,
    ) -> None:
        self.assessment = assessment
        self.run = run
        self.writes = 0

    async def persist_bundle(self, _bundle: object) -> PersistWriteResult:
        self.writes += 1
        return PersistWriteResult("inserted", "assessment-1", "run-1", latest_run_id="run-1")

    async def get_assessment(self, assessment_id: str) -> AssessmentRecord | None:
        if self.assessment is None or self.assessment.assessment_id != assessment_id:
            return None
        return self.assessment

    async def get_run(self, _run_id: str) -> AssessmentRunRecord | None:
        return self.run

    async def get_latest_run(self, assessment_id: str) -> AssessmentRunRecord | None:
        if self.run is None or self.run.assessment_id != assessment_id:
            return None
        return self.run


def _assessment(assessment_id: str, track: str, run_id: str) -> AssessmentRecord:
    return AssessmentRecord(
        assessment_id=assessment_id,
        candidate_ref="opaque-candidate",
        track=track,
        access_state="PREVIEW",
        claim_token_hash=None,
        claimed_at=None,
        latest_run_id=run_id,
        expires_at=None,
        created_at=ASSESSED_AT,
        updated_at=ASSESSED_AT,
    )


def _run_record(
    result: dict[str, Any] | None,
    *,
    assessment_id: str,
    run_id: str,
    track: str,
    state: str = "COMPLETED",
    error_code: str | None = None,
) -> AssessmentRunRecord:
    return AssessmentRunRecord(
        run_id=run_id,
        assessment_id=assessment_id,
        state=state,
        error_code=error_code,
        pipeline_version="assessment.pipeline.v1",
        contract_version="1.2.0",
        rubric_version="V2",
        track=track,
        assessment_input={"track": track},
        scoring_context=None,
        assessment_result=result,
        review_flags=[],
        stages=["score"],
        assessed_at=ASSESSED_AT,
        created_at=ASSESSED_AT,
        source_records=[],
        evidence_facts=[],
        document=None,
    )


def test_persisted_completed_assessment_returns_preview_and_full_report() -> None:
    result = _golden("c01_se_full_score.json")
    repository = MemoryRepository(
        _assessment(result["assessment_id"], result["track"], result["run_id"]),
        _run_record(
            result,
            assessment_id=result["assessment_id"],
            run_id=result["run_id"],
            track=result["track"],
        ),
    )
    outcome = get_readiness_report(assessment_id=result["assessment_id"], repository=repository)
    draft_validator("readiness_reporting_outcome.schema.json").validate(outcome)
    assert outcome["state"] == "COMPLETED"
    assert outcome["error_code"] is None
    assert outcome["reporting_version"] == REPORTING_VERSION
    draft_validator("readiness_report.schema.json").validate(outcome["report"])
    draft_validator("readiness_preview.schema.json").validate(outcome["preview"])
    assert repository.writes == 0
    assert repository.assessment is not None
    assert repository.assessment.access_state == "PREVIEW"


def test_missing_and_non_completed_runs_return_safe_failures() -> None:
    missing = get_readiness_report(assessment_id="missing", repository=MemoryRepository())
    assert missing["state"] == "FAILED"
    assert missing["error_code"] == ERROR_ASSESSMENT_NOT_FOUND
    assert missing["preview"] is None
    assert missing["report"] is None
    result = _golden("c01_se_full_score.json")
    review = get_readiness_report(
        assessment_id=result["assessment_id"],
        repository=MemoryRepository(
            _assessment(result["assessment_id"], result["track"], result["run_id"]),
            _run_record(
                None,
                assessment_id=result["assessment_id"],
                run_id=result["run_id"],
                track=result["track"],
                state="REVIEW_REQUIRED",
                error_code="REVIEW_REQUIRED",
            ),
        ),
    )
    assert review["error_code"] == ERROR_ASSESSMENT_NOT_COMPLETED
    assert review["report"] is None
    not_scorable = get_readiness_report(
        assessment_id=result["assessment_id"],
        repository=MemoryRepository(
            _assessment(result["assessment_id"], result["track"], result["run_id"]),
            _run_record(
                None,
                assessment_id=result["assessment_id"],
                run_id=result["run_id"],
                track=result["track"],
                state="NOT_SCORABLE",
                error_code="CV_UNREADABLE",
            ),
        ),
    )
    assert not_scorable["error_code"] == ERROR_ASSESSMENT_NOT_COMPLETED
    missing_result = get_readiness_report(
        assessment_id=result["assessment_id"],
        repository=MemoryRepository(
            _assessment(result["assessment_id"], result["track"], result["run_id"]),
            _run_record(
                None,
                assessment_id=result["assessment_id"],
                run_id=result["run_id"],
                track=result["track"],
                state="COMPLETED",
            ),
        ),
    )
    assert missing_result["error_code"] == ERROR_ASSESSMENT_RESULT_MISSING
    blob = str(missing) + str(review) + str(not_scorable) + str(missing_result)
    assert "postgresql://" not in blob
    assert "traceback" not in blob.lower()
    assert "C:\\" not in blob


def test_service_never_calls_pipeline_or_scorer_and_does_not_write() -> None:
    source = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))
    called: set[str] = set()
    for node in ast.walk(source):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called.add(node.func.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            called.add(node.func.attr)
    assert "score_assessment" not in called
    assert "run_assessment_pipeline" not in called
    assert "score_frozen_assessment" not in called
    assert "persist_bundle" not in called
    text = SERVICE_PATH.read_text(encoding="utf-8")
    assert "score_assessment" not in text
    assert "run_assessment_pipeline" not in text
    result = _golden("c02_da_full_score.json")
    repository = MemoryRepository(
        _assessment(result["assessment_id"], result["track"], result["run_id"]),
        _run_record(
            result,
            assessment_id=result["assessment_id"],
            run_id=result["run_id"],
            track=result["track"],
        ),
    )
    outcome = asyncio.run(
        get_readiness_report_async(assessment_id=result["assessment_id"], repository=repository)
    )
    assert outcome["state"] == "COMPLETED"
    assert repository.writes == 0
    assert repository.assessment is not None
    assert repository.assessment.access_state == "PREVIEW"


class _BoomRepository:
    async def persist_bundle(self, _bundle: object) -> PersistWriteResult:
        raise AssertionError("reporting must not write")

    async def get_assessment(self, _assessment_id: str) -> None:
        raise RuntimeError("repository unavailable")

    async def get_run(self, _run_id: str) -> None:
        raise RuntimeError("repository unavailable")

    async def get_latest_run(self, _assessment_id: str) -> None:
        raise RuntimeError("repository unavailable")


def test_service_covers_empty_id_missing_run_invalid_result_and_exceptions() -> None:
    empty = get_readiness_report(assessment_id="  ", repository=MemoryRepository())
    assert empty["error_code"] == ERROR_ASSESSMENT_NOT_FOUND
    result = _golden("c01_se_full_score.json")
    no_run = get_readiness_report(
        assessment_id=result["assessment_id"],
        repository=MemoryRepository(
            _assessment(result["assessment_id"], result["track"], result["run_id"]),
            None,
        ),
    )
    assert no_run["error_code"] == ERROR_ASSESSMENT_NOT_COMPLETED
    invalid = deepcopy(result)
    invalid.pop("criterion_results")
    invalid_result = get_readiness_report(
        assessment_id=result["assessment_id"],
        repository=MemoryRepository(
            _assessment(result["assessment_id"], result["track"], result["run_id"]),
            _run_record(
                invalid,
                assessment_id=result["assessment_id"],
                run_id=result["run_id"],
                track=result["track"],
            ),
        ),
    )
    assert invalid_result["error_code"] == ERROR_REPORT_RULESET_INVALID
    boom = get_readiness_report(assessment_id=result["assessment_id"], repository=_BoomRepository())
    assert boom["error_code"] == ERROR_REPORT_BUILD_FAILED
    assert boom["preview"] is None
    assert "repository unavailable" not in str(boom)
    version = get_readiness_report(
        assessment_id=result["assessment_id"],
        repository=MemoryRepository(
            _assessment(result["assessment_id"], result["track"], result["run_id"]),
            _run_record(
                result,
                assessment_id=result["assessment_id"],
                run_id=result["run_id"],
                track=result["track"],
            ),
        ),
        report_version="9.9.9",
    )
    assert version["error_code"] == "REPORT_VERSION_NOT_FOUND"
    assert version["report"] is None

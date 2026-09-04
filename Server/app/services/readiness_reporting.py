"""Package M reporting service downstream of Package L persistence.

Loads the latest persisted run and assembles preview/full report payloads
on demand. It never calls Package K, never scores, and never writes.
"""

from __future__ import annotations

import asyncio
from typing import Any

from jsonschema.exceptions import ValidationError

from app.engine.reporting import build_readiness_preview, build_readiness_report
from app.engine.reporting.outcomes import (
    ERROR_ASSESSMENT_NOT_COMPLETED,
    ERROR_ASSESSMENT_NOT_FOUND,
    ERROR_ASSESSMENT_RESULT_MISSING,
    ERROR_REPORT_BUILD_FAILED,
    ERROR_REPORT_RULESET_INVALID,
    ERROR_REPORT_VERSION_NOT_FOUND,
    REPORT_VERSION,
    REPORTING_VERSION,
    is_report_payload,
)
from app.engine.schema_registry import draft_validator
from app.repositories.interfaces import AssessmentRepository

_BUILDER_ERRORS = {
    ERROR_REPORT_VERSION_NOT_FOUND,
    ERROR_REPORT_RULESET_INVALID,
    ERROR_REPORT_BUILD_FAILED,
}


def get_readiness_report(
    *,
    assessment_id: str,
    repository: AssessmentRepository,
    report_version: str = REPORT_VERSION,
) -> dict[str, Any]:
    """Synchronously load one persisted assessment and assemble report payloads."""
    return asyncio.run(
        get_readiness_report_async(
            assessment_id=assessment_id,
            repository=repository,
            report_version=report_version,
        )
    )


async def get_readiness_report_async(
    *,
    assessment_id: str,
    repository: AssessmentRepository,
    report_version: str = REPORT_VERSION,
) -> dict[str, Any]:
    """Load the latest persisted run and return preview plus full report."""
    try:
        return await _load(assessment_id, repository, report_version)
    except Exception:
        return _outcome(
            state="FAILED",
            error_code=ERROR_REPORT_BUILD_FAILED,
            assessment_id=assessment_id if isinstance(assessment_id, str) else "",
            run_id="",
        )


async def _load(
    assessment_id: str,
    repository: AssessmentRepository,
    report_version: str,
) -> dict[str, Any]:
    if not isinstance(assessment_id, str) or not assessment_id.strip():
        return _outcome(
            state="FAILED",
            error_code=ERROR_ASSESSMENT_NOT_FOUND,
            assessment_id="",
            run_id="",
        )
    record = await repository.get_assessment(assessment_id)
    if record is None:
        return _outcome(
            state="FAILED",
            error_code=ERROR_ASSESSMENT_NOT_FOUND,
            assessment_id=assessment_id,
            run_id="",
        )
    run = await repository.get_latest_run(assessment_id)
    if run is None:
        return _outcome(
            state="FAILED",
            error_code=ERROR_ASSESSMENT_NOT_COMPLETED,
            assessment_id=assessment_id,
            run_id="",
        )
    if run.state != "COMPLETED":
        return _outcome(
            state="FAILED",
            error_code=ERROR_ASSESSMENT_NOT_COMPLETED,
            assessment_id=assessment_id,
            run_id=run.run_id,
        )
    if run.assessment_result is None:
        return _outcome(
            state="FAILED",
            error_code=ERROR_ASSESSMENT_RESULT_MISSING,
            assessment_id=assessment_id,
            run_id=run.run_id,
        )
    try:
        draft_validator("assessment_result.schema.json").validate(run.assessment_result)
    except ValidationError:
        return _outcome(
            state="FAILED",
            error_code=ERROR_REPORT_RULESET_INVALID,
            assessment_id=assessment_id,
            run_id=run.run_id,
        )
    report = build_readiness_report(run.assessment_result, report_version=report_version)
    if not is_report_payload(report):
        error_code = str(report.get("error_code") or ERROR_REPORT_BUILD_FAILED)
        if error_code not in _BUILDER_ERRORS:
            error_code = ERROR_REPORT_BUILD_FAILED
        return _outcome(
            state="FAILED",
            error_code=error_code,
            assessment_id=assessment_id,
            run_id=run.run_id,
        )
    preview = build_readiness_preview(report)
    if preview.get("schema_version") != "readiness.preview.v1":
        return _outcome(
            state="FAILED",
            error_code=ERROR_REPORT_BUILD_FAILED,
            assessment_id=assessment_id,
            run_id=run.run_id,
        )
    return _outcome(
        state="COMPLETED",
        error_code=None,
        assessment_id=assessment_id,
        run_id=run.run_id,
        preview=preview,
        report=report,
    )


def _outcome(
    *,
    state: str,
    error_code: str | None,
    assessment_id: str,
    run_id: str,
    preview: dict[str, Any] | None = None,
    report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    outcome = {
        "state": state,
        "error_code": error_code,
        "reporting_version": REPORTING_VERSION,
        "assessment_id": assessment_id,
        "run_id": run_id,
        "preview": preview,
        "report": report,
    }
    draft_validator("readiness_reporting_outcome.schema.json").validate(outcome)
    return outcome

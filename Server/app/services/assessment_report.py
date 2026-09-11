"""Package Q: deliver the unlocked Readiness Report to the verified owner.

Authorization and entitlement only. This service does not score, run Package K,
call Paystack, persist a report, or mutate access_state.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from jsonschema.exceptions import ValidationError

from app.engine.reporting.outcomes import (
    ERROR_ASSESSMENT_NOT_COMPLETED as REPORTING_NOT_COMPLETED,
)
from app.engine.reporting.outcomes import (
    ERROR_ASSESSMENT_NOT_FOUND as REPORTING_NOT_FOUND,
)
from app.engine.reporting.outcomes import (
    is_report_payload,
)
from app.engine.schema_registry import draft_validator
from app.repositories.interfaces import AssessmentRepository
from app.services.readiness_reporting import get_readiness_report_async

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "assessment.report.v1"
SCHEMA_FILENAME = "assessment_report_error.schema.json"

ERROR_AUTH_REQUIRED = "AUTH_REQUIRED"
ERROR_AUTH_INVALID = "AUTH_INVALID"
ERROR_AUTH_SERVICE_UNAVAILABLE = "AUTH_SERVICE_UNAVAILABLE"
ERROR_ASSESSMENT_NOT_FOUND = "ASSESSMENT_NOT_FOUND"
ERROR_ASSESSMENT_NOT_OWNED = "ASSESSMENT_NOT_OWNED"
ERROR_REPORT_LOCKED = "REPORT_LOCKED"
ERROR_ASSESSMENT_NOT_COMPLETED = "ASSESSMENT_NOT_COMPLETED"
ERROR_REPORT_SERVICE_UNAVAILABLE = "REPORT_SERVICE_UNAVAILABLE"
ERROR_REPORT_BUILD_FAILED = "REPORT_BUILD_FAILED"

REPORT_HTTP_STATUS = {
    ERROR_AUTH_REQUIRED: 401,
    ERROR_AUTH_INVALID: 401,
    ERROR_AUTH_SERVICE_UNAVAILABLE: 503,
    ERROR_ASSESSMENT_NOT_FOUND: 404,
    ERROR_ASSESSMENT_NOT_OWNED: 403,
    ERROR_REPORT_LOCKED: 402,
    ERROR_ASSESSMENT_NOT_COMPLETED: 409,
    ERROR_REPORT_SERVICE_UNAVAILABLE: 503,
    ERROR_REPORT_BUILD_FAILED: 500,
}

LoadReport = Callable[..., Awaitable[dict[str, Any]]]


def report_failed_outcome(error_code: str, assessment_id: str = "") -> dict[str, Any]:
    """Return a safe failed delivery outcome with no paid report fields."""
    return _validated_error(
        {
            "schema_version": SCHEMA_VERSION,
            "state": "FAILED",
            "assessment_id": assessment_id,
            "error_code": error_code,
        }
    )


def report_service_unavailable(assessment_id: str = "") -> dict[str, Any]:
    """Return a safe unconfigured/unavailable delivery outcome."""
    return report_failed_outcome(ERROR_REPORT_SERVICE_UNAVAILABLE, assessment_id)


def report_http_status(outcome: dict[str, Any]) -> int:
    """Map a delivery outcome to an HTTP status code."""
    if is_report_payload(outcome):
        return 200
    error_code = outcome.get("error_code")
    if isinstance(error_code, str):
        return REPORT_HTTP_STATUS.get(error_code, 500)
    return 500


async def deliver_unlocked_readiness_report(
    *,
    repository: AssessmentRepository,
    assessment_id: str,
    owner_user_id: str,
    load_report: LoadReport | None = None,
) -> dict[str, Any]:
    """Return readiness.report.v1 for the verified owner of an unlocked assessment."""
    identifier = assessment_id.strip() if isinstance(assessment_id, str) else ""
    if not identifier:
        return report_failed_outcome(ERROR_ASSESSMENT_NOT_FOUND, identifier)
    if not isinstance(owner_user_id, str) or not owner_user_id.strip():
        return report_failed_outcome(ERROR_AUTH_INVALID, identifier)
    try:
        record = await repository.get_assessment(identifier)
    except Exception:
        logger.error("unlocked report assessment lookup failed")
        return report_service_unavailable(identifier)
    if record is None:
        return report_failed_outcome(ERROR_ASSESSMENT_NOT_FOUND, identifier)
    if record.owner_user_id is None or record.owner_user_id != owner_user_id.strip():
        return report_failed_outcome(ERROR_ASSESSMENT_NOT_OWNED, identifier)
    if record.access_state != "UNLOCKED":
        return report_failed_outcome(ERROR_REPORT_LOCKED, identifier)
    loader = load_report if load_report is not None else get_readiness_report_async
    try:
        outcome = await loader(assessment_id=identifier, repository=repository)
    except Exception:
        logger.error("unlocked report assembly failed")
        return report_failed_outcome(ERROR_REPORT_BUILD_FAILED, identifier)
    return _report_from_package_m(identifier, outcome)


def _report_from_package_m(assessment_id: str, outcome: object) -> dict[str, Any]:
    if not isinstance(outcome, dict):
        return report_failed_outcome(ERROR_REPORT_BUILD_FAILED, assessment_id)
    if outcome.get("state") == "COMPLETED":
        report = outcome.get("report")
        if is_report_payload(report):
            try:
                draft_validator("readiness_report.schema.json").validate(report)
            except ValidationError:
                logger.error("unlocked report failed schema validation")
                return report_failed_outcome(ERROR_REPORT_BUILD_FAILED, assessment_id)
            return report
        return report_failed_outcome(ERROR_REPORT_BUILD_FAILED, assessment_id)
    error_code = outcome.get("error_code")
    if error_code == REPORTING_NOT_FOUND:
        return report_failed_outcome(ERROR_ASSESSMENT_NOT_FOUND, assessment_id)
    if error_code == REPORTING_NOT_COMPLETED:
        return report_failed_outcome(ERROR_ASSESSMENT_NOT_COMPLETED, assessment_id)
    return report_failed_outcome(ERROR_REPORT_BUILD_FAILED, assessment_id)


def _validated_error(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        draft_validator(SCHEMA_FILENAME).validate(payload)
    except ValidationError:
        logger.error("unlocked report error outcome failed schema validation")
        return {
            "schema_version": SCHEMA_VERSION,
            "state": "FAILED",
            "assessment_id": str(payload.get("assessment_id") or ""),
            "error_code": ERROR_REPORT_SERVICE_UNAVAILABLE,
        }
    return payload

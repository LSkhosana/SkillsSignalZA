"""Package O: claim an existing anonymous assessment for a verified user.

Ownership only. This service does not score, rebuild Package M, or unlock
the paid report. The raw claim token is hashed in memory and never logged.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from jsonschema.exceptions import ValidationError

from app.engine.schema_registry import draft_validator
from app.repositories.interfaces import AssessmentRepository
from app.services.anonymous_assessment import hash_claim_token

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "assessment.claim.v1"
SCHEMA_FILENAME = "assessment_claim_response.schema.json"

ERROR_AUTH_REQUIRED = "AUTH_REQUIRED"
ERROR_AUTH_INVALID = "AUTH_INVALID"
ERROR_AUTH_SERVICE_UNAVAILABLE = "AUTH_SERVICE_UNAVAILABLE"
ERROR_INVALID_CLAIM_REQUEST = "INVALID_CLAIM_REQUEST"
ERROR_ASSESSMENT_NOT_FOUND = "ASSESSMENT_NOT_FOUND"
ERROR_CLAIM_TOKEN_INVALID = "CLAIM_TOKEN_INVALID"
ERROR_CLAIM_EXPIRED = "CLAIM_EXPIRED"
ERROR_ASSESSMENT_ALREADY_CLAIMED = "ASSESSMENT_ALREADY_CLAIMED"
ERROR_CLAIM_SERVICE_UNAVAILABLE = "CLAIM_SERVICE_UNAVAILABLE"

CLAIM_HTTP_STATUS = {
    ERROR_AUTH_REQUIRED: 401,
    ERROR_AUTH_INVALID: 401,
    ERROR_AUTH_SERVICE_UNAVAILABLE: 503,
    ERROR_INVALID_CLAIM_REQUEST: 422,
    ERROR_ASSESSMENT_NOT_FOUND: 404,
    ERROR_CLAIM_TOKEN_INVALID: 403,
    ERROR_CLAIM_EXPIRED: 410,
    ERROR_ASSESSMENT_ALREADY_CLAIMED: 409,
    ERROR_CLAIM_SERVICE_UNAVAILABLE: 503,
}


def claim_failed_outcome(error_code: str, assessment_id: str = "") -> dict[str, Any]:
    """Return a safe failed claim outcome with no owner, hash, or token."""
    return _validated_outcome(
        {
            "schema_version": SCHEMA_VERSION,
            "state": "FAILED",
            "assessment_id": assessment_id,
            "access_state": None,
            "claimed_at": None,
            "error_code": error_code,
        }
    )


def claim_service_unavailable(assessment_id: str = "") -> dict[str, Any]:
    """Return a safe unconfigured/unavailable claim outcome."""
    return claim_failed_outcome(ERROR_CLAIM_SERVICE_UNAVAILABLE, assessment_id)


def claim_http_status(outcome: dict[str, Any]) -> int:
    """Map a claim outcome to an HTTP status code."""
    if outcome.get("state") == "CLAIMED":
        return 200
    error_code = outcome.get("error_code")
    if isinstance(error_code, str):
        return CLAIM_HTTP_STATUS.get(error_code, 500)
    return 500


async def claim_assessment_for_user(
    *,
    repository: AssessmentRepository,
    assessment_id: str,
    authenticated_user_id: str,
    claim_token: str,
    claimed_at: datetime | None = None,
) -> dict[str, Any]:
    """Attach a verified user as owner of one existing anonymous assessment."""
    identifier = assessment_id.strip() if isinstance(assessment_id, str) else ""
    if not identifier or not isinstance(claim_token, str) or not claim_token.strip():
        return claim_failed_outcome(ERROR_INVALID_CLAIM_REQUEST, identifier)
    if not isinstance(authenticated_user_id, str) or not authenticated_user_id.strip():
        return claim_failed_outcome(ERROR_AUTH_INVALID, identifier)
    presented_hash = hash_claim_token(claim_token)
    instant = claimed_at if claimed_at is not None else datetime.now(UTC)
    try:
        result = await repository.claim_assessment(
            assessment_id=identifier,
            authenticated_user_id=authenticated_user_id.strip(),
            presented_claim_token_hash=presented_hash,
            claimed_at=instant,
        )
    except Exception:
        logger.error("assessment claim persistence failed")
        return claim_service_unavailable(identifier)
    if result.status in {"claimed", "idempotent"}:
        claimed_instant = result.claimed_at if result.claimed_at is not None else instant
        return _validated_outcome(
            {
                "schema_version": SCHEMA_VERSION,
                "state": "CLAIMED",
                "assessment_id": result.assessment_id,
                "access_state": "PREVIEW",
                "claimed_at": _rfc3339(claimed_instant),
                "error_code": None,
            }
        )
    error_by_status = {
        "not_found": ERROR_ASSESSMENT_NOT_FOUND,
        "token_invalid": ERROR_CLAIM_TOKEN_INVALID,
        "expired": ERROR_CLAIM_EXPIRED,
        "conflict": ERROR_ASSESSMENT_ALREADY_CLAIMED,
    }
    error_code = error_by_status.get(result.status, ERROR_CLAIM_SERVICE_UNAVAILABLE)
    return claim_failed_outcome(error_code, identifier)


def _rfc3339(value: datetime) -> str:
    instant = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return instant.astimezone(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validated_outcome(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        draft_validator(SCHEMA_FILENAME).validate(payload)
    except ValidationError:
        logger.error("assessment claim outcome failed schema validation")
        return {
            "schema_version": SCHEMA_VERSION,
            "state": "FAILED",
            "assessment_id": str(payload.get("assessment_id") or ""),
            "access_state": None,
            "claimed_at": None,
            "error_code": ERROR_CLAIM_SERVICE_UNAVAILABLE,
        }
    return payload

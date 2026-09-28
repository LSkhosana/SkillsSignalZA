"""Package FL-4: list owned assessment summaries for the verified caller.

Owner scope only. This service does not score, claim, charge, unlock, or
return CV text, evidence, tokens, or payment secrets.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from jsonschema.exceptions import ValidationError

from app.engine.schema_registry import draft_validator
from app.repositories.interfaces import AssessmentRepository
from app.repositories.records import OwnedAssessmentSummary

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "assessment.summaries.v1"
SCHEMA_FILENAME = "assessment_summaries.schema.json"
DEFAULT_LIMIT = 50
MAX_LIMIT = 50

ERROR_AUTH_REQUIRED = "AUTH_REQUIRED"
ERROR_AUTH_INVALID = "AUTH_INVALID"
ERROR_AUTH_SERVICE_UNAVAILABLE = "AUTH_SERVICE_UNAVAILABLE"
ERROR_SUMMARIES_SERVICE_UNAVAILABLE = "SUMMARIES_SERVICE_UNAVAILABLE"

SUMMARIES_HTTP_STATUS = {
    ERROR_AUTH_REQUIRED: 401,
    ERROR_AUTH_INVALID: 401,
    ERROR_AUTH_SERVICE_UNAVAILABLE: 503,
    ERROR_SUMMARIES_SERVICE_UNAVAILABLE: 503,
}


def summaries_failed_outcome(
    error_code: str, *, limit: int = DEFAULT_LIMIT, offset: int = 0
) -> dict[str, Any]:
    """Return a safe failed listing outcome with no assessment rows."""
    page_size = _clamp_limit(limit)
    start = max(offset, 0)
    return _validated_outcome(
        {
            "schema_version": SCHEMA_VERSION,
            "state": "FAILED",
            "items": [],
            "limit": page_size,
            "offset": start,
            "has_more": False,
            "error_code": error_code,
        }
    )


def summaries_service_unavailable(*, limit: int = DEFAULT_LIMIT, offset: int = 0) -> dict[str, Any]:
    """Return a safe unconfigured/unavailable listing outcome."""
    return summaries_failed_outcome(
        ERROR_SUMMARIES_SERVICE_UNAVAILABLE,
        limit=limit,
        offset=offset,
    )


def summaries_http_status(outcome: dict[str, Any]) -> int:
    """Map a listing outcome to an HTTP status code."""
    if outcome.get("state") == "LISTED":
        return 200
    error_code = outcome.get("error_code")
    if isinstance(error_code, str):
        return SUMMARIES_HTTP_STATUS.get(error_code, 500)
    return 500


async def list_owned_assessment_summaries(
    *,
    repository: AssessmentRepository,
    owner_user_id: str,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> dict[str, Any]:
    """Return newest-first summaries owned by the authenticated subject only."""
    page_size = _clamp_limit(limit)
    start = max(offset, 0)
    if not isinstance(owner_user_id, str) or not owner_user_id.strip():
        return summaries_failed_outcome(ERROR_AUTH_INVALID, limit=page_size, offset=start)
    owner = owner_user_id.strip()
    try:
        rows = await repository.list_owned_assessment_summaries(
            owner_user_id=owner,
            limit=page_size + 1,
            offset=start,
        )
    except Exception:
        logger.error("owned assessment summary listing failed")
        return summaries_service_unavailable(limit=page_size, offset=start)
    has_more = len(rows) > page_size
    items = [_item(row) for row in rows[:page_size]]
    return _validated_outcome(
        {
            "schema_version": SCHEMA_VERSION,
            "state": "LISTED",
            "items": items,
            "limit": page_size,
            "offset": start,
            "has_more": has_more,
            "error_code": None,
        }
    )


def _clamp_limit(limit: int) -> int:
    if not isinstance(limit, int) or isinstance(limit, bool):
        return DEFAULT_LIMIT
    return min(max(limit, 1), MAX_LIMIT)


def _item(row: OwnedAssessmentSummary) -> dict[str, Any]:
    assessed = row.assessed_at if row.assessed_at is not None else datetime.now(UTC)
    return {
        "assessment_id": row.assessment_id,
        "track": row.track,
        "final_score": row.final_score,
        "band": row.band,
        "access_state": row.access_state,
        "assessed_at": _rfc3339(assessed),
        "unlocked_at": _rfc3339(row.unlocked_at) if row.unlocked_at is not None else None,
    }


def _rfc3339(value: datetime) -> str:
    instant = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return instant.astimezone(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validated_outcome(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        draft_validator(SCHEMA_FILENAME).validate(payload)
    except ValidationError:
        logger.error("owned assessment summary outcome failed schema validation")
        return {
            "schema_version": SCHEMA_VERSION,
            "state": "FAILED",
            "items": [],
            "limit": DEFAULT_LIMIT,
            "offset": 0,
            "has_more": False,
            "error_code": ERROR_SUMMARIES_SERVICE_UNAVAILABLE,
        }
    return payload

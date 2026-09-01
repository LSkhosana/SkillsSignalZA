"""Assessment HTTP boundary.

Routes validate the transport envelope and map engine states to HTTP
status codes. Scoring rules belong in `app.engine.scoring`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.engine.outcomes import engine_outcome
from app.schemas.scoring import ScoreAssessmentRequest
from app.services.assessment_scoring import score_frozen_assessment

router = APIRouter()

HTTP_STATUS_BY_STATE = {
    "COMPLETED": 200,
    "REVIEW_REQUIRED": 200,
    "INPUT_INVALID": 422,
    "TRACK_INVALID": 422,
    "RULESET_NOT_FOUND": 503,
    "RULESET_INVALID": 503,
    "QA_FAILED": 500,
    "FAILED": 500,
}


@router.post(
    "/score",
    summary="Score a frozen assessment run",
    description=(
        "Invoke the Package D deterministic engine with caller-supplied identity, "
        "assessment input, evidence facts, scoring context, and source records. "
        "The response body is the canonical engine outcome with no wrapper object."
    ),
    responses={
        200: {"description": "COMPLETED or REVIEW_REQUIRED engine outcome."},
        422: {
            "description": (
                "INPUT_INVALID or TRACK_INVALID engine outcome, or FastAPI envelope "
                "validation failure."
            )
        },
        500: {"description": "QA_FAILED or FAILED engine outcome."},
        503: {"description": "RULESET_NOT_FOUND or RULESET_INVALID engine outcome."},
    },
)
def post_assessment_score(payload: ScoreAssessmentRequest) -> JSONResponse:
    try:
        outcome = score_frozen_assessment(payload)
    except Exception:
        outcome = engine_outcome("FAILED", error_code="FAILED")
    return JSONResponse(content=outcome, status_code=_http_status(outcome))


def _http_status(outcome: dict[str, Any]) -> int:
    state = outcome.get("state")
    if not isinstance(state, str):
        return 500
    return HTTP_STATUS_BY_STATE.get(state, 500)

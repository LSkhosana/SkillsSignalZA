"""Report HTTP boundary.

GET /api/v1/assessments/{assessment_id}/report delivers the canonical
readiness.report.v1 payload to the verified owner of an unlocked assessment.
Authorization and entitlement live in the delivery service. Package M only
assembles the report from the persisted canonical result.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.auth import AuthServiceUnavailable, parse_bearer_authorization
from app.core.resources import resolve_report_resources
from app.services.assessment_report import (
    ERROR_AUTH_INVALID,
    ERROR_AUTH_SERVICE_UNAVAILABLE,
    deliver_unlocked_readiness_report,
    report_failed_outcome,
    report_http_status,
    report_service_unavailable,
)

router = APIRouter()


@router.get(
    "/{assessment_id}/report",
    summary="Get the unlocked Readiness Report",
    description=(
        "Return canonical readiness.report.v1 for the verified owner of an "
        "UNLOCKED completed assessment. Does not rescore, charge, or mutate state."
    ),
    responses={
        200: {"description": "Canonical readiness.report.v1 payload."},
        401: {"description": "Missing or invalid Authorization bearer token."},
        402: {"description": "Verified owner, but the assessment remains PREVIEW."},
        403: {"description": "Caller does not own the assessment."},
        404: {"description": "Assessment does not exist."},
        409: {"description": "Latest persisted run is not COMPLETED."},
        500: {"description": "Persisted result could not be assembled into a report."},
        503: {"description": "Auth or persistence infrastructure unavailable."},
    },
)
async def get_unlocked_assessment_report(assessment_id: str, request: Request) -> JSONResponse:
    access_token, auth_error = parse_bearer_authorization(request.headers.get("Authorization"))
    if auth_error is not None:
        payload = report_failed_outcome(auth_error, assessment_id)
        return JSONResponse(content=payload, status_code=report_http_status(payload))
    repository, verifier = await resolve_report_resources(request.app)
    if repository is None or verifier is None:
        payload = report_service_unavailable(assessment_id)
        return JSONResponse(content=payload, status_code=503)
    try:
        principal = await verifier.verify_access_token(access_token or "")
    except AuthServiceUnavailable:
        payload = report_failed_outcome(ERROR_AUTH_SERVICE_UNAVAILABLE, assessment_id)
        return JSONResponse(content=payload, status_code=503)
    except Exception:
        payload = report_failed_outcome(ERROR_AUTH_SERVICE_UNAVAILABLE, assessment_id)
        return JSONResponse(content=payload, status_code=503)
    if principal is None or not principal.subject:
        payload = report_failed_outcome(ERROR_AUTH_INVALID, assessment_id)
        return JSONResponse(content=payload, status_code=401)
    try:
        load_report = getattr(request.app.state, "load_report", None)
        outcome = await deliver_unlocked_readiness_report(
            repository=repository,
            assessment_id=assessment_id,
            owner_user_id=principal.subject,
            load_report=load_report,
        )
    except Exception:
        outcome = report_service_unavailable(assessment_id)
        return JSONResponse(content=outcome, status_code=503)
    return JSONResponse(content=outcome, status_code=report_http_status(outcome))

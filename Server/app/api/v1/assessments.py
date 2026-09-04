"""Assessment HTTP boundary.

Routes validate the transport envelope and map engine states to HTTP
status codes. Scoring rules belong in `app.engine.scoring`.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.datastructures import UploadFile

from app.core.resources import resolve_submission_resources, submission_overrides
from app.engine.outcomes import engine_outcome
from app.repositories.supabase import MAX_FILE_SIZE_BYTES
from app.schemas.scoring import ScoreAssessmentRequest
from app.services.anonymous_assessment import (
    ERROR_FILE_TOO_LARGE,
    ERROR_INVALID_SUBMISSION,
    anonymous_failed_outcome,
    anonymous_http_status,
    anonymous_service_unavailable,
    submit_anonymous_assessment,
)
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


@router.post(
    "",
    summary="Submit an anonymous assessment",
    description=(
        "Accept a customer CV upload plus optional links, run the server-owned "
        "assessment pipeline, persist the outcome, and return readiness.preview.v1 only."
    ),
    responses={
        201: {"description": "COMPLETED persisted preview."},
        202: {"description": "REVIEW_REQUIRED persisted without a preview."},
        422: {"description": "Invalid submission or NOT_SCORABLE persisted outcome."},
        503: {"description": "Persistence unavailable or internal orchestration failure."},
    },
)
@router.post("/")
async def post_anonymous_assessment(request: Request) -> JSONResponse:
    repository, storage = await resolve_submission_resources(request.app)
    if repository is None or storage is None:
        payload = anonymous_service_unavailable()
        return JSONResponse(content=payload, status_code=503)
    parsed = await _parse_anonymous_multipart(request)
    if isinstance(parsed, JSONResponse):
        return parsed
    try:
        outcome = await submit_anonymous_assessment(
            repository=repository,
            storage=storage,
            **parsed,
            **submission_overrides(request.app),
        )
    except Exception:
        outcome = anonymous_service_unavailable()
        return JSONResponse(content=outcome, status_code=503)
    return JSONResponse(content=outcome, status_code=anonymous_http_status(outcome))


def _http_status(outcome: dict[str, Any]) -> int:
    state = outcome.get("state")
    if not isinstance(state, str):
        return 500
    return HTTP_STATUS_BY_STATE.get(state, 500)


async def _parse_anonymous_multipart(request: Request) -> dict[str, Any] | JSONResponse:
    try:
        form = await request.form()
    except Exception:
        return _invalid_submission_response()
    try:
        track = form.get("track")
        cv_parts = form.getlist("cv")
        links_field = form.get("links")
        if not isinstance(track, str) or len(cv_parts) != 1:
            return _invalid_submission_response()
        cv = cv_parts[0]
        if not isinstance(cv, UploadFile):
            return _invalid_submission_response()
        file_bytes = await _read_bounded_cv(cv)
        if isinstance(file_bytes, JSONResponse):
            return file_bytes
        links = _parse_links_field(links_field)
        if isinstance(links, JSONResponse):
            return links
        return {
            "track": track,
            "cv_file_bytes": file_bytes,
            "original_filename": cv.filename or "",
            "media_type": cv.content_type or "",
            "links": links,
        }
    finally:
        close = getattr(form, "close", None)
        if close is not None:
            result = close()
            if hasattr(result, "__await__"):
                await result


async def _read_bounded_cv(cv: UploadFile) -> bytes | JSONResponse:
    """Read at most MAX_FILE_SIZE_BYTES + 1 so oversized uploads never fill memory."""
    file_bytes = await cv.read(MAX_FILE_SIZE_BYTES + 1)
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        return _file_too_large_response()
    return bytes(file_bytes)


def _parse_links_field(links_field: object) -> list[dict[str, Any]] | JSONResponse:
    if links_field is None or links_field == "":
        return []
    if not isinstance(links_field, str):
        return _invalid_submission_response()
    try:
        payload = json.loads(links_field)
    except json.JSONDecodeError:
        return _invalid_submission_response()
    if not isinstance(payload, list):
        return _invalid_submission_response()
    return payload


def _invalid_submission_response() -> JSONResponse:
    return JSONResponse(
        content=anonymous_failed_outcome(ERROR_INVALID_SUBMISSION),
        status_code=422,
    )


def _file_too_large_response() -> JSONResponse:
    return JSONResponse(
        content=anonymous_failed_outcome(ERROR_FILE_TOO_LARGE),
        status_code=422,
    )

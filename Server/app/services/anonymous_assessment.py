"""Anonymous assessment submission orchestration (Package N).

Sequence: validate transport -> server identity -> Package K once ->
private CV storage -> Package L persistence -> Package M preview.

This service never invokes the scoring engine directly and never returns
the paid readiness report or Package K internals to the caller.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from jsonschema.exceptions import ValidationError

from app.engine.extraction import retrieve_candidate_link
from app.engine.schema_registry import draft_validator
from app.repositories.interfaces import AssessmentRepository, DocumentStorage
from app.repositories.supabase import (
    MAX_FILE_SIZE_BYTES,
    SUPPORTED_MEDIA_TYPES,
    DocumentStorageError,
    opaque_storage_path,
)
from app.services.assessment_persistence import (
    PERSISTABLE_STATES,
    persist_assessment_outcome_async,
)
from app.services.assessment_pipeline import run_assessment_pipeline
from app.services.readiness_reporting import get_readiness_report_async

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "anonymous.assessment.v1"
CONTRACT_VERSION = "1.2.0"
RUBRIC_VERSION = "V2"
MAX_LINKS = 5
ALLOWED_TRACKS = frozenset({"software_engineering", "data_analytics"})
ALLOWED_DECLARED_TYPES = frozenset(
    {
        "repository",
        "portfolio",
        "project",
        "deployed_project",
        "kaggle",
        "dashboard",
        "other_professional",
    }
)
LINK_OBJECT_KEYS = frozenset({"submitted_url", "declared_type"})

ERROR_INVALID_SUBMISSION = "INVALID_SUBMISSION"
ERROR_UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
ERROR_FILE_TOO_LARGE = "FILE_TOO_LARGE"
ERROR_TOO_MANY_LINKS = "TOO_MANY_LINKS"
ERROR_ASSESSMENT_PIPELINE_FAILED = "ASSESSMENT_PIPELINE_FAILED"
ERROR_STORAGE_FAILED = "STORAGE_FAILED"
ERROR_PERSISTENCE_FAILED = "PERSISTENCE_FAILED"
ERROR_REPORTING_FAILED = "REPORTING_FAILED"
ERROR_ASSESSMENT_SERVICE_UNAVAILABLE = "ASSESSMENT_SERVICE_UNAVAILABLE"

INPUT_ERROR_CODES = frozenset(
    {
        ERROR_INVALID_SUBMISSION,
        ERROR_UNSUPPORTED_MEDIA_TYPE,
        ERROR_FILE_TOO_LARGE,
        ERROR_TOO_MANY_LINKS,
    }
)
SUCCESS_PERSISTENCE_STATES = frozenset({"PERSISTED", "PERSISTENCE_NOOP"})

RunPipeline = Callable[..., dict[str, Any]]
RetrieveLink = Callable[..., dict[str, Any]]
LoadReport = Callable[..., Awaitable[dict[str, Any]]]
IdentityFactory = Callable[[], "AssessmentIdentity"]
ClaimTokenFactory = Callable[[], str]


@dataclass(frozen=True)
class AssessmentIdentity:
    """Server-owned opaque identifiers for one anonymous submission."""

    assessment_id: str
    run_id: str
    document_id: str
    candidate_ref: str


class SubmissionHalt(Exception):
    """Safe validation failure that never includes secrets or CV bytes."""

    def __init__(self, error_code: str) -> None:
        self.error_code = error_code
        super().__init__(error_code)


def default_identity_factory() -> AssessmentIdentity:
    """Return cryptographically random opaque IDs that satisfy storage path rules."""
    return AssessmentIdentity(
        assessment_id=f"a-{uuid.uuid4()}",
        run_id=f"r-{uuid.uuid4()}",
        document_id=f"d-{uuid.uuid4()}",
        candidate_ref=f"c-{uuid.uuid4()}",
    )


def default_claim_token_factory() -> str:
    """Return a high-entropy claim token. Callers must not persist the raw value."""
    return secrets.token_urlsafe(32)


def hash_claim_token(raw_claim_token: str) -> str:
    """Return SHA-256 hex of the raw claim token. The raw value is not stored."""
    return hashlib.sha256(raw_claim_token.encode("utf-8")).hexdigest()


def utc_timestamp() -> str:
    """Return an RFC 3339 UTC timestamp with second precision."""
    return datetime.now(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def anonymous_failed_outcome(error_code: str) -> dict[str, Any]:
    """Return a safe failed outcome with no identity or claim token."""
    return _outcome(
        state="FAILED",
        error_code=error_code,
        assessment_id="",
        run_id="",
        access_state=None,
        claim_token=None,
        preview=None,
    )


def anonymous_service_unavailable() -> dict[str, Any]:
    """Return a safe unconfigured/unavailable outcome."""
    return anonymous_failed_outcome(ERROR_ASSESSMENT_SERVICE_UNAVAILABLE)


async def submit_anonymous_assessment(
    *,
    track: str,
    cv_file_bytes: bytes,
    original_filename: str,
    media_type: str,
    links: list[dict[str, Any]],
    repository: AssessmentRepository,
    storage: DocumentStorage,
    assessed_at: str | None = None,
    submitted_at: str | None = None,
    identity_factory: IdentityFactory | None = None,
    claim_token_factory: ClaimTokenFactory | None = None,
    retrieve_link: RetrieveLink | None = None,
    run_pipeline: RunPipeline | None = None,
    load_report: LoadReport | None = None,
) -> dict[str, Any]:
    """Orchestrate one anonymous CV submission through K, storage, L, and M."""
    try:
        if track not in ALLOWED_TRACKS:
            raise SubmissionHalt(ERROR_INVALID_SUBMISSION)
        canonical_media = _canonical_media_type(media_type)
        filename = _validated_filename(original_filename, canonical_media)
        validated_links = _validated_links(links)
        _validated_cv_bytes(cv_file_bytes)
        identity = (identity_factory or default_identity_factory)()
        raw_claim_token = (claim_token_factory or default_claim_token_factory)()
        claim_token_hash = hash_claim_token(raw_claim_token)
        timestamp = assessed_at or utc_timestamp()
        submitted = submitted_at or timestamp
        assessment_input = _canonical_assessment_input(
            track=track,
            identity=identity,
            file_bytes=cv_file_bytes,
            original_filename=filename,
            media_type=canonical_media,
            links=validated_links,
            submitted_at=submitted,
        )
        pipeline = run_pipeline or run_assessment_pipeline
        pipeline_outcome = pipeline(
            assessment_input=assessment_input,
            cv_file_bytes=cv_file_bytes,
            assessment_id=identity.assessment_id,
            run_id=identity.run_id,
            assessed_at=timestamp,
            retrieve_link=retrieve_link or retrieve_candidate_link,
        )
        pipeline_state = str(pipeline_outcome.get("state") or "")
        if pipeline_state not in PERSISTABLE_STATES:
            logger.info(
                "anonymous assessment pipeline not persistable assessment_id=%s state=%s",
                identity.assessment_id,
                pipeline_state,
            )
            return _outcome(
                state="FAILED",
                error_code=ERROR_ASSESSMENT_PIPELINE_FAILED,
                assessment_id=identity.assessment_id,
                run_id=identity.run_id,
                access_state=None,
                claim_token=None,
                preview=None,
            )
        try:
            document_metadata = await storage.put_private_document(
                assessment_id=identity.assessment_id,
                document_id=identity.document_id,
                file_bytes=cv_file_bytes,
                media_type=canonical_media,
                original_filename=filename,
            )
        except DocumentStorageError:
            return _outcome(
                state="FAILED",
                error_code=ERROR_STORAGE_FAILED,
                assessment_id=identity.assessment_id,
                run_id=identity.run_id,
                access_state=None,
                claim_token=None,
                preview=None,
            )
        except Exception:
            logger.error("anonymous assessment storage failed")
            return _outcome(
                state="FAILED",
                error_code=ERROR_STORAGE_FAILED,
                assessment_id=identity.assessment_id,
                run_id=identity.run_id,
                access_state=None,
                claim_token=None,
                preview=None,
            )
        storage_path = str(document_metadata.get("storage_path") or "")
        if not _document_metadata_matches(
            assessment_id=identity.assessment_id,
            assessment_input=assessment_input,
            document_metadata=document_metadata,
            file_bytes=cv_file_bytes,
        ):
            await _delete_uploaded(storage, storage_path)
            return _outcome(
                state="FAILED",
                error_code=ERROR_STORAGE_FAILED,
                assessment_id=identity.assessment_id,
                run_id=identity.run_id,
                access_state=None,
                claim_token=None,
                preview=None,
            )
        persistence = await persist_assessment_outcome_async(
            assessment_input=assessment_input,
            pipeline_outcome=pipeline_outcome,
            document_metadata=document_metadata,
            assessed_at=timestamp,
            claim_token_hash=claim_token_hash,
            expires_at=None,
            repository=repository,
        )
        persisted = persistence.get("state") in SUCCESS_PERSISTENCE_STATES
        if not persisted:
            await _compensate_uploaded_object(
                storage=storage,
                storage_path=storage_path,
                repository=repository,
                assessment_id=identity.assessment_id,
            )
            return _outcome(
                state="FAILED",
                error_code=ERROR_PERSISTENCE_FAILED,
                assessment_id=identity.assessment_id,
                run_id=identity.run_id,
                access_state=None,
                claim_token=None,
                preview=None,
            )
        returned_token = raw_claim_token if persistence.get("state") == "PERSISTED" else None
        if pipeline_state == "COMPLETED":
            reporter = load_report or get_readiness_report_async
            try:
                reporting = await reporter(
                    assessment_id=identity.assessment_id,
                    repository=repository,
                )
            except Exception:
                logger.error("anonymous assessment reporting failed")
                return _outcome(
                    state="FAILED",
                    error_code=ERROR_REPORTING_FAILED,
                    assessment_id=identity.assessment_id,
                    run_id=identity.run_id,
                    access_state="PREVIEW",
                    claim_token=returned_token,
                    preview=None,
                )
            preview = reporting.get("preview") if reporting.get("state") == "COMPLETED" else None
            if not isinstance(preview, dict):
                return _outcome(
                    state="FAILED",
                    error_code=ERROR_REPORTING_FAILED,
                    assessment_id=identity.assessment_id,
                    run_id=identity.run_id,
                    access_state="PREVIEW",
                    claim_token=returned_token,
                    preview=None,
                )
            return _outcome(
                state="COMPLETED",
                error_code=None,
                assessment_id=identity.assessment_id,
                run_id=identity.run_id,
                access_state="PREVIEW",
                claim_token=returned_token,
                preview=preview,
            )
        return _outcome(
            state=pipeline_state,
            error_code=pipeline_outcome.get("error_code")
            if isinstance(pipeline_outcome.get("error_code"), str)
            else None,
            assessment_id=identity.assessment_id,
            run_id=identity.run_id,
            access_state="PREVIEW",
            claim_token=returned_token,
            preview=None,
        )
    except SubmissionHalt as exc:
        return _outcome(
            state="FAILED",
            error_code=exc.error_code,
            assessment_id="",
            run_id="",
            access_state=None,
            claim_token=None,
            preview=None,
        )
    except Exception:
        logger.error("anonymous assessment orchestration failed")
        return _outcome(
            state="FAILED",
            error_code=ERROR_ASSESSMENT_SERVICE_UNAVAILABLE,
            assessment_id="",
            run_id="",
            access_state=None,
            claim_token=None,
            preview=None,
        )


def anonymous_http_status(outcome: dict[str, Any]) -> int:
    """Map a Package N outcome to a stable HTTP status code."""
    state = outcome.get("state")
    if state == "COMPLETED" and isinstance(outcome.get("preview"), dict):
        return 201
    if state == "REVIEW_REQUIRED":
        return 202
    if state == "NOT_SCORABLE":
        return 422
    error_code = outcome.get("error_code")
    if error_code in INPUT_ERROR_CODES:
        return 422
    return 503


def _canonical_media_type(media_type: str) -> str:
    if not isinstance(media_type, str) or not media_type.strip():
        raise SubmissionHalt(ERROR_UNSUPPORTED_MEDIA_TYPE)
    normalized = media_type.split(";", 1)[0].strip().lower()
    if normalized not in SUPPORTED_MEDIA_TYPES:
        raise SubmissionHalt(ERROR_UNSUPPORTED_MEDIA_TYPE)
    return normalized


def _validated_filename(original_filename: str, media_type: str) -> str:
    if isinstance(original_filename, str) and original_filename.strip():
        return original_filename.strip()
    return "cv.pdf" if media_type == "application/pdf" else "cv.docx"


def _validated_cv_bytes(file_bytes: bytes) -> None:
    if not isinstance(file_bytes, bytes | bytearray) or not file_bytes:
        raise SubmissionHalt(ERROR_INVALID_SUBMISSION)
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise SubmissionHalt(ERROR_FILE_TOO_LARGE)


def _validated_links(links: object) -> list[dict[str, Any]]:
    if links is None:
        return []
    if not isinstance(links, list):
        raise SubmissionHalt(ERROR_INVALID_SUBMISSION)
    if len(links) > MAX_LINKS:
        raise SubmissionHalt(ERROR_TOO_MANY_LINKS)
    validated: list[dict[str, Any]] = []
    for index, item in enumerate(links, start=1):
        if not isinstance(item, dict):
            raise SubmissionHalt(ERROR_INVALID_SUBMISSION)
        if set(item) != LINK_OBJECT_KEYS:
            raise SubmissionHalt(ERROR_INVALID_SUBMISSION)
        submitted_url = item.get("submitted_url")
        declared_type = item.get("declared_type")
        if not isinstance(submitted_url, str) or not submitted_url.strip():
            raise SubmissionHalt(ERROR_INVALID_SUBMISSION)
        if declared_type not in ALLOWED_DECLARED_TYPES:
            raise SubmissionHalt(ERROR_INVALID_SUBMISSION)
        validated.append(
            {
                "link_id": f"link-{index:03d}",
                "submitted_url": submitted_url.strip(),
                "declared_type": declared_type,
            }
        )
    return validated


def _canonical_assessment_input(
    *,
    track: str,
    identity: AssessmentIdentity,
    file_bytes: bytes,
    original_filename: str,
    media_type: str,
    links: list[dict[str, Any]],
    submitted_at: str,
) -> dict[str, Any]:
    if track not in ALLOWED_TRACKS:
        raise SubmissionHalt(ERROR_INVALID_SUBMISSION)
    payload = {
        "contract_version": CONTRACT_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "track": track,
        "candidate_ref": identity.candidate_ref,
        "cv": {
            "document_id": identity.document_id,
            "media_type": media_type,
            "sha256": hashlib.sha256(file_bytes).hexdigest(),
            "original_filename": original_filename,
        },
        "links": links,
        "submitted_at": submitted_at,
    }
    try:
        draft_validator("assessment_input.schema.json").validate(payload)
    except (ValidationError, TypeError, ValueError):
        raise SubmissionHalt(ERROR_INVALID_SUBMISSION) from None
    return payload


def _document_metadata_matches(
    *,
    assessment_id: str,
    assessment_input: dict[str, Any],
    document_metadata: object,
    file_bytes: bytes,
) -> bool:
    if not isinstance(document_metadata, dict):
        return False
    declared = assessment_input["cv"]
    expected_path = opaque_storage_path(
        assessment_id, str(declared["document_id"]), str(declared["media_type"])
    )
    try:
        byte_size = int(document_metadata.get("byte_size"))
    except (TypeError, ValueError):
        return False
    return (
        str(document_metadata.get("document_id")) == str(declared["document_id"])
        and str(document_metadata.get("original_filename")) == str(declared["original_filename"])
        and str(document_metadata.get("media_type")) == str(declared["media_type"])
        and str(document_metadata.get("sha256")).lower() == str(declared["sha256"]).lower()
        and byte_size == len(file_bytes)
        and str(document_metadata.get("storage_path")) == expected_path
    )


async def _delete_uploaded(storage: DocumentStorage, storage_path: str) -> None:
    if not storage_path:
        return
    try:
        await storage.delete_private_document(storage_path)
    except Exception:
        logger.error("anonymous assessment storage cleanup failed")


async def _compensate_uploaded_object(
    *,
    storage: DocumentStorage,
    storage_path: str,
    repository: AssessmentRepository,
    assessment_id: str,
) -> None:
    try:
        existing = await repository.get_assessment(assessment_id)
    except Exception:
        return
    if existing is not None:
        return
    await _delete_uploaded(storage, storage_path)


def _outcome(
    *,
    state: str,
    error_code: str | None,
    assessment_id: str,
    run_id: str,
    access_state: str | None,
    claim_token: str | None,
    preview: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "state": state,
        "assessment_id": assessment_id,
        "run_id": run_id,
        "access_state": access_state,
        "claim_token": claim_token,
        "preview": preview,
        "error_code": error_code,
    }
    draft_validator("anonymous_assessment_response.schema.json").validate(payload)
    return payload

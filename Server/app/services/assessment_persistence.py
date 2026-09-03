"""Package L persistence service downstream of Package K.

This service records canonical pipeline outcomes. It never reruns
extraction, classification, binding, or scoring.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema.exceptions import ValidationError

from app.engine.schema_registry import draft_validator
from app.repositories.interfaces import AssessmentRepository
from app.repositories.records import DocumentMetadata, PersistenceBundle
from app.repositories.supabase import opaque_storage_path

PERSISTENCE_VERSION = "persist.assessment.v1"
CONTRACT_VERSION = "1.2.0"
RUBRIC_VERSION = "V2"
PIPELINE_VERSION = "assessment.pipeline.v1"
PERSISTABLE_STATES = frozenset({"COMPLETED", "REVIEW_REQUIRED", "NOT_SCORABLE"})
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
ERROR_INVALID_ASSESSMENT_INPUT = "INVALID_ASSESSMENT_INPUT"
ERROR_INVALID_PIPELINE_OUTCOME = "INVALID_PIPELINE_OUTCOME"
ERROR_IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
ERROR_DOCUMENT_MISMATCH = "DOCUMENT_MISMATCH"
ERROR_UNSUPPORTED_PIPELINE_STATE = "UNSUPPORTED_PIPELINE_STATE"
ERROR_INVALID_CLAIM_TOKEN_HASH = "INVALID_CLAIM_TOKEN_HASH"
ERROR_PERSISTENCE_CONFLICT = "PERSISTENCE_CONFLICT"
ERROR_PERSISTENCE_EXCEPTION = "PERSISTENCE_EXCEPTION"


def persist_assessment_outcome(
    *,
    assessment_input: dict[str, Any],
    pipeline_outcome: dict[str, Any],
    document_metadata: dict[str, Any],
    assessed_at: str,
    claim_token_hash: str | None = None,
    expires_at: str | None = None,
    repository: AssessmentRepository,
) -> dict[str, Any]:
    """Validate and persist one Package K outcome without mutating it."""
    try:
        return _run_sync(
            assessment_input=assessment_input,
            pipeline_outcome=pipeline_outcome,
            document_metadata=document_metadata,
            assessed_at=assessed_at,
            claim_token_hash=claim_token_hash,
            expires_at=expires_at,
            repository=repository,
        )
    except PersistenceHalt as exc:
        return _outcome(
            state="PERSISTENCE_FAILED",
            error_code=exc.error_code,
            assessment_id=_safe_id(pipeline_outcome, "assessment_id"),
            run_id=_safe_id(pipeline_outcome, "run_id"),
        )
    except Exception:
        return _outcome(
            state="PERSISTENCE_FAILED",
            error_code=ERROR_PERSISTENCE_EXCEPTION,
            assessment_id=_safe_id(pipeline_outcome, "assessment_id"),
            run_id=_safe_id(pipeline_outcome, "run_id"),
        )


async def persist_assessment_outcome_async(
    *,
    assessment_input: dict[str, Any],
    pipeline_outcome: dict[str, Any],
    document_metadata: dict[str, Any],
    assessed_at: str,
    claim_token_hash: str | None = None,
    expires_at: str | None = None,
    repository: AssessmentRepository,
) -> dict[str, Any]:
    """Async persistence entry used by integration tests and future FastAPI routes."""
    try:
        bundle = _validated_bundle(
            assessment_input=assessment_input,
            pipeline_outcome=pipeline_outcome,
            document_metadata=document_metadata,
            assessed_at=assessed_at,
            claim_token_hash=claim_token_hash,
            expires_at=expires_at,
        )
        result = await repository.persist_bundle(bundle)
    except PersistenceHalt as exc:
        return _outcome(
            state="PERSISTENCE_FAILED",
            error_code=exc.error_code,
            assessment_id=_safe_id(pipeline_outcome, "assessment_id"),
            run_id=_safe_id(pipeline_outcome, "run_id"),
        )
    except Exception:
        return _outcome(
            state="PERSISTENCE_FAILED",
            error_code=ERROR_PERSISTENCE_EXCEPTION,
            assessment_id=_safe_id(pipeline_outcome, "assessment_id"),
            run_id=_safe_id(pipeline_outcome, "run_id"),
        )
    return _write_outcome(result.assessment_id, result.run_id, result.status, result.latest_run_id)


def _run_sync(**kwargs: Any) -> dict[str, Any]:
    import asyncio

    return asyncio.run(persist_assessment_outcome_async(**kwargs))


class PersistenceHalt(Exception):
    def __init__(self, error_code: str) -> None:
        self.error_code = error_code
        super().__init__(error_code)


def _validated_bundle(
    *,
    assessment_input: dict[str, Any],
    pipeline_outcome: dict[str, Any],
    document_metadata: dict[str, Any],
    assessed_at: str,
    claim_token_hash: str | None,
    expires_at: str | None,
) -> PersistenceBundle:
    try:
        draft_validator("assessment_input.schema.json").validate(assessment_input)
    except (ValidationError, TypeError, ValueError):
        raise PersistenceHalt(ERROR_INVALID_ASSESSMENT_INPUT) from None
    try:
        draft_validator("assessment_pipeline.schema.json").validate(pipeline_outcome)
    except (ValidationError, TypeError, ValueError):
        raise PersistenceHalt(ERROR_INVALID_PIPELINE_OUTCOME) from None
    if pipeline_outcome.get("state") not in PERSISTABLE_STATES:
        raise PersistenceHalt(ERROR_UNSUPPORTED_PIPELINE_STATE)
    if str(pipeline_outcome.get("track")) != str(assessment_input.get("track")):
        raise PersistenceHalt(ERROR_IDENTITY_MISMATCH)
    if str(pipeline_outcome.get("contract_version")) != CONTRACT_VERSION:
        raise PersistenceHalt(ERROR_IDENTITY_MISMATCH)
    if str(pipeline_outcome.get("rubric_version")) != RUBRIC_VERSION:
        raise PersistenceHalt(ERROR_IDENTITY_MISMATCH)
    if str(pipeline_outcome.get("pipeline_version")) != PIPELINE_VERSION:
        raise PersistenceHalt(ERROR_IDENTITY_MISMATCH)
    assessment_id = str(pipeline_outcome.get("assessment_id") or "")
    run_id = str(pipeline_outcome.get("run_id") or "")
    if not assessment_id or not run_id:
        raise PersistenceHalt(ERROR_IDENTITY_MISMATCH)
    document = _validated_document(assessment_input, document_metadata, assessment_id)
    hashed = _validated_claim_hash(claim_token_hash)
    try:
        assessed_at_dt = _parse_rfc3339(assessed_at)
        expires_at_dt = _parse_rfc3339(expires_at) if expires_at is not None else None
    except (TypeError, ValueError):
        raise PersistenceHalt(ERROR_INVALID_ASSESSMENT_INPUT) from None
    return PersistenceBundle(
        assessment_id=assessment_id,
        run_id=run_id,
        candidate_ref=str(assessment_input["candidate_ref"]),
        track=str(assessment_input["track"]),
        assessed_at=assessed_at_dt,
        claim_token_hash=hashed,
        expires_at=expires_at_dt,
        document=document,
        pipeline_outcome=pipeline_outcome,
        assessment_input=assessment_input,
    )


def _validated_document(
    assessment_input: dict[str, Any], document_metadata: dict[str, Any], assessment_id: str
) -> DocumentMetadata:
    if not isinstance(document_metadata, dict):
        raise PersistenceHalt(ERROR_DOCUMENT_MISMATCH)
    declared = assessment_input["cv"]
    required = (
        "document_id",
        "storage_path",
        "original_filename",
        "media_type",
        "sha256",
        "byte_size",
    )
    if any(key not in document_metadata for key in required):
        raise PersistenceHalt(ERROR_DOCUMENT_MISMATCH)
    sha256 = str(document_metadata["sha256"]).lower()
    declared_sha = str(declared["sha256"]).lower()
    if sha256 != declared_sha or not SHA256_RE.fullmatch(sha256):
        raise PersistenceHalt(ERROR_DOCUMENT_MISMATCH)
    if str(document_metadata["document_id"]) != str(declared["document_id"]):
        raise PersistenceHalt(ERROR_DOCUMENT_MISMATCH)
    if str(document_metadata["original_filename"]) != str(declared["original_filename"]):
        raise PersistenceHalt(ERROR_DOCUMENT_MISMATCH)
    if str(document_metadata["media_type"]) != str(declared["media_type"]):
        raise PersistenceHalt(ERROR_DOCUMENT_MISMATCH)
    try:
        byte_size = int(document_metadata["byte_size"])
    except (TypeError, ValueError):
        raise PersistenceHalt(ERROR_DOCUMENT_MISMATCH) from None
    if byte_size <= 0 or byte_size > 10485760:
        raise PersistenceHalt(ERROR_DOCUMENT_MISMATCH)
    storage_path = str(document_metadata["storage_path"])
    expected_path = opaque_storage_path(
        assessment_id, str(declared["document_id"]), str(declared["media_type"])
    )
    if storage_path != expected_path:
        raise PersistenceHalt(ERROR_DOCUMENT_MISMATCH)
    if Path(storage_path).name == declared["original_filename"]:
        raise PersistenceHalt(ERROR_DOCUMENT_MISMATCH)
    if str(assessment_input["candidate_ref"]) in storage_path.split("/"):
        raise PersistenceHalt(ERROR_DOCUMENT_MISMATCH)
    return DocumentMetadata(
        document_id=str(declared["document_id"]),
        storage_path=storage_path,
        original_filename=str(declared["original_filename"]),
        media_type=str(declared["media_type"]),
        sha256=sha256,
        byte_size=byte_size,
    )


def _validated_claim_hash(claim_token_hash: str | None) -> str | None:
    if claim_token_hash is None:
        return None
    if not isinstance(claim_token_hash, str) or not SHA256_RE.fullmatch(claim_token_hash):
        raise PersistenceHalt(ERROR_INVALID_CLAIM_TOKEN_HASH)
    return claim_token_hash


def _parse_rfc3339(value: object) -> datetime:
    if not isinstance(value, str) or "T" not in value:
        msg = "timestamp must be RFC 3339"
        raise ValueError(msg)
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        msg = "timestamp must be timezone-aware"
        raise ValueError(msg)
    return parsed


def _write_outcome(
    assessment_id: str, run_id: str, status: str, latest_run_id: str | None
) -> dict[str, Any]:
    if status == "conflict":
        return _outcome(
            state="PERSISTENCE_CONFLICT",
            error_code=ERROR_PERSISTENCE_CONFLICT,
            assessment_id=assessment_id,
            run_id=run_id,
            latest_run_id=latest_run_id,
        )
    state = "PERSISTED" if status == "inserted" else "PERSISTENCE_NOOP"
    return _outcome(
        state=state,
        error_code=None,
        assessment_id=assessment_id,
        run_id=run_id,
        access_state="PREVIEW",
        latest_run_id=latest_run_id or run_id,
    )


def _safe_id(payload: object, key: str) -> str:
    if isinstance(payload, dict) and isinstance(payload.get(key), str):
        return payload[key]
    return ""


def _outcome(
    *,
    state: str,
    error_code: str | None,
    assessment_id: str,
    run_id: str,
    access_state: str | None = None,
    latest_run_id: str | None = None,
) -> dict[str, Any]:
    outcome = {
        "state": state,
        "error_code": error_code,
        "persistence_version": PERSISTENCE_VERSION,
        "contract_version": CONTRACT_VERSION,
        "assessment_id": assessment_id,
        "run_id": run_id,
        "access_state": access_state,
        "latest_run_id": latest_run_id,
    }
    draft_validator("assessment_persistence.schema.json").validate(outcome)
    return outcome

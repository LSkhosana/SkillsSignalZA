"""Package O claim orchestration tests. No database or live Auth network."""

from __future__ import annotations

import ast
import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.engine.schema_registry import draft_validator
from app.repositories.records import AssessmentRecord, ClaimWriteResult
from app.services.anonymous_assessment import hash_claim_token
from app.services.assessment_claim import (
    ERROR_ASSESSMENT_ALREADY_CLAIMED,
    ERROR_ASSESSMENT_NOT_FOUND,
    ERROR_AUTH_INVALID,
    ERROR_CLAIM_EXPIRED,
    ERROR_CLAIM_SERVICE_UNAVAILABLE,
    ERROR_CLAIM_TOKEN_INVALID,
    ERROR_INVALID_CLAIM_REQUEST,
    SCHEMA_VERSION,
    claim_assessment_for_user,
    claim_failed_outcome,
    claim_http_status,
    claim_service_unavailable,
)
from tests.unit.services.test_anonymous_assessment import IDENTITY, RAW_CLAIM, RecordingRepository

SERVICE_PATH = Path(__file__).resolve().parents[3] / "app" / "services" / "assessment_claim.py"
CLAIMED_AT = datetime(2026, 9, 4, 13, 0, tzinfo=UTC)
USER_A = "user-verified-a"
USER_B = "user-verified-b"
FORBIDDEN = {
    "owner_user_id",
    "claim_token",
    "claim_token_hash",
    "category_breakdown",
    "strengths",
    "material_gaps",
    "priority_actions",
    "project_recommendation",
    "criterion_breakdown",
    "cap_detail",
    "explicit_text",
    "evidence_facts",
    "source_records",
    "scoring_context",
    "storage_path",
    "assessment_result",
    "email",
    "access_token",
}


class StatusRepository:
    def __init__(self, result: ClaimWriteResult) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    async def claim_assessment(self, **kwargs: Any) -> ClaimWriteResult:
        self.calls.append(kwargs)
        return self.result


def _seed(repository: RecordingRepository, **overrides: Any) -> None:
    record = AssessmentRecord(
        assessment_id=IDENTITY.assessment_id,
        candidate_ref=IDENTITY.candidate_ref,
        track="software_engineering",
        access_state="PREVIEW",
        claim_token_hash=hash_claim_token(RAW_CLAIM),
        claimed_at=None,
        latest_run_id=IDENTITY.run_id,
        expires_at=None,
        created_at=CLAIMED_AT,
        updated_at=CLAIMED_AT,
        owner_user_id=None,
    )
    for key, value in overrides.items():
        object.__setattr__(record, key, value)
    repository.assessments[IDENTITY.assessment_id] = record


def _claim(**kwargs: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "repository": RecordingRepository(),
        "assessment_id": IDENTITY.assessment_id,
        "authenticated_user_id": USER_A,
        "claim_token": RAW_CLAIM,
        "claimed_at": CLAIMED_AT,
    }
    defaults.update(kwargs)
    return asyncio.run(claim_assessment_for_user(**defaults))


def test_valid_claim_returns_claimed_preview_without_internal_data() -> None:
    repository = RecordingRepository()
    _seed(repository)
    outcome = _claim(repository=repository)
    draft_validator("assessment_claim_response.schema.json").validate(outcome)
    assert outcome["schema_version"] == SCHEMA_VERSION
    assert outcome["state"] == "CLAIMED"
    assert outcome["access_state"] == "PREVIEW"
    assert outcome["error_code"] is None
    assert outcome["assessment_id"] == IDENTITY.assessment_id
    owned = repository.assessments[IDENTITY.assessment_id]
    assert owned.owner_user_id == USER_A
    assert owned.claim_token_hash is None
    assert owned.candidate_ref == IDENTITY.candidate_ref
    assert owned.access_state == "PREVIEW"
    assert RAW_CLAIM not in str(outcome)
    assert RAW_CLAIM not in str(repository.claim_calls)
    for key in FORBIDDEN:
        assert key not in outcome


def test_same_owner_retry_is_idempotent() -> None:
    repository = RecordingRepository()
    _seed(repository)
    first = _claim(repository=repository)
    second = _claim(repository=repository, claim_token="different-token-after-hash-cleared")
    assert first["state"] == "CLAIMED"
    assert second["state"] == "CLAIMED"
    assert claim_http_status(second) == 200
    assert repository.assessments[IDENTITY.assessment_id].owner_user_id == USER_A


def test_conflict_expired_invalid_and_missing_map_to_stable_errors() -> None:
    missing = _claim(repository=RecordingRepository())
    assert missing["error_code"] == ERROR_ASSESSMENT_NOT_FOUND
    assert claim_http_status(missing) == 404

    wrong = RecordingRepository()
    _seed(wrong)
    invalid = _claim(repository=wrong, claim_token="not-the-token")
    assert invalid["error_code"] == ERROR_CLAIM_TOKEN_INVALID
    assert claim_http_status(invalid) == 403
    assert wrong.assessments[IDENTITY.assessment_id].owner_user_id is None

    expired = RecordingRepository()
    _seed(expired, expires_at=datetime(2020, 1, 1, tzinfo=UTC))
    expired_outcome = _claim(repository=expired)
    assert expired_outcome["error_code"] == ERROR_CLAIM_EXPIRED
    assert claim_http_status(expired_outcome) == 410

    owned = RecordingRepository()
    _seed(owned, owner_user_id=USER_B, claim_token_hash=None)
    conflict = _claim(repository=owned)
    assert conflict["error_code"] == ERROR_ASSESSMENT_ALREADY_CLAIMED
    assert claim_http_status(conflict) == 409


def test_invalid_request_and_blank_principal_are_rejected() -> None:
    blank = _claim(claim_token="   ")
    assert blank["error_code"] == ERROR_INVALID_CLAIM_REQUEST
    assert claim_http_status(blank) == 422
    principal = _claim(authenticated_user_id="  ")
    assert principal["error_code"] == ERROR_AUTH_INVALID


def test_repository_failure_is_service_unavailable() -> None:
    repository = RecordingRepository()
    _seed(repository)
    repository.claim_error = RuntimeError("forced")
    outcome = _claim(repository=repository)
    assert outcome["error_code"] == ERROR_CLAIM_SERVICE_UNAVAILABLE
    assert claim_http_status(outcome) == 503
    assert claim_service_unavailable()["error_code"] == ERROR_CLAIM_SERVICE_UNAVAILABLE
    assert claim_failed_outcome(ERROR_CLAIM_TOKEN_INVALID)["state"] == "FAILED"


def test_presented_hash_is_sha256_and_raw_token_is_not_passed() -> None:
    repository = StatusRepository(
        ClaimWriteResult(
            "claimed", IDENTITY.assessment_id, claimed_at=CLAIMED_AT, access_state="PREVIEW"
        )
    )
    outcome = asyncio.run(
        claim_assessment_for_user(
            repository=repository,  # type: ignore[arg-type]
            assessment_id=IDENTITY.assessment_id,
            authenticated_user_id=USER_A,
            claim_token=RAW_CLAIM,
            claimed_at=CLAIMED_AT,
        )
    )
    assert outcome["state"] == "CLAIMED"
    assert repository.calls[0]["presented_claim_token_hash"] == hash_claim_token(RAW_CLAIM)
    assert repository.calls[0]["presented_claim_token_hash"] != RAW_CLAIM
    assert "claim_token" not in repository.calls[0]


def test_unknown_error_http_status_is_500() -> None:
    assert claim_http_status({"state": "FAILED", "error_code": "NOPE"}) == 500
    assert claim_http_status({"state": "FAILED"}) == 500
    assert claim_http_status({"state": "CLAIMED"}) == 200


def test_module_does_not_call_scoring_or_log_secrets() -> None:
    text = SERVICE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(text)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert "app.engine.scoring" not in imported
    assert "app.services.assessment_pipeline" not in imported
    assert "app.services.readiness_reporting" not in imported
    assert "score_assessment" not in text
    assert "run_assessment_pipeline" not in text
    assert "get_readiness_report" not in text
    for line in text.splitlines():
        if "logger." in line:
            lowered = line.lower()
            assert "claim_token" not in lowered
            assert "authorization" not in lowered
            assert "bearer" not in lowered
            assert "access_token" not in lowered

"""HTTP tests for POST /api/v1/assessments/{id}/claim. Fakes only; no Supabase."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.auth import AuthenticatedPrincipal, AuthServiceUnavailable
from app.core.config import get_settings
from app.core.security import require_authenticated_principal
from app.engine.schema_registry import draft_validator
from app.main import create_app
from app.repositories.records import AssessmentRecord
from app.services.anonymous_assessment import hash_claim_token
from app.services.assessment_claim import (
    ERROR_ASSESSMENT_ALREADY_CLAIMED,
    ERROR_ASSESSMENT_NOT_FOUND,
    ERROR_AUTH_INVALID,
    ERROR_AUTH_REQUIRED,
    ERROR_AUTH_SERVICE_UNAVAILABLE,
    ERROR_CLAIM_EXPIRED,
    ERROR_CLAIM_SERVICE_UNAVAILABLE,
    ERROR_CLAIM_TOKEN_INVALID,
    ERROR_INVALID_CLAIM_REQUEST,
)
from tests.integration.test_assessment_score import SCORE_PATH, _completed_request, _load
from tests.unit.services.test_anonymous_assessment import IDENTITY, RAW_CLAIM, RecordingRepository

CLAIMED_AT = datetime(2026, 9, 4, 13, 0, tzinfo=UTC)
USER_A = "user-verified-a"
USER_B = "user-verified-b"
ACCESS = "verified-access-token-not-for-storage"
CLAIM_PATH = f"/api/v1/assessments/{IDENTITY.assessment_id}/claim"
ROUTE_PATH = Path(__file__).resolve().parents[2] / "app" / "api" / "v1" / "assessments.py"
DEFAULT_PRINCIPAL = AuthenticatedPrincipal(USER_A)
FORBIDDEN = {
    "owner_user_id",
    "claim_token_hash",
    "category_breakdown",
    "strengths",
    "material_gaps",
    "priority_actions",
    "project_recommendation",
    "criterion_breakdown",
    "explicit_text",
    "evidence_facts",
    "source_records",
    "scoring_context",
    "storage_path",
    "assessment_result",
    "email",
    "access_token",
    "preview",
}


class FakeVerifier:
    def __init__(
        self,
        principal: AuthenticatedPrincipal | None = DEFAULT_PRINCIPAL,
        error: Exception | None = None,
    ) -> None:
        self.principal = principal
        self.error = error
        self.tokens: list[str] = []

    async def verify_access_token(self, access_token: str) -> AuthenticatedPrincipal | None:
        self.tokens.append(access_token)
        if self.error is not None:
            raise self.error
        return self.principal


@pytest.fixture
def app_client() -> Iterator[tuple[TestClient, Any]]:
    get_settings.cache_clear()
    application = create_app()
    with TestClient(application) as client:
        application.state.auto_bind_resources = False
        yield client, application
    get_settings.cache_clear()


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


def _bind(
    application: Any,
    *,
    repository: RecordingRepository | None = None,
    verifier: FakeVerifier | None = None,
    seed: bool = True,
    **overrides: Any,
) -> tuple[RecordingRepository, FakeVerifier]:
    repo = repository if repository is not None else RecordingRepository()
    auth = verifier if verifier is not None else FakeVerifier()
    if seed and IDENTITY.assessment_id not in repo.assessments:
        _seed(repo)
    application.state.repository = repo
    application.state.auth_verifier = auth
    application.state.claimed_at = CLAIMED_AT
    for name, value in overrides.items():
        setattr(application.state, name, value)
    return repo, auth


def _post(
    client: TestClient,
    *,
    path: str = CLAIM_PATH,
    token: str | None = ACCESS,
    body: object = None,
    authorization: str | None = None,
) -> Any:
    headers: dict[str, str] = {}
    if authorization is not None:
        headers["Authorization"] = authorization
    elif token is not None:
        headers["Authorization"] = f"Bearer {token}"
    payload = {"claim_token": RAW_CLAIM} if body is None else body
    return client.post(path, json=payload, headers=headers)


def test_valid_verified_user_claims_assessment(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    repository, verifier = _bind(application)
    response = _post(client)
    assert response.status_code == 200
    payload = response.json()
    draft_validator("assessment_claim_response.schema.json").validate(payload)
    assert payload["state"] == "CLAIMED"
    assert payload["access_state"] == "PREVIEW"
    assert payload["error_code"] is None
    assert payload["assessment_id"] == IDENTITY.assessment_id
    owned = repository.assessments[IDENTITY.assessment_id]
    assert owned.owner_user_id == USER_A
    assert owned.claim_token_hash is None
    assert owned.candidate_ref == IDENTITY.candidate_ref
    assert owned.access_state == "PREVIEW"
    assert verifier.tokens == [ACCESS]
    assert RAW_CLAIM not in str(payload)
    assert ACCESS not in str(payload)
    for key in FORBIDDEN:
        assert key not in payload


def test_missing_and_malformed_authorization_are_unauthorized(
    app_client: tuple[TestClient, Any],
) -> None:
    client, application = app_client
    _bind(application)
    missing = _post(client, token=None)
    assert missing.status_code == 401
    assert missing.json()["error_code"] == ERROR_AUTH_REQUIRED
    malformed = _post(client, authorization="Token abc")
    assert malformed.status_code == 401
    assert malformed.json()["error_code"] == ERROR_AUTH_INVALID
    empty_bearer = _post(client, authorization="Bearer")
    assert empty_bearer.status_code == 401


def test_invalid_supabase_token_is_unauthorized(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _bind(application, verifier=FakeVerifier(principal=None))
    response = _post(client)
    assert response.status_code == 401
    assert response.json()["error_code"] == ERROR_AUTH_INVALID


def test_auth_outage_is_service_unavailable(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _bind(application, verifier=FakeVerifier(error=AuthServiceUnavailable()))
    response = _post(client)
    assert response.status_code == 503
    assert response.json()["error_code"] == ERROR_AUTH_SERVICE_UNAVAILABLE


def test_body_supplied_user_id_is_ignored(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    repository, _verifier = _bind(application)
    response = _post(
        client,
        body={
            "claim_token": RAW_CLAIM,
            "user_id": USER_B,
            "owner_user_id": USER_B,
            "authenticated_user_id": USER_B,
        },
    )
    assert response.status_code == 200
    assert repository.assessments[IDENTITY.assessment_id].owner_user_id == USER_A
    assert repository.claim_calls[0]["authenticated_user_id"] == USER_A


def test_invalid_claim_body_is_unprocessable(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _bind(application)
    missing = _post(client, body={})
    assert missing.status_code == 422
    assert missing.json()["error_code"] == ERROR_INVALID_CLAIM_REQUEST
    not_object = client.post(
        CLAIM_PATH,
        json=["claim_token"],
        headers={"Authorization": f"Bearer {ACCESS}"},
    )
    assert not_object.status_code == 422
    empty = _post(client, body={"claim_token": "  "})
    assert empty.status_code == 422


def test_not_found_wrong_token_expired_and_conflict(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _bind(application, seed=False)
    missing = _post(client)
    assert missing.status_code == 404
    assert missing.json()["error_code"] == ERROR_ASSESSMENT_NOT_FOUND

    repository, _verifier = _bind(application)
    wrong = _post(client, body={"claim_token": "wrong-token"})
    assert wrong.status_code == 403
    assert wrong.json()["error_code"] == ERROR_CLAIM_TOKEN_INVALID
    assert repository.assessments[IDENTITY.assessment_id].owner_user_id is None

    expired = RecordingRepository()
    _seed(expired, expires_at=datetime(2020, 1, 1, tzinfo=UTC))
    _bind(application, repository=expired, seed=False)
    gone = _post(client)
    assert gone.status_code == 410
    assert gone.json()["error_code"] == ERROR_CLAIM_EXPIRED

    owned = RecordingRepository()
    _seed(owned, owner_user_id=USER_B, claim_token_hash=None)
    _bind(application, repository=owned, seed=False)
    conflict = _post(client)
    assert conflict.status_code == 409
    assert conflict.json()["error_code"] == ERROR_ASSESSMENT_ALREADY_CLAIMED


def test_same_user_retry_is_idempotent_success(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    repository, _verifier = _bind(application)
    first = _post(client)
    second = _post(client)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["state"] == "CLAIMED"
    assert repository.assessments[IDENTITY.assessment_id].owner_user_id == USER_A
    draft_validator("assessment_claim_response.schema.json").validate(second.json())


def test_missing_resources_and_security_stub(
    app_client: tuple[TestClient, Any],
) -> None:
    client, _application = app_client
    response = _post(client)
    assert response.status_code == 503
    assert response.json()["error_code"] == ERROR_CLAIM_SERVICE_UNAVAILABLE
    with pytest.raises(NotImplementedError):
        import asyncio

        asyncio.run(require_authenticated_principal())


def test_score_endpoint_is_unchanged(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _bind(application)
    document = _load("c01_se_full_score.json")
    response = client.post(SCORE_PATH, json=_completed_request(document))
    assert response.status_code == 200
    assert response.json()["state"] == "COMPLETED"
    assert response.json().get("schema_version") != "assessment.claim.v1"


def test_route_does_not_log_tokens() -> None:
    text = ROUTE_PATH.read_text(encoding="utf-8")
    for line in text.splitlines():
        if "logger." in line:
            lowered = line.lower()
            assert "claim_token" not in lowered
            assert "authorization" not in lowered
            assert "bearer" not in lowered
            assert "access_token" not in lowered
    tree = ast.parse(text)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert "app.engine.scoring" not in imported
    assert "app.services.assessment_pipeline" not in imported
    assert "app.services.readiness_reporting" not in imported

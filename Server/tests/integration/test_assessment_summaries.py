"""HTTP tests for GET /api/v1/assessments. Fakes only; no Supabase."""

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
from app.engine.schema_registry import draft_validator
from app.main import create_app
from app.repositories.records import AssessmentRecord, AssessmentRunRecord, PaymentRecord
from app.services.assessment_summaries import (
    ERROR_AUTH_INVALID,
    ERROR_AUTH_REQUIRED,
    ERROR_AUTH_SERVICE_UNAVAILABLE,
    ERROR_SUMMARIES_SERVICE_UNAVAILABLE,
    SCHEMA_VERSION,
)
from tests.integration.test_assessment_claim import FakeVerifier
from tests.integration.test_assessment_score import SCORE_PATH, _completed_request, _load
from tests.unit.services.test_anonymous_assessment import IDENTITY, RecordingRepository
from tests.unit.services.test_assessment_report import WRITE_METHODS, _WriteTrackingRepository

LIST_PATH = "/api/v1/assessments"
ROUTE_PATH = Path(__file__).resolve().parents[2] / "app" / "api" / "v1" / "assessments.py"
OLDER = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
NEWER = datetime(2026, 9, 5, 10, 0, tzinfo=UTC)
PAID_AT = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)
USER_A = "user-verified-a"
USER_B = "user-verified-b"
ACCESS = "verified-access-token-not-for-storage"
DEFAULT_PRINCIPAL = AuthenticatedPrincipal(USER_A)
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
    "preview",
    "authorization_url",
    "provider_reference",
    "provider_transaction_id",
}


@pytest.fixture
def app_client() -> Iterator[tuple[TestClient, Any]]:
    get_settings.cache_clear()
    application = create_app()
    with TestClient(application) as client:
        application.state.auto_bind_resources = False
        yield client, application
    get_settings.cache_clear()


def _run(
    assessment_id: str,
    run_id: str,
    *,
    assessed_at: datetime,
    state: str = "COMPLETED",
    result: dict[str, Any] | None = None,
    track: str = "software_engineering",
) -> AssessmentRunRecord:
    return AssessmentRunRecord(
        run_id=run_id,
        assessment_id=assessment_id,
        state=state,
        error_code=None,
        pipeline_version="assessment.pipeline.v1",
        contract_version="1.2.0",
        rubric_version="V2",
        track=track,
        assessment_input={"track": track},
        scoring_context=None,
        assessment_result=result,
        review_flags=[],
        stages=["score"],
        assessed_at=assessed_at,
        created_at=assessed_at,
        source_records=[],
        evidence_facts=[],
        document=None,
    )


def _seed(
    repository: RecordingRepository,
    *,
    assessment_id: str,
    owner_user_id: str | None,
    access_state: str,
    assessed_at: datetime,
    run_state: str = "COMPLETED",
    result: dict[str, Any] | None = None,
    track: str = "software_engineering",
) -> None:
    run_id = f"run-{assessment_id}"
    repository.assessments[assessment_id] = AssessmentRecord(
        assessment_id=assessment_id,
        candidate_ref=IDENTITY.candidate_ref,
        track=track,
        access_state=access_state,  # type: ignore[arg-type]
        claim_token_hash="hash-must-never-appear",
        claimed_at=assessed_at,
        latest_run_id=run_id,
        expires_at=None,
        created_at=assessed_at,
        updated_at=assessed_at,
        owner_user_id=owner_user_id,
    )
    repository.runs[run_id] = _run(
        assessment_id,
        run_id,
        assessed_at=assessed_at,
        state=run_state,
        result=result,
        track=track,
    )


def _seed_payment(
    repository: RecordingRepository,
    *,
    assessment_id: str,
    owner_user_id: str,
    paid_at: datetime,
) -> None:
    payment_id = f"pay-{assessment_id}"
    repository.payments[payment_id] = PaymentRecord(
        payment_id=payment_id,
        assessment_id=assessment_id,
        owner_user_id=owner_user_id,
        product_id="readiness_report_v1",
        billing_model="one_time",
        provider="paystack",
        provider_reference=f"psk-{assessment_id}",
        provider_transaction_id="txn-secret",
        amount_minor=15900,
        currency="ZAR",
        status="SUCCEEDED",
        authorization_url="https://paystack.invalid/checkout",
        paid_at=paid_at,
        created_at=paid_at,
        updated_at=paid_at,
    )


def _bind(
    application: Any,
    *,
    repository: RecordingRepository | None = None,
    verifier: FakeVerifier | None = None,
) -> tuple[RecordingRepository, FakeVerifier]:
    repo = repository if repository is not None else _WriteTrackingRepository()
    auth = verifier if verifier is not None else FakeVerifier(DEFAULT_PRINCIPAL)
    application.state.repository = repo
    application.state.auth_verifier = auth
    return repo, auth


def _get(
    client: TestClient,
    *,
    token: str | None = ACCESS,
    authorization: str | None = None,
    params: dict[str, Any] | None = None,
    path: str = LIST_PATH,
) -> Any:
    headers: dict[str, str] = {}
    if authorization is not None:
        headers["Authorization"] = authorization
    elif token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return client.get(path, headers=headers, params=params)


def _assert_safe(payload: dict[str, Any]) -> None:
    draft_validator("assessment_summaries.schema.json").validate(payload)
    for key in FORBIDDEN:
        assert key not in payload
    for item in payload.get("items", []):
        for key in FORBIDDEN:
            assert key not in item
    blob = str(payload)
    assert ACCESS not in blob
    assert "hash-must-never-appear" not in blob
    assert "paystack.invalid" not in blob
    assert "txn-secret" not in blob


def test_unauthenticated_requests_are_unauthorized(
    app_client: tuple[TestClient, Any],
) -> None:
    client, application = app_client
    _bind(application)
    missing = _get(client, token=None)
    assert missing.status_code == 401
    assert missing.json()["error_code"] == ERROR_AUTH_REQUIRED
    _assert_safe(missing.json())
    malformed = _get(client, authorization="Token abc")
    assert malformed.status_code == 401
    assert malformed.json()["error_code"] == ERROR_AUTH_INVALID
    empty_bearer = _get(client, authorization="Bearer")
    assert empty_bearer.status_code == 401


def test_invalid_token_is_unauthorized(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _bind(application, verifier=FakeVerifier(principal=None))
    response = _get(client)
    assert response.status_code == 401
    assert response.json()["error_code"] == ERROR_AUTH_INVALID


def test_auth_outage_is_service_unavailable(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _bind(application, verifier=FakeVerifier(error=AuthServiceUnavailable()))
    response = _get(client)
    assert response.status_code == 503
    assert response.json()["error_code"] == ERROR_AUTH_SERVICE_UNAVAILABLE


def test_unexpected_auth_error_is_service_unavailable(
    app_client: tuple[TestClient, Any],
) -> None:
    client, application = app_client
    _bind(application, verifier=FakeVerifier(error=RuntimeError("forced")))
    response = _get(client)
    assert response.status_code == 503
    assert response.json()["error_code"] == ERROR_AUTH_SERVICE_UNAVAILABLE


def test_empty_principal_subject_is_unauthorized(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _bind(application, verifier=FakeVerifier(principal=AuthenticatedPrincipal("")))
    response = _get(client)
    assert response.status_code == 401
    assert response.json()["error_code"] == ERROR_AUTH_INVALID


def test_owner_receives_owned_preview_and_unlocked_summaries(
    app_client: tuple[TestClient, Any],
) -> None:
    client, application = app_client
    repository, verifier = _bind(application)
    _seed(
        repository,
        assessment_id="owned-preview",
        owner_user_id=USER_A,
        access_state="PREVIEW",
        assessed_at=OLDER,
        result={"final_score": 59, "band": "foundation_visible"},
    )
    _seed(
        repository,
        assessment_id="owned-unlocked",
        owner_user_id=USER_A,
        access_state="UNLOCKED",
        assessed_at=NEWER,
        result={"final_score": 82, "band": "strong_application_evidence"},
    )
    _seed_payment(repository, assessment_id="owned-unlocked", owner_user_id=USER_A, paid_at=PAID_AT)
    _seed(
        repository,
        assessment_id="other-user",
        owner_user_id=USER_B,
        access_state="UNLOCKED",
        assessed_at=NEWER,
        result={"final_score": 91, "band": "strong_application_evidence"},
    )
    _seed(
        repository,
        assessment_id="unowned-anonymous",
        owner_user_id=None,
        access_state="PREVIEW",
        assessed_at=NEWER,
        result={"final_score": 12, "band": "limited_application_evidence"},
    )
    response = _get(client, params={"user_id": USER_B, "owner_user_id": USER_B})
    assert response.status_code == 200
    payload = response.json()
    _assert_safe(payload)
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["state"] == "LISTED"
    ids = [item["assessment_id"] for item in payload["items"]]
    assert ids == ["owned-unlocked", "owned-preview"]
    by_id = {item["assessment_id"]: item for item in payload["items"]}
    assert by_id["owned-preview"]["access_state"] == "PREVIEW"
    assert by_id["owned-preview"]["unlocked_at"] is None
    assert by_id["owned-unlocked"]["access_state"] == "UNLOCKED"
    assert by_id["owned-unlocked"]["unlocked_at"] == "2026-09-06T12:00:00Z"
    assert by_id["owned-unlocked"]["final_score"] == 82
    assert verifier.tokens == [ACCESS]
    assert isinstance(repository, _WriteTrackingRepository)
    assert repository.write_names == []


def test_mixed_owners_never_leak_across_boundaries(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    repository, _verifier = _bind(application)
    _seed(
        repository,
        assessment_id="a-one",
        owner_user_id=USER_A,
        access_state="PREVIEW",
        assessed_at=NEWER,
        result={"final_score": 40, "band": "limited_application_evidence"},
    )
    _seed(
        repository,
        assessment_id="b-one",
        owner_user_id=USER_B,
        access_state="UNLOCKED",
        assessed_at=NEWER,
        result={"final_score": 88, "band": "strong_application_evidence"},
    )
    owner_a = _get(client)
    assert [item["assessment_id"] for item in owner_a.json()["items"]] == ["a-one"]
    application.state.auth_verifier = FakeVerifier(AuthenticatedPrincipal(USER_B))
    owner_b = _get(client, token="other-token")
    assert [item["assessment_id"] for item in owner_b.json()["items"]] == ["b-one"]


def test_score_and_band_absent_when_run_is_not_completed(
    app_client: tuple[TestClient, Any],
) -> None:
    client, application = app_client
    repository, _verifier = _bind(application)
    _seed(
        repository,
        assessment_id="not-scored",
        owner_user_id=USER_A,
        access_state="PREVIEW",
        assessed_at=NEWER,
        run_state="REVIEW_REQUIRED",
        result={"final_score": 70, "band": "developing_application_readiness"},
    )
    payload = _get(client).json()
    _assert_safe(payload)
    assert payload["items"][0]["final_score"] is None
    assert payload["items"][0]["band"] is None


def test_empty_owned_list_is_success(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _bind(application)
    response = _get(client)
    assert response.status_code == 200
    payload = response.json()
    _assert_safe(payload)
    assert payload["items"] == []
    assert payload["has_more"] is False
    assert payload["limit"] == 50
    assert payload["offset"] == 0


def test_newest_first_ordering_is_deterministic(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    repository, _verifier = _bind(application)
    _seed(
        repository,
        assessment_id="assessment-a",
        owner_user_id=USER_A,
        access_state="PREVIEW",
        assessed_at=NEWER,
        result={"final_score": 1, "band": "limited_application_evidence"},
    )
    _seed(
        repository,
        assessment_id="assessment-c",
        owner_user_id=USER_A,
        access_state="PREVIEW",
        assessed_at=OLDER,
        result={"final_score": 2, "band": "limited_application_evidence"},
    )
    _seed(
        repository,
        assessment_id="assessment-b",
        owner_user_id=USER_A,
        access_state="PREVIEW",
        assessed_at=NEWER,
        result={"final_score": 3, "band": "limited_application_evidence"},
    )
    ids = [item["assessment_id"] for item in _get(client).json()["items"]]
    assert ids == ["assessment-b", "assessment-a", "assessment-c"]


def test_limit_is_clamped_and_has_more_is_explicit(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    repository, _verifier = _bind(application)
    for index, stamp in enumerate((NEWER, OLDER)):
        _seed(
            repository,
            assessment_id=f"owned-{index}",
            owner_user_id=USER_A,
            access_state="PREVIEW",
            assessed_at=stamp,
            result={"final_score": 10 + index, "band": "limited_application_evidence"},
        )
    payload = _get(client, params={"limit": "1", "offset": "0"}).json()
    assert payload["limit"] == 1
    assert payload["has_more"] is True
    assert len(payload["items"]) == 1
    overflow = _get(client, params={"limit": "999", "offset": "-8"}).json()
    assert overflow["limit"] == 50
    assert overflow["offset"] == 0
    invalid = _get(client, params={"limit": "abc", "offset": " "}).json()
    assert invalid["limit"] == 50
    assert invalid["offset"] == 0


def test_missing_resources_are_unavailable(app_client: tuple[TestClient, Any]) -> None:
    client, _application = app_client
    response = _get(client)
    assert response.status_code == 503
    assert response.json()["error_code"] == ERROR_SUMMARIES_SERVICE_UNAVAILABLE


def test_repository_error_is_unavailable(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    repository, _verifier = _bind(application)
    repository.list_summaries_error = RuntimeError("forced")
    response = _get(client)
    assert response.status_code == 503
    assert response.json()["error_code"] == ERROR_SUMMARIES_SERVICE_UNAVAILABLE


def test_score_endpoint_is_unchanged(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _bind(application)
    document = _load("c01_se_full_score.json")
    response = client.post(SCORE_PATH, json=_completed_request(document))
    assert response.status_code == 200
    assert response.json()["state"] == "COMPLETED"
    assert response.json().get("schema_version") != SCHEMA_VERSION


def test_listing_does_not_call_write_methods(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    repository, _verifier = _bind(application)
    _seed(
        repository,
        assessment_id="owned-preview",
        owner_user_id=USER_A,
        access_state="PREVIEW",
        assessed_at=NEWER,
        result={"final_score": 59, "band": "foundation_visible"},
    )
    _get(client)
    assert isinstance(repository, _WriteTrackingRepository)
    assert repository.write_names == []
    for name in WRITE_METHODS:
        assert name not in repository.write_names


def test_route_does_not_log_tokens_or_import_scoring() -> None:
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

"""HTTP tests for GET /api/v1/assessments/{id}/report. Fakes only; no live Auth."""

from __future__ import annotations

import ast
import json
from collections.abc import Iterator
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.auth import AuthenticatedPrincipal, AuthServiceUnavailable
from app.core.config import get_settings
from app.core.security import require_authenticated_principal
from app.engine.reporting.outcomes import REPORT_SCHEMA_VERSION
from app.engine.schema_registry import draft_validator
from app.main import create_app
from app.repositories.records import AssessmentRecord, AssessmentRunRecord
from app.services.assessment_report import (
    ERROR_ASSESSMENT_NOT_COMPLETED,
    ERROR_ASSESSMENT_NOT_FOUND,
    ERROR_ASSESSMENT_NOT_OWNED,
    ERROR_AUTH_INVALID,
    ERROR_AUTH_REQUIRED,
    ERROR_AUTH_SERVICE_UNAVAILABLE,
    ERROR_REPORT_BUILD_FAILED,
    ERROR_REPORT_LOCKED,
    ERROR_REPORT_SERVICE_UNAVAILABLE,
)
from tests.integration.test_anonymous_assessment import ANON_PATH
from tests.integration.test_assessment_claim import FakeVerifier
from tests.integration.test_assessment_score import SCORE_PATH, _completed_request, _load
from tests.integration.test_payment_checkout import FakePaymentProvider
from tests.unit.engine.test_readiness_report import _golden
from tests.unit.services.test_anonymous_assessment import IDENTITY, RecordingRepository
from tests.unit.services.test_assessment_report import WRITE_METHODS, _WriteTrackingRepository

ASSESSED_AT = datetime(2026, 9, 2, 8, 0, tzinfo=UTC)
USER_A = "user-verified-a"
USER_B = "user-verified-b"
ACCESS = "verified-access-token-not-for-storage"
REPORT_PATH = f"/api/v1/assessments/{IDENTITY.assessment_id}/report"
ROUTE_PATH = Path(__file__).resolve().parents[2] / "app" / "api" / "v1" / "reports.py"
PAID_KEYS = {
    "category_breakdown",
    "strengths",
    "material_gaps",
    "priority_actions",
    "project_recommendation",
    "criterion_breakdown",
    "score_summary",
}
FORBIDDEN = PAID_KEYS | {
    "owner_user_id",
    "claim_token",
    "claim_token_hash",
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
}


@pytest.fixture
def app_client() -> Iterator[tuple[TestClient, Any]]:
    get_settings.cache_clear()
    application = create_app()
    with TestClient(application) as client:
        application.state.auto_bind_resources = False
        yield client, application
    get_settings.cache_clear()


def _completed_result() -> dict[str, Any]:
    result = deepcopy(_golden("c01_se_full_score.json"))
    result["assessment_id"] = IDENTITY.assessment_id
    result["run_id"] = IDENTITY.run_id
    return result


def _run_record(
    result: dict[str, Any] | None,
    *,
    state: str = "COMPLETED",
    error_code: str | None = None,
) -> AssessmentRunRecord:
    return AssessmentRunRecord(
        run_id=IDENTITY.run_id,
        assessment_id=IDENTITY.assessment_id,
        state=state,
        error_code=error_code,
        pipeline_version="assessment.pipeline.v1",
        contract_version="1.2.0",
        rubric_version="V2",
        track="software_engineering",
        assessment_input={"track": "software_engineering"},
        scoring_context=None,
        assessment_result=result,
        review_flags=[],
        stages=["score"],
        assessed_at=ASSESSED_AT,
        created_at=ASSESSED_AT,
        source_records=[],
        evidence_facts=[],
        document=None,
    )


def _seed(
    repository: RecordingRepository,
    *,
    owner_user_id: str | None = USER_A,
    access_state: str = "UNLOCKED",
    result: dict[str, Any] | None = None,
    run: AssessmentRunRecord | None = None,
) -> None:
    repository.assessments[IDENTITY.assessment_id] = AssessmentRecord(
        assessment_id=IDENTITY.assessment_id,
        candidate_ref=IDENTITY.candidate_ref,
        track="software_engineering",
        access_state=access_state,  # type: ignore[arg-type]
        claim_token_hash=None,
        claimed_at=ASSESSED_AT,
        latest_run_id=IDENTITY.run_id,
        expires_at=None,
        created_at=ASSESSED_AT,
        updated_at=ASSESSED_AT,
        owner_user_id=owner_user_id,
    )
    repository.runs[IDENTITY.run_id] = run if run is not None else _run_record(result)


def _bind(
    application: Any,
    *,
    repository: RecordingRepository | None = None,
    verifier: FakeVerifier | None = None,
    provider: FakePaymentProvider | None = None,
    seed: bool = True,
    access_state: str = "UNLOCKED",
    result: dict[str, Any] | None = None,
    run: AssessmentRunRecord | None = None,
    owner_user_id: str | None = USER_A,
) -> tuple[_WriteTrackingRepository, FakeVerifier, FakePaymentProvider]:
    repo = repository if repository is not None else _WriteTrackingRepository()
    auth = verifier if verifier is not None else FakeVerifier(AuthenticatedPrincipal(USER_A))
    pay = provider if provider is not None else FakePaymentProvider()
    if seed and IDENTITY.assessment_id not in repo.assessments:
        _seed(
            repo,
            owner_user_id=owner_user_id,
            access_state=access_state,
            result=result if result is not None else _completed_result(),
            run=run,
        )
    application.state.repository = repo
    application.state.auth_verifier = auth
    application.state.payment_provider = pay
    return repo, auth, pay  # type: ignore[return-value]


def _get(
    client: TestClient,
    *,
    path: str = REPORT_PATH,
    token: str | None = ACCESS,
    authorization: str | None = None,
) -> Any:
    headers: dict[str, str] = {}
    if authorization is not None:
        headers["Authorization"] = authorization
    elif token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return client.get(path, headers=headers)


def _assert_denied(response: Any, status_code: int, error_code: str) -> None:
    assert response.status_code == status_code
    payload = response.json()
    draft_validator("assessment_report_error.schema.json").validate(payload)
    assert payload["error_code"] == error_code
    assert payload["schema_version"] != REPORT_SCHEMA_VERSION
    for key in FORBIDDEN:
        assert key not in payload
    serialized = json.dumps(payload)
    assert ACCESS not in serialized
    assert "sk_test" not in serialized
    assert "postgresql://" not in serialized


def test_unlocked_verified_owner_receives_full_report(
    app_client: tuple[TestClient, Any],
) -> None:
    client, application = app_client
    repository, verifier, provider = _bind(application)
    response = _get(client)
    assert response.status_code == 200
    payload = response.json()
    draft_validator("readiness_report.schema.json").validate(payload)
    assert payload["schema_version"] == REPORT_SCHEMA_VERSION
    assert payload["assessment_id"] == IDENTITY.assessment_id
    assert payload["run_id"] == IDENTITY.run_id
    assert verifier.tokens == [ACCESS]
    assert provider.initialize_calls == []
    assert provider.verify_calls == []
    assert repository.write_names == []
    assert repository.assessments[IDENTITY.assessment_id].access_state == "UNLOCKED"


def test_repeated_get_is_readonly_and_idempotent(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    repository, _auth, provider = _bind(application)
    first = _get(client)
    second = _get(client)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert repository.write_names == []
    assert provider.initialize_calls == []
    assert repository.assessments[IDENTITY.assessment_id].access_state == "UNLOCKED"


def test_missing_malformed_and_invalid_auth_are_401(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    repository, _auth, provider = _bind(application)
    missing = _get(client, token=None)
    malformed = _get(client, authorization="Token not-bearer")
    blank = _get(client, authorization="Bearer")
    _bind(
        application,
        repository=repository,
        verifier=FakeVerifier(None),
        provider=provider,
        seed=False,
    )
    invalid = _get(client)
    _assert_denied(missing, 401, ERROR_AUTH_REQUIRED)
    _assert_denied(malformed, 401, ERROR_AUTH_INVALID)
    _assert_denied(blank, 401, ERROR_AUTH_INVALID)
    _assert_denied(invalid, 401, ERROR_AUTH_INVALID)
    assert provider.initialize_calls == []
    assert repository.write_names == []


def test_auth_provider_unavailable_is_503(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _bind(application, verifier=FakeVerifier(error=AuthServiceUnavailable()))
    response = _get(client)
    _assert_denied(response, 503, ERROR_AUTH_SERVICE_UNAVAILABLE)


def test_auth_verifier_crash_is_503(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _bind(application, verifier=FakeVerifier(error=RuntimeError("verifier crashed")))
    response = _get(client)
    _assert_denied(response, 503, ERROR_AUTH_SERVICE_UNAVAILABLE)
    assert "verifier crashed" not in response.text


def test_missing_assessment_is_404(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    repository, _auth, provider = _bind(application, seed=False)
    response = _get(client)
    _assert_denied(response, 404, ERROR_ASSESSMENT_NOT_FOUND)
    assert repository.write_names == []
    assert provider.initialize_calls == []


def test_wrong_owner_is_403_without_report_fields(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    repository, _auth, provider = _bind(
        application,
        verifier=FakeVerifier(AuthenticatedPrincipal(USER_B)),
    )
    response = _get(client)
    _assert_denied(response, 403, ERROR_ASSESSMENT_NOT_OWNED)
    assert repository.write_names == []
    assert provider.initialize_calls == []
    assert repository.assessments[IDENTITY.assessment_id].access_state == "UNLOCKED"


def test_preview_owner_is_402_locked(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    calls: list[str] = []

    async def boom(**_kwargs: Any) -> dict[str, Any]:
        calls.append("load")
        raise AssertionError("locked assessments must not assemble a report")

    repository, _auth, provider = _bind(application, access_state="PREVIEW")
    application.state.load_report = boom
    response = _get(client)
    _assert_denied(response, 402, ERROR_REPORT_LOCKED)
    assert calls == []
    assert repository.write_names == []
    assert provider.initialize_calls == []
    assert repository.assessments[IDENTITY.assessment_id].access_state == "PREVIEW"


def test_non_completed_run_is_409(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _bind(
        application,
        run=_run_record(None, state="REVIEW_REQUIRED", error_code="REVIEW_REQUIRED"),
    )
    response = _get(client)
    _assert_denied(response, 409, ERROR_ASSESSMENT_NOT_COMPLETED)


def test_missing_and_invalid_result_are_500(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _bind(application, run=_run_record(None, state="COMPLETED"))
    missing = _get(client)
    _assert_denied(missing, 500, ERROR_REPORT_BUILD_FAILED)

    invalid = deepcopy(_completed_result())
    invalid.pop("criterion_results")
    _bind(application, result=invalid)
    broken = _get(client)
    _assert_denied(broken, 500, ERROR_REPORT_BUILD_FAILED)


def test_package_m_failure_is_safe_500(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _bind(application)

    async def failed(**_kwargs: Any) -> dict[str, Any]:
        return {"state": "FAILED", "error_code": "REPORT_RULESET_INVALID", "report": None}

    application.state.load_report = failed
    response = _get(client)
    _assert_denied(response, 500, ERROR_REPORT_BUILD_FAILED)


def test_missing_resources_are_503(app_client: tuple[TestClient, Any]) -> None:
    client, _application = app_client
    response = _get(client)
    _assert_denied(response, 503, ERROR_REPORT_SERVICE_UNAVAILABLE)
    with pytest.raises(NotImplementedError):
        import asyncio

        asyncio.run(require_authenticated_principal())


def test_delivery_exception_is_503(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _bind(application)

    async def boom(**_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("delivery exploded")

    import app.api.v1.reports as reports_api

    original = reports_api.deliver_unlocked_readiness_report
    reports_api.deliver_unlocked_readiness_report = boom  # type: ignore[assignment]
    try:
        response = _get(client)
    finally:
        reports_api.deliver_unlocked_readiness_report = original
    _assert_denied(response, 503, ERROR_REPORT_SERVICE_UNAVAILABLE)
    assert "delivery exploded" not in response.text


def test_anonymous_preview_and_score_routes_remain(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _bind(application)
    reports_collection = client.get("/api/v1/reports/assessment-1")
    assert reports_collection.status_code == 404
    document = _load("c01_se_full_score.json")
    scored = client.post(SCORE_PATH, json=_completed_request(document))
    assert scored.status_code == 200
    assert scored.json()["state"] == "COMPLETED"
    assert ANON_PATH == "/api/v1/assessments"


def test_route_does_not_invoke_scoring_package_k_or_paystack() -> None:
    text = ROUTE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(text)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    assert "app.engine.scoring" not in imported
    assert "app.services.assessment_pipeline" not in imported
    assert "app.commerce.paystack" not in imported
    assert "app.services.assessment_payment" not in imported
    assert "app.services.assessment_claim" not in imported
    for name in WRITE_METHODS:
        assert name not in text
    assert "claim_token" not in text
    for line in text.splitlines():
        if "logger." in line:
            lowered = line.lower()
            assert "authorization" not in lowered
            assert "bearer" not in lowered
            assert "access_token" not in lowered

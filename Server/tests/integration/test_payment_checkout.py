"""HTTP tests for POST /api/v1/assessments/{id}/payment. Fakes only."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.commerce.errors import PaymentProviderRejected, PaymentProviderUnavailable
from app.commerce.provider import PaymentCheckout, VerifiedPayment
from app.core.auth import AuthenticatedPrincipal, AuthServiceUnavailable
from app.core.config import get_settings
from app.engine.schema_registry import draft_validator
from app.main import create_app
from app.repositories.records import AssessmentRecord, AssessmentRunRecord, PaymentRecord
from tests.integration.test_assessment_claim import FakeVerifier
from tests.unit.services.test_anonymous_assessment import IDENTITY, RecordingRepository

CLAIMED_AT = datetime(2026, 9, 4, 13, 0, tzinfo=UTC)
USER_A = "user-verified-a"
USER_B = "user-verified-b"
EMAIL = "owner@example.invalid"
ACCESS = "verified-access-token-not-for-storage"
PAYMENT_PATH = f"/api/v1/assessments/{IDENTITY.assessment_id}/payment"
AUTH_URL = "https://checkout.paystack.com/fake-auth"
PAYMENT_ID = "pay_fixed_test_id"
REFERENCE = "psk_fixed_test_reference"
SCHEMA = draft_validator("payment_checkout_response.schema.json")
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
    "access_code",
}


class FakePaymentProvider:
    def __init__(self) -> None:
        self.initialize_calls: list[dict[str, Any]] = []
        self.verify_calls: list[str] = []
        self.initialize_error: Exception | None = None
        self.verify_error: Exception | None = None
        self.checkout = PaymentCheckout(reference=REFERENCE, authorization_url=AUTH_URL)
        self.verified = VerifiedPayment(
            reference=REFERENCE,
            provider_transaction_id="9001",
            amount_minor=15900,
            currency="ZAR",
            paid_at=datetime(2026, 9, 8, 9, 0, tzinfo=UTC),
            status="success",
        )
        self.valid_signature = True

    async def initialize_transaction(
        self,
        *,
        email: str,
        amount_minor: int,
        currency: str,
        reference: str,
        callback_url: str | None = None,
    ) -> PaymentCheckout:
        self.initialize_calls.append(
            {
                "email": email,
                "amount_minor": amount_minor,
                "currency": currency,
                "reference": reference,
                "callback_url": callback_url,
            }
        )
        if self.initialize_error is not None:
            raise self.initialize_error
        return PaymentCheckout(reference=reference, authorization_url=AUTH_URL)

    async def verify_transaction(self, *, reference: str) -> VerifiedPayment:
        self.verify_calls.append(reference)
        if self.verify_error is not None:
            raise self.verify_error
        return self.verified

    def webhook_signature_is_valid(self, body: bytes, signature: str | None) -> bool:
        return self.valid_signature and bool(signature)


@pytest.fixture
def app_client() -> Iterator[tuple[TestClient, Any]]:
    get_settings.cache_clear()
    application = create_app()
    with TestClient(application) as client:
        application.state.auto_bind_resources = False
        yield client, application
    get_settings.cache_clear()


def _completed_run() -> AssessmentRunRecord:
    return AssessmentRunRecord(
        run_id=IDENTITY.run_id,
        assessment_id=IDENTITY.assessment_id,
        state="COMPLETED",
        error_code=None,
        pipeline_version="assessment.pipeline.v1",
        contract_version="1.2.0",
        rubric_version="V2",
        track="software_engineering",
        assessment_input={"track": "software_engineering"},
        scoring_context={"track": "software_engineering"},
        assessment_result={"overall_band": "developing"},
        review_flags=[],
        stages=["score"],
        assessed_at=CLAIMED_AT,
        created_at=CLAIMED_AT,
        source_records=[],
        evidence_facts=[],
        document=None,
    )


def _seed(repository: RecordingRepository, **overrides: Any) -> None:
    record = AssessmentRecord(
        assessment_id=IDENTITY.assessment_id,
        candidate_ref=IDENTITY.candidate_ref,
        track="software_engineering",
        access_state="PREVIEW",
        claim_token_hash=None,
        claimed_at=CLAIMED_AT,
        latest_run_id=IDENTITY.run_id,
        expires_at=None,
        created_at=CLAIMED_AT,
        updated_at=CLAIMED_AT,
        owner_user_id=USER_A,
    )
    for key, value in overrides.items():
        object.__setattr__(record, key, value)
    repository.assessments[IDENTITY.assessment_id] = record
    repository.runs[IDENTITY.run_id] = _completed_run()


def _bind(
    application: Any,
    *,
    repository: RecordingRepository | None = None,
    verifier: FakeVerifier | None = None,
    provider: FakePaymentProvider | None = None,
    seed: bool = True,
    email: str | None = EMAIL,
) -> tuple[RecordingRepository, FakeVerifier, FakePaymentProvider]:
    repo = repository if repository is not None else RecordingRepository()
    auth = (
        verifier
        if verifier is not None
        else FakeVerifier(AuthenticatedPrincipal(USER_A, email=email))
    )
    pay = provider if provider is not None else FakePaymentProvider()
    if seed and IDENTITY.assessment_id not in repo.assessments:
        _seed(repo)
    application.state.repository = repo
    application.state.auth_verifier = auth
    application.state.payment_provider = pay
    application.state.payment_id_factory = lambda: PAYMENT_ID
    application.state.payment_reference_factory = lambda: REFERENCE
    return repo, auth, pay


def _assert_safe(payload: dict[str, Any]) -> None:
    SCHEMA.validate(payload)
    serialized = json.dumps(payload)
    for key in FORBIDDEN:
        assert key not in payload
    assert EMAIL not in serialized
    assert "sk_test" not in serialized
    assert "access_code" not in serialized


def test_verified_owner_initializes_checkout(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _repo, _auth, provider = _bind(application)
    response = client.post(PAYMENT_PATH, headers={"Authorization": f"Bearer {ACCESS}"})
    assert response.status_code == 200
    payload = response.json()
    _assert_safe(payload)
    assert payload["state"] == "PAYMENT_INITIALIZED"
    assert payload["amount_minor"] == 15900
    assert payload["currency"] == "ZAR"
    assert payload["provider"] == "paystack"
    assert payload["authorization_url"] == AUTH_URL
    assert payload["provider_reference"] == REFERENCE
    assert payload["access_state"] == "PREVIEW"
    assert len(provider.initialize_calls) == 1
    assert provider.initialize_calls[0]["email"] == EMAIL
    assert provider.initialize_calls[0]["amount_minor"] == 15900
    assert provider.initialize_calls[0]["currency"] == "ZAR"


def test_missing_and_invalid_auth_are_401(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _bind(application)
    missing = client.post(PAYMENT_PATH)
    invalid = client.post(PAYMENT_PATH, headers={"Authorization": "Bearer"})
    assert missing.status_code == 401
    assert missing.json()["error_code"] == "AUTH_REQUIRED"
    assert invalid.status_code == 401
    assert invalid.json()["error_code"] == "AUTH_INVALID"


def test_wrong_owner_is_403(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _bind(application, verifier=FakeVerifier(AuthenticatedPrincipal(USER_B, email=EMAIL)))
    response = client.post(PAYMENT_PATH, headers={"Authorization": f"Bearer {ACCESS}"})
    assert response.status_code == 403
    assert response.json()["error_code"] == "ASSESSMENT_NOT_OWNED"


def test_missing_assessment_is_404(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _bind(application, seed=False)
    response = client.post(PAYMENT_PATH, headers={"Authorization": f"Bearer {ACCESS}"})
    assert response.status_code == 404
    assert response.json()["error_code"] == "ASSESSMENT_NOT_FOUND"


def test_non_completed_is_409(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    repo, _auth, provider = _bind(application)
    run = repo.runs[IDENTITY.run_id]
    repo.runs[IDENTITY.run_id] = AssessmentRunRecord(**{**run.__dict__, "state": "REVIEW_REQUIRED"})
    response = client.post(PAYMENT_PATH, headers={"Authorization": f"Bearer {ACCESS}"})
    assert response.status_code == 409
    assert response.json()["error_code"] == "ASSESSMENT_NOT_COMPLETED"
    assert provider.initialize_calls == []


def test_missing_verified_email_is_422(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _bind(application, email=None)
    response = client.post(PAYMENT_PATH, headers={"Authorization": f"Bearer {ACCESS}"})
    assert response.status_code == 422
    assert response.json()["error_code"] == "PAYMENT_EMAIL_REQUIRED"


def test_already_unlocked_is_idempotent_without_paystack(
    app_client: tuple[TestClient, Any],
) -> None:
    client, application = app_client
    repo, _auth, provider = _bind(application)
    _seed(repo, access_state="UNLOCKED")
    response = client.post(PAYMENT_PATH, headers={"Authorization": f"Bearer {ACCESS}"})
    assert response.status_code == 200
    payload = response.json()
    _assert_safe(payload)
    assert payload["state"] == "ALREADY_UNLOCKED"
    assert payload["access_state"] == "UNLOCKED"
    assert provider.initialize_calls == []


def test_existing_initialized_returns_same_checkout(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    repo, _auth, provider = _bind(application)
    existing = PaymentRecord(
        payment_id=PAYMENT_ID,
        assessment_id=IDENTITY.assessment_id,
        owner_user_id=USER_A,
        product_id="readiness_report_v1",
        billing_model="one_time",
        provider="paystack",
        provider_reference=REFERENCE,
        provider_transaction_id=None,
        amount_minor=15900,
        currency="ZAR",
        status="INITIALIZED",
        authorization_url=AUTH_URL,
        paid_at=None,
        created_at=CLAIMED_AT,
        updated_at=CLAIMED_AT,
    )
    repo.payments[PAYMENT_ID] = existing
    first = client.post(PAYMENT_PATH, headers={"Authorization": f"Bearer {ACCESS}"})
    second = client.post(PAYMENT_PATH, headers={"Authorization": f"Bearer {ACCESS}"})
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["authorization_url"] == AUTH_URL
    assert second.json()["provider_reference"] == REFERENCE
    assert provider.initialize_calls == []


def test_initializing_does_not_create_second_checkout(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    repo, _auth, provider = _bind(application)
    repo.payments["pay_busy"] = PaymentRecord(
        payment_id="pay_busy",
        assessment_id=IDENTITY.assessment_id,
        owner_user_id=USER_A,
        product_id="readiness_report_v1",
        billing_model="one_time",
        provider="paystack",
        provider_reference="psk_busy",
        provider_transaction_id=None,
        amount_minor=15900,
        currency="ZAR",
        status="INITIALIZING",
        authorization_url=None,
        paid_at=None,
        created_at=CLAIMED_AT,
        updated_at=CLAIMED_AT,
    )
    response = client.post(PAYMENT_PATH, headers={"Authorization": f"Bearer {ACCESS}"})
    assert response.status_code == 409
    assert response.json()["error_code"] == "PAYMENT_INITIALIZING"
    assert provider.initialize_calls == []


def test_client_body_cannot_override_server_owned_fields(
    app_client: tuple[TestClient, Any],
) -> None:
    client, application = app_client
    _repo, _auth, provider = _bind(application)
    response = client.post(
        PAYMENT_PATH,
        headers={"Authorization": f"Bearer {ACCESS}"},
        json={
            "amount_minor": 1,
            "currency": "USD",
            "product_id": "other",
            "provider": "other",
            "email": "attacker@example.invalid",
            "owner_user_id": USER_B,
            "reference": "client-ref",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["amount_minor"] == 15900
    assert payload["currency"] == "ZAR"
    assert payload["provider"] == "paystack"
    assert payload["provider_reference"] == REFERENCE
    assert provider.initialize_calls[0]["email"] == EMAIL
    assert "attacker@example.invalid" not in str(payload)


def test_provider_failure_marks_attempt_failed(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    provider = FakePaymentProvider()
    provider.initialize_error = PaymentProviderRejected()
    repo, _auth, _pay = _bind(application, provider=provider)
    response = client.post(PAYMENT_PATH, headers={"Authorization": f"Bearer {ACCESS}"})
    assert response.status_code == 503
    assert response.json()["error_code"] == "PAYMENT_INITIALIZATION_FAILED"
    stored = repo.payments[PAYMENT_ID]
    assert stored.status == "INITIALIZATION_FAILED"


def test_provider_timeout_is_unavailable(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    provider = FakePaymentProvider()
    provider.initialize_error = PaymentProviderUnavailable()
    _bind(application, provider=provider)
    response = client.post(PAYMENT_PATH, headers={"Authorization": f"Bearer {ACCESS}"})
    assert response.status_code == 503
    assert response.json()["error_code"] == "PAYMENT_SERVICE_UNAVAILABLE"


def test_auth_outage_and_invalid_principal(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _bind(application, verifier=FakeVerifier(error=AuthServiceUnavailable()))
    outage = client.post(PAYMENT_PATH, headers={"Authorization": f"Bearer {ACCESS}"})
    assert outage.status_code == 503
    assert outage.json()["error_code"] == "AUTH_SERVICE_UNAVAILABLE"
    _bind(application, verifier=FakeVerifier(error=RuntimeError("boom")))
    crashed = client.post(PAYMENT_PATH, headers={"Authorization": f"Bearer {ACCESS}"})
    assert crashed.status_code == 503
    _bind(application, verifier=FakeVerifier(principal=None))
    missing = client.post(PAYMENT_PATH, headers={"Authorization": f"Bearer {ACCESS}"})
    assert missing.status_code == 401
    assert missing.json()["error_code"] == "AUTH_INVALID"

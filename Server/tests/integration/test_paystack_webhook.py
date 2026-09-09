"""HTTP tests for POST /api/v1/payments/paystack/webhook. Fakes only."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.v1.payments import _parse_event, _read_bounded_body
from app.commerce.errors import PaymentProviderRejected, PaymentProviderUnavailable
from app.commerce.paystack import PaystackPaymentProvider, paystack_webhook_signature
from app.core.config import get_settings
from app.main import create_app
from app.repositories.records import AssessmentRecord, AssessmentRunRecord, PaymentRecord
from tests.integration.test_payment_checkout import AUTH_URL, EMAIL, FakePaymentProvider
from tests.unit.services.test_anonymous_assessment import IDENTITY, RecordingRepository

FAKE_SECRET = "sk_test_fake_skillsignalza_not_real"
CLAIMED_AT = datetime(2026, 9, 4, 13, 0, tzinfo=UTC)
USER_A = "user-verified-a"
PAYMENT_ID = "pay_fixed_test_id"
REFERENCE = "psk_fixed_test_reference"
TX_ID = "9007199254740991"
WEBHOOK_PATH = "/api/v1/payments/paystack/webhook"
PAID_AT = "2026-09-08T09:00:00.000Z"


@pytest.fixture
def app_client() -> Iterator[tuple[TestClient, Any]]:
    get_settings.cache_clear()
    application = create_app()
    with TestClient(application) as client:
        application.state.auto_bind_resources = False
        yield client, application
    get_settings.cache_clear()


def _event(event: str = "charge.success", reference: str = REFERENCE) -> bytes:
    return json.dumps({"event": event, "data": {"reference": reference, "amount": 15900}}).encode()


def _initialized_payment() -> PaymentRecord:
    return PaymentRecord(
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


def _seed(repo: RecordingRepository) -> None:
    repo.assessments[IDENTITY.assessment_id] = AssessmentRecord(
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
    repo.runs[IDENTITY.run_id] = AssessmentRunRecord(
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
    payment = _initialized_payment()
    repo.payments[PAYMENT_ID] = payment
    repo.payments_by_reference[REFERENCE] = PAYMENT_ID


def _bind_fake(application: Any) -> tuple[RecordingRepository, FakePaymentProvider]:
    repo = RecordingRepository()
    provider = FakePaymentProvider()
    _seed(repo)
    application.state.repository = repo
    application.state.payment_provider = provider
    return repo, provider


def test_missing_signature_is_rejected(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    repo, provider = _bind_fake(application)
    response = client.post(WEBHOOK_PATH, content=_event())
    assert response.status_code == 400
    assert repo.assessments[IDENTITY.assessment_id].access_state == "PREVIEW"
    assert provider.verify_calls == []


def test_invalid_signature_is_rejected_before_event_fields(
    app_client: tuple[TestClient, Any],
) -> None:
    client, application = app_client
    repo, provider = _bind_fake(application)
    provider.valid_signature = False
    response = client.post(
        WEBHOOK_PATH,
        content=_event(),
        headers={"x-paystack-signature": "deadbeef"},
    )
    assert response.status_code == 400
    assert repo.assessments[IDENTITY.assessment_id].access_state == "PREVIEW"
    assert provider.verify_calls == []


def test_hmac_sha512_signature_is_required_over_exact_bytes(
    app_client: tuple[TestClient, Any],
) -> None:
    client, application = app_client
    repo = RecordingRepository()
    _seed(repo)
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "status": True,
                "data": {
                    "id": int(TX_ID),
                    "status": "success",
                    "reference": REFERENCE,
                    "amount": 15900,
                    "currency": "ZAR",
                    "paid_at": PAID_AT,
                },
            },
        )

    provider = PaystackPaymentProvider(
        secret_key=FAKE_SECRET,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    application.state.repository = repo
    application.state.payment_provider = provider
    body = _event()
    valid = paystack_webhook_signature(FAKE_SECRET, body)
    other = paystack_webhook_signature(FAKE_SECRET, b'{"event":"charge.success"}')
    rejected = client.post(WEBHOOK_PATH, content=body, headers={"x-paystack-signature": other})
    accepted = client.post(WEBHOOK_PATH, content=body, headers={"x-paystack-signature": valid})
    assert rejected.status_code == 400
    assert accepted.status_code == 200
    assert repo.assessments[IDENTITY.assessment_id].access_state == "UNLOCKED"
    assert repo.payments[PAYMENT_ID].status == "SUCCEEDED"
    assert captured == [f"https://api.paystack.co/transaction/verify/{REFERENCE}"]
    assert FAKE_SECRET not in accepted.text
    assert EMAIL not in accepted.text
    assert "authorization" not in accepted.text.lower()


def test_oversized_body_is_rejected(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _bind_fake(application)
    response = client.post(
        WEBHOOK_PATH,
        content=b"{" + (b"a" * 70_000) + b"}",
        headers={"x-paystack-signature": "ab", "content-length": "70002"},
    )
    assert response.status_code == 413


def test_signed_non_charge_success_is_noop(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    repo, provider = _bind_fake(application)
    response = client.post(
        WEBHOOK_PATH,
        content=_event("invoice.create"),
        headers={"x-paystack-signature": "ok"},
    )
    assert response.status_code == 200
    assert repo.assessments[IDENTITY.assessment_id].access_state == "PREVIEW"
    assert provider.verify_calls == []


def test_signed_charge_success_does_not_unlock_without_verify(
    app_client: tuple[TestClient, Any],
) -> None:
    client, application = app_client
    repo, provider = _bind_fake(application)
    provider.verify_error = PaymentProviderRejected()
    response = client.post(
        WEBHOOK_PATH,
        content=_event(),
        headers={"x-paystack-signature": "ok"},
    )
    assert response.status_code == 200
    assert repo.assessments[IDENTITY.assessment_id].access_state == "PREVIEW"
    assert repo.payments[PAYMENT_ID].status == "INITIALIZED"
    assert provider.verify_calls == [REFERENCE]


def test_provider_timeout_does_not_unlock(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    repo, provider = _bind_fake(application)
    provider.verify_error = PaymentProviderUnavailable()
    response = client.post(
        WEBHOOK_PATH,
        content=_event(),
        headers={"x-paystack-signature": "ok"},
    )
    assert response.status_code == 503
    assert repo.assessments[IDENTITY.assessment_id].access_state == "PREVIEW"


@pytest.mark.parametrize(
    ("verified", "unlocked"),
    [
        (
            {
                "status": "failed",
                "reference": REFERENCE,
                "amount_minor": 15900,
                "currency": "ZAR",
            },
            False,
        ),
        (
            {
                "status": "success",
                "reference": "other-ref",
                "amount_minor": 15900,
                "currency": "ZAR",
            },
            False,
        ),
        (
            {
                "status": "success",
                "reference": REFERENCE,
                "amount_minor": 1,
                "currency": "ZAR",
            },
            False,
        ),
        (
            {
                "status": "success",
                "reference": REFERENCE,
                "amount_minor": 15900,
                "currency": "NGN",
            },
            False,
        ),
    ],
)
def test_verified_mismatch_does_not_unlock(
    app_client: tuple[TestClient, Any],
    verified: dict[str, Any],
    unlocked: bool,
) -> None:
    client, application = app_client
    repo, provider = _bind_fake(application)
    provider.verified = provider.verified.__class__(
        reference=str(verified["reference"]),
        provider_transaction_id=TX_ID,
        amount_minor=int(verified["amount_minor"]),
        currency=str(verified["currency"]),
        paid_at=datetime(2026, 9, 8, 9, 0, tzinfo=UTC),
        status=str(verified["status"]),
    )
    response = client.post(
        WEBHOOK_PATH,
        content=_event(),
        headers={"x-paystack-signature": "ok"},
    )
    assert response.status_code == 200
    assert (repo.assessments[IDENTITY.assessment_id].access_state == "UNLOCKED") is unlocked


def test_valid_verified_success_unlocks_once_and_replay_is_idempotent(
    app_client: tuple[TestClient, Any],
) -> None:
    client, application = app_client
    repo, provider = _bind_fake(application)
    first = client.post(
        WEBHOOK_PATH,
        content=_event(),
        headers={"x-paystack-signature": "ok"},
    )
    second = client.post(
        WEBHOOK_PATH,
        content=_event(),
        headers={"x-paystack-signature": "ok"},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert repo.assessments[IDENTITY.assessment_id].access_state == "UNLOCKED"
    assert repo.payments[PAYMENT_ID].status == "SUCCEEDED"
    assert repo.payments[PAYMENT_ID].provider_transaction_id == "9001"
    assert len(provider.verify_calls) == 2
    assert "card" not in first.text
    assert FAKE_SECRET not in first.text
    assert EMAIL not in first.text


def test_signed_invalid_json_and_missing_reference_are_retryable_without_unlock(
    app_client: tuple[TestClient, Any],
) -> None:
    client, application = app_client
    repo, provider = _bind_fake(application)
    invalid = client.post(
        WEBHOOK_PATH,
        content=b"not-json",
        headers={"x-paystack-signature": "ok"},
    )
    listed = client.post(
        WEBHOOK_PATH,
        content=b"[1]",
        headers={"x-paystack-signature": "ok"},
    )
    missing = client.post(
        WEBHOOK_PATH,
        content=b'{"event":"charge.success","data":{}}',
        headers={"x-paystack-signature": "ok"},
    )
    blank = client.post(
        WEBHOOK_PATH,
        content=b'{"event":"charge.success","data":{"reference":" "}}',
        headers={"x-paystack-signature": "ok"},
    )
    bad_data = client.post(
        WEBHOOK_PATH,
        content=b'{"event":"charge.success","data":[]}',
        headers={"x-paystack-signature": "ok"},
    )
    assert invalid.status_code == 422
    assert listed.status_code == 422
    assert missing.status_code == 422
    assert blank.status_code == 422
    assert bad_data.status_code == 422
    assert invalid.json()["received"] is False
    assert repo.assessments[IDENTITY.assessment_id].access_state == "PREVIEW"
    assert repo.payments[PAYMENT_ID].status == "INITIALIZED"
    assert provider.verify_calls == []


def test_invalid_content_length_still_reads_body(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    repo, provider = _bind_fake(application)
    response = client.post(
        WEBHOOK_PATH,
        content=_event("invoice.create"),
        headers={"x-paystack-signature": "ok", "content-length": "abc"},
    )
    assert response.status_code == 200
    assert provider.verify_calls == []
    assert repo.assessments[IDENTITY.assessment_id].access_state == "PREVIEW"


def test_oversized_body_without_content_length_is_rejected() -> None:
    class Req:
        headers: dict[str, str] = {}

        async def body(self) -> bytes:
            return b"x" * 70_000

    _body, error = asyncio.run(_read_bounded_body(Req()))  # type: ignore[arg-type]
    assert error is not None
    assert error.status_code == 413
    assert _parse_event(b"[1]") is None
    assert _parse_event(b"not-json") is None

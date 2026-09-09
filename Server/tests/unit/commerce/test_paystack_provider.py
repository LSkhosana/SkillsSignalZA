"""Paystack provider tests. Mocked HTTP only; fake credentials only."""

from __future__ import annotations

import ast
import asyncio
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from app.commerce.errors import PaymentProviderRejected, PaymentProviderUnavailable
from app.commerce.paystack import (
    PAYSTACK_API_ORIGIN,
    PaystackPaymentProvider,
    paystack_webhook_signature,
)

FAKE_SECRET = "sk_test_fake_skillsignalza_not_real"
EMAIL = "owner@example.invalid"
REFERENCE = "psk_test_reference_1"
AUTH_URL = "https://checkout.paystack.com/fake-auth"
PROVIDER_PATH = Path(__file__).resolve().parents[3] / "app" / "commerce" / "paystack.py"


def _provider(handler: object, callback_url: str | None = None) -> PaystackPaymentProvider:
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    client = httpx.AsyncClient(transport=transport)
    return PaystackPaymentProvider(
        secret_key=FAKE_SECRET,
        client=client,
        callback_url=callback_url,
    )


def test_initialize_posts_server_owned_values_only() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "status": True,
                "data": {"authorization_url": AUTH_URL, "reference": REFERENCE},
            },
        )

    checkout = asyncio.run(
        _provider(handler).initialize_transaction(
            email=EMAIL,
            amount_minor=15900,
            currency="ZAR",
            reference=REFERENCE,
        )
    )
    assert checkout.authorization_url == AUTH_URL
    assert checkout.reference == REFERENCE
    request = captured[0]
    assert str(request.url) == f"{PAYSTACK_API_ORIGIN}/transaction/initialize"
    assert request.method == "POST"
    assert request.headers["Authorization"] == f"Bearer {FAKE_SECRET}"
    assert request.headers["Content-Type"].startswith("application/json")
    body = json_body(request)
    assert body == {
        "email": EMAIL,
        "amount": 15900,
        "currency": "ZAR",
        "reference": REFERENCE,
    }
    assert "candidate_ref" not in body
    assert "owner_user_id" not in body
    assert "access_token" not in body
    assert "channels" not in body
    assert "metadata" not in body


def test_initialize_includes_callback_url_only_when_configured() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "status": True,
                "data": {"authorization_url": AUTH_URL, "reference": REFERENCE},
            },
        )

    asyncio.run(
        _provider(
            handler, callback_url="https://app.example.invalid/return"
        ).initialize_transaction(
            email=EMAIL,
            amount_minor=15900,
            currency="ZAR",
            reference=REFERENCE,
        )
    )
    assert json_body(captured[0])["callback_url"] == "https://app.example.invalid/return"


def test_initialize_malformed_timeout_and_error_are_safe_failures() -> None:
    def malformed(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": True, "data": {}})

    def rejected(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"status": False, "message": "bad"})

    def timeout(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    def unavailable(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"status": False})

    with pytest.raises(PaymentProviderRejected):
        asyncio.run(
            _provider(malformed).initialize_transaction(
                email=EMAIL, amount_minor=15900, currency="ZAR", reference=REFERENCE
            )
        )
    with pytest.raises(PaymentProviderRejected):
        asyncio.run(
            _provider(rejected).initialize_transaction(
                email=EMAIL, amount_minor=15900, currency="ZAR", reference=REFERENCE
            )
        )
    with pytest.raises(PaymentProviderUnavailable):
        asyncio.run(
            _provider(timeout).initialize_transaction(
                email=EMAIL, amount_minor=15900, currency="ZAR", reference=REFERENCE
            )
        )
    with pytest.raises(PaymentProviderUnavailable):
        asyncio.run(
            _provider(unavailable).initialize_transaction(
                email=EMAIL, amount_minor=15900, currency="ZAR", reference=REFERENCE
            )
        )


def test_verify_requires_success_reference_amount_currency_id_and_paid_at() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == f"{PAYSTACK_API_ORIGIN}/transaction/verify/{REFERENCE}"
        assert request.method == "GET"
        assert request.headers["Authorization"] == f"Bearer {FAKE_SECRET}"
        return httpx.Response(
            200,
            json={
                "status": True,
                "data": {
                    "id": 9_007_199_254_740_991,
                    "status": "success",
                    "reference": REFERENCE,
                    "amount": 15900,
                    "currency": "ZAR",
                    "paid_at": "2026-09-08T09:00:00.000Z",
                },
            },
        )

    verified = asyncio.run(_provider(handler).verify_transaction(reference=REFERENCE))
    assert verified.reference == REFERENCE
    assert verified.amount_minor == 15900
    assert verified.currency == "ZAR"
    assert verified.provider_transaction_id == "9007199254740991"
    assert verified.paid_at == datetime(2026, 9, 8, 9, 0, tzinfo=UTC)
    assert verified.status == "success"


@pytest.mark.parametrize(
    "payload",
    [
        {"status": False, "data": {"status": "success"}},
        {
            "status": True,
            "data": {
                "id": 1,
                "status": "failed",
                "reference": REFERENCE,
                "amount": 15900,
                "currency": "ZAR",
                "paid_at": "2026-09-08T09:00:00Z",
            },
        },
        {
            "status": True,
            "data": {
                "id": 1,
                "status": "success",
                "reference": "other",
                "amount": 15900,
                "currency": "ZAR",
                "paid_at": "2026-09-08T09:00:00Z",
            },
        },
        {
            "status": True,
            "data": {
                "id": 1,
                "status": "success",
                "reference": REFERENCE,
                "amount": 15800,
                "currency": "ZAR",
                "paid_at": "2026-09-08T09:00:00Z",
            },
        },
        {
            "status": True,
            "data": {
                "id": 1,
                "status": "success",
                "reference": REFERENCE,
                "amount": 15900,
                "currency": "NGN",
                "paid_at": "2026-09-08T09:00:00Z",
            },
        },
        {
            "status": True,
            "data": {
                "status": "success",
                "reference": REFERENCE,
                "amount": 15900,
                "currency": "ZAR",
                "paid_at": "2026-09-08T09:00:00Z",
            },
        },
        {
            "status": True,
            "data": {
                "id": 1,
                "status": "success",
                "reference": REFERENCE,
                "amount": 15900,
                "currency": "ZAR",
            },
        },
    ],
)
def test_verify_rejects_invalid_provider_payloads(payload: dict[str, object]) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    with pytest.raises(PaymentProviderRejected):
        asyncio.run(_provider(handler).verify_transaction(reference=REFERENCE))


def test_verify_timeout_is_unavailable() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    with pytest.raises(PaymentProviderUnavailable):
        asyncio.run(_provider(handler).verify_transaction(reference=REFERENCE))


def test_webhook_signature_covers_exact_payload_bytes() -> None:
    provider = PaystackPaymentProvider(
        secret_key=FAKE_SECRET,
        client=httpx.AsyncClient(),
    )
    body = b'{"event":"charge.success","data":{"reference":"psk_test_reference_1"}}'
    valid = paystack_webhook_signature(FAKE_SECRET, body)
    assert provider.webhook_signature_is_valid(body, valid) is True
    assert provider.webhook_signature_is_valid(body, "0" * len(valid)) is False
    assert provider.webhook_signature_is_valid(body, None) is False
    assert provider.webhook_signature_is_valid(b'{"event":"other"}', valid) is False


def test_initialize_http_error_and_reference_mismatch() -> None:
    def boom(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    def mismatch(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": True,
                "data": {"authorization_url": AUTH_URL, "reference": "other"},
            },
        )

    def not_json(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json")

    def not_object(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["nope"])

    def empty_url(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"status": True, "data": {"authorization_url": "  ", "reference": REFERENCE}},
        )

    with pytest.raises(PaymentProviderUnavailable):
        asyncio.run(
            _provider(boom).initialize_transaction(
                email=EMAIL, amount_minor=15900, currency="ZAR", reference=REFERENCE
            )
        )
    with pytest.raises(PaymentProviderRejected):
        asyncio.run(
            _provider(mismatch).initialize_transaction(
                email=EMAIL, amount_minor=15900, currency="ZAR", reference=REFERENCE
            )
        )
    with pytest.raises(PaymentProviderRejected):
        asyncio.run(
            _provider(not_json).initialize_transaction(
                email=EMAIL, amount_minor=15900, currency="ZAR", reference=REFERENCE
            )
        )
    with pytest.raises(PaymentProviderRejected):
        asyncio.run(
            _provider(not_object).initialize_transaction(
                email=EMAIL, amount_minor=15900, currency="ZAR", reference=REFERENCE
            )
        )
    with pytest.raises(PaymentProviderRejected):
        asyncio.run(
            _provider(empty_url).initialize_transaction(
                email=EMAIL, amount_minor=15900, currency="ZAR", reference=REFERENCE
            )
        )


def test_verify_http_error_empty_reference_and_malformed() -> None:
    def boom(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    def unavailable(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, json={"status": False})

    def missing(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"status": False})

    def not_json(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json")

    def not_object(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["nope"])

    def data_not_object(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": True, "data": []})

    def bad_paid(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": True,
                "data": {
                    "id": 1,
                    "status": "success",
                    "reference": REFERENCE,
                    "amount": 15900,
                    "currency": "ZAR",
                    "paid_at": "not-a-date",
                },
            },
        )

    def naive_paid(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": True,
                "data": {
                    "id": "tx-1",
                    "status": "success",
                    "reference": REFERENCE,
                    "amount": 15900,
                    "currency": "ZAR",
                    "paid_at": "2026-09-08T09:00:00",
                },
            },
        )

    def bool_id(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": True,
                "data": {
                    "id": True,
                    "status": "success",
                    "reference": REFERENCE,
                    "amount": 15900,
                    "currency": "ZAR",
                    "paid_at": "2026-09-08T09:00:00Z",
                },
            },
        )

    with pytest.raises(PaymentProviderRejected):
        asyncio.run(_provider(boom).verify_transaction(reference="  "))
    with pytest.raises(PaymentProviderUnavailable):
        asyncio.run(_provider(boom).verify_transaction(reference=REFERENCE))
    with pytest.raises(PaymentProviderUnavailable):
        asyncio.run(_provider(unavailable).verify_transaction(reference=REFERENCE))
    with pytest.raises(PaymentProviderRejected):
        asyncio.run(_provider(missing).verify_transaction(reference=REFERENCE))
    with pytest.raises(PaymentProviderRejected):
        asyncio.run(_provider(not_json).verify_transaction(reference=REFERENCE))
    with pytest.raises(PaymentProviderRejected):
        asyncio.run(_provider(not_object).verify_transaction(reference=REFERENCE))
    with pytest.raises(PaymentProviderRejected):
        asyncio.run(_provider(data_not_object).verify_transaction(reference=REFERENCE))
    with pytest.raises(PaymentProviderRejected):
        asyncio.run(_provider(bad_paid).verify_transaction(reference=REFERENCE))
    with pytest.raises(PaymentProviderRejected):
        asyncio.run(_provider(bool_id).verify_transaction(reference=REFERENCE))
    verified = asyncio.run(_provider(naive_paid).verify_transaction(reference=REFERENCE))
    assert verified.provider_transaction_id == "tx-1"
    assert verified.paid_at.tzinfo is not None


def test_webhook_signature_rejects_length_mismatch() -> None:
    provider = PaystackPaymentProvider(secret_key=FAKE_SECRET, client=httpx.AsyncClient())
    body = b"{}"
    assert provider.webhook_signature_is_valid(body, "abc") is False
    assert provider.webhook_signature_is_valid(body, "   ") is False
    text = PROVIDER_PATH.read_text(encoding="utf-8")
    assert "PAYSTACK_PUBLIC_KEY" not in text
    for line in text.splitlines():
        if "logger." in line:
            assert "secret" not in line.lower()
            assert "authorization_url" not in line
            assert "email" not in line
            assert "body" not in line
    assert ast.parse(text) is not None


def json_body(request: httpx.Request) -> dict[str, object]:
    import json

    payload = json.loads(request.content.decode("utf-8"))
    assert isinstance(payload, dict)
    return payload

"""Paystack one-time transaction adapter.

Uses the official https://api.paystack.co origin only. Test vs live mode is
selected by the secret key, never by a configurable hostname. Secret keys,
customer card payloads, and raw provider bodies are never logged.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import UTC, datetime

import httpx

from app.commerce.errors import PaymentProviderRejected, PaymentProviderUnavailable
from app.commerce.provider import PaymentCheckout, VerifiedPayment

logger = logging.getLogger(__name__)

PAYSTACK_API_ORIGIN = "https://api.paystack.co"
INITIALIZE_PATH = "/transaction/initialize"
VERIFY_PATH_PREFIX = "/transaction/verify/"
INITIALIZE_TIMEOUT = httpx.Timeout(10.0)
VERIFY_TIMEOUT = httpx.Timeout(5.0)


def paystack_webhook_signature(secret: str, body: bytes) -> str:
    """Return the HMAC SHA-512 hex digest Paystack sends as x-paystack-signature."""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha512).hexdigest()


class PaystackPaymentProvider:
    """httpx adapter for Paystack Initialize and Verify Transaction."""

    def __init__(
        self,
        *,
        secret_key: str,
        client: httpx.AsyncClient,
        callback_url: str | None = None,
    ) -> None:
        self._secret_key = secret_key
        self._client = client
        self._callback_url = callback_url.strip() if callback_url else None

    async def initialize_transaction(
        self,
        *,
        email: str,
        amount_minor: int,
        currency: str,
        reference: str,
        callback_url: str | None = None,
    ) -> PaymentCheckout:
        payload: dict[str, object] = {
            "email": email,
            "amount": amount_minor,
            "currency": currency,
            "reference": reference,
        }
        resolved_callback = callback_url if callback_url is not None else self._callback_url
        if resolved_callback:
            payload["callback_url"] = resolved_callback
        try:
            response = await self._client.post(
                f"{PAYSTACK_API_ORIGIN}{INITIALIZE_PATH}",
                headers={
                    "Authorization": f"Bearer {self._secret_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=INITIALIZE_TIMEOUT,
            )
        except httpx.TimeoutException:
            logger.error("paystack initialize timed out")
            raise PaymentProviderUnavailable from None
        except httpx.HTTPError:
            logger.error("paystack initialize failed")
            raise PaymentProviderUnavailable from None
        return _checkout_from_initialize_response(response, reference)

    async def verify_transaction(self, *, reference: str) -> VerifiedPayment:
        encoded = reference.strip()
        if not encoded:
            raise PaymentProviderRejected
        try:
            response = await self._client.get(
                f"{PAYSTACK_API_ORIGIN}{VERIFY_PATH_PREFIX}{encoded}",
                headers={"Authorization": f"Bearer {self._secret_key}"},
                timeout=VERIFY_TIMEOUT,
            )
        except httpx.TimeoutException:
            logger.error("paystack verify timed out")
            raise PaymentProviderUnavailable from None
        except httpx.HTTPError:
            logger.error("paystack verify failed")
            raise PaymentProviderUnavailable from None
        return _verified_from_verify_response(response, encoded)

    def webhook_signature_is_valid(self, body: bytes, signature: str | None) -> bool:
        if signature is None or not signature.strip():
            return False
        expected = paystack_webhook_signature(self._secret_key, body)
        received = signature.strip()
        if len(expected) != len(received):
            return False
        return hmac.compare_digest(expected, received)


def _checkout_from_initialize_response(
    response: httpx.Response, expected_reference: str
) -> PaymentCheckout:
    if response.status_code >= 500:
        logger.error("paystack initialize unavailable")
        raise PaymentProviderUnavailable
    payload = _json_object(response)
    if payload is None:
        raise PaymentProviderRejected
    if payload.get("status") is not True:
        raise PaymentProviderRejected
    data = payload.get("data")
    if not isinstance(data, dict):
        raise PaymentProviderRejected
    reference = data.get("reference")
    authorization_url = data.get("authorization_url")
    if not isinstance(reference, str) or not reference.strip():
        raise PaymentProviderRejected
    if not isinstance(authorization_url, str) or not authorization_url.strip():
        raise PaymentProviderRejected
    if reference.strip() != expected_reference:
        raise PaymentProviderRejected
    return PaymentCheckout(
        reference=reference.strip(),
        authorization_url=authorization_url.strip(),
    )


def _verified_from_verify_response(
    response: httpx.Response, expected_reference: str
) -> VerifiedPayment:
    if response.status_code >= 500:
        logger.error("paystack verify unavailable")
        raise PaymentProviderUnavailable
    if response.status_code == 404:
        raise PaymentProviderRejected
    payload = _json_object(response)
    if payload is None:
        raise PaymentProviderRejected
    if payload.get("status") is not True:
        raise PaymentProviderRejected
    data = payload.get("data")
    if not isinstance(data, dict):
        raise PaymentProviderRejected
    status = data.get("status")
    reference = data.get("reference")
    amount = data.get("amount")
    currency = data.get("currency")
    transaction_id = data.get("id")
    paid_at = _parse_paid_at(data.get("paid_at"))
    if status != "success":
        raise PaymentProviderRejected
    if not isinstance(reference, str) or reference.strip() != expected_reference:
        raise PaymentProviderRejected
    if not isinstance(amount, int) or amount != 15900:
        raise PaymentProviderRejected
    if currency != "ZAR":
        raise PaymentProviderRejected
    if transaction_id is None or isinstance(transaction_id, bool):
        raise PaymentProviderRejected
    if not isinstance(transaction_id, int | str) or str(transaction_id).strip() == "":
        raise PaymentProviderRejected
    if paid_at is None:
        raise PaymentProviderRejected
    return VerifiedPayment(
        reference=reference.strip(),
        provider_transaction_id=str(transaction_id).strip(),
        amount_minor=amount,
        currency=currency,
        paid_at=paid_at,
        status="success",
    )


def _json_object(response: httpx.Response) -> dict[str, object] | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _parse_paid_at(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)

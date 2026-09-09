"""Package P: initialize one-time Readiness Report checkout and fulfill payment.

Does not rescore, rebuild Package M, or expose the paid report. Customer email
is used only for Paystack Initialize Transaction and is never persisted.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

from jsonschema.exceptions import ValidationError

from app.commerce.configuration.validation import load_validated_payment_product
from app.commerce.errors import (
    PaymentProviderError,
    PaymentProviderRejected,
    PaymentProviderUnavailable,
)
from app.commerce.provider import PaymentProvider, VerifiedPayment
from app.engine.schema_registry import draft_validator
from app.repositories.interfaces import AssessmentRepository
from app.repositories.records import PaymentRecord

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "payment.checkout.v1"
SCHEMA_FILENAME = "payment_checkout_response.schema.json"

ERROR_AUTH_REQUIRED = "AUTH_REQUIRED"
ERROR_AUTH_INVALID = "AUTH_INVALID"
ERROR_AUTH_SERVICE_UNAVAILABLE = "AUTH_SERVICE_UNAVAILABLE"
ERROR_ASSESSMENT_NOT_FOUND = "ASSESSMENT_NOT_FOUND"
ERROR_ASSESSMENT_NOT_OWNED = "ASSESSMENT_NOT_OWNED"
ERROR_ASSESSMENT_NOT_COMPLETED = "ASSESSMENT_NOT_COMPLETED"
ERROR_PAYMENT_EMAIL_REQUIRED = "PAYMENT_EMAIL_REQUIRED"
ERROR_PAYMENT_INITIALIZING = "PAYMENT_INITIALIZING"
ERROR_PAYMENT_SERVICE_UNAVAILABLE = "PAYMENT_SERVICE_UNAVAILABLE"
ERROR_PAYMENT_INITIALIZATION_FAILED = "PAYMENT_INITIALIZATION_FAILED"
ERROR_PAYMENT_RULESET_INVALID = "PAYMENT_RULESET_INVALID"

PAYMENT_HTTP_STATUS = {
    ERROR_AUTH_REQUIRED: 401,
    ERROR_AUTH_INVALID: 401,
    ERROR_AUTH_SERVICE_UNAVAILABLE: 503,
    ERROR_ASSESSMENT_NOT_FOUND: 404,
    ERROR_ASSESSMENT_NOT_OWNED: 403,
    ERROR_ASSESSMENT_NOT_COMPLETED: 409,
    ERROR_PAYMENT_EMAIL_REQUIRED: 422,
    ERROR_PAYMENT_INITIALIZING: 409,
    ERROR_PAYMENT_SERVICE_UNAVAILABLE: 503,
    ERROR_PAYMENT_INITIALIZATION_FAILED: 503,
    ERROR_PAYMENT_RULESET_INVALID: 503,
}


def payment_failed_outcome(error_code: str, assessment_id: str = "") -> dict[str, Any]:
    """Return a safe failed checkout outcome with no email, secrets, or report."""
    return _validated_outcome(
        {
            "schema_version": SCHEMA_VERSION,
            "state": "FAILED",
            "assessment_id": assessment_id,
            "payment_id": None,
            "access_state": None,
            "amount_minor": None,
            "currency": None,
            "provider": None,
            "provider_reference": None,
            "authorization_url": None,
            "error_code": error_code,
        }
    )


def payment_service_unavailable(assessment_id: str = "") -> dict[str, Any]:
    """Return a safe unconfigured/unavailable checkout outcome."""
    return payment_failed_outcome(ERROR_PAYMENT_SERVICE_UNAVAILABLE, assessment_id)


def payment_http_status(outcome: dict[str, Any]) -> int:
    """Map a checkout outcome to an HTTP status code."""
    if outcome.get("state") in {"PAYMENT_INITIALIZED", "ALREADY_UNLOCKED"}:
        return 200
    error_code = outcome.get("error_code")
    if isinstance(error_code, str):
        return PAYMENT_HTTP_STATUS.get(error_code, 500)
    return 500


def usable_verified_email(email: str | None) -> str | None:
    """Return a usable verified email, or None when checkout cannot start."""
    if not isinstance(email, str):
        return None
    stripped = email.strip()
    if not stripped or "@" not in stripped or " " in stripped:
        return None
    return stripped


async def initialize_readiness_checkout(
    *,
    repository: AssessmentRepository,
    provider: PaymentProvider,
    assessment_id: str,
    owner_user_id: str,
    email: str,
    payment_id_factory: Any | None = None,
    reference_factory: Any | None = None,
) -> dict[str, Any]:
    """Create or reuse a one-time Paystack checkout for a completed owned assessment."""
    identifier = assessment_id.strip() if isinstance(assessment_id, str) else ""
    if not identifier:
        return payment_failed_outcome(ERROR_ASSESSMENT_NOT_FOUND, identifier)
    if not isinstance(owner_user_id, str) or not owner_user_id.strip():
        return payment_failed_outcome(ERROR_AUTH_INVALID, identifier)
    verified_email = usable_verified_email(email)
    if verified_email is None:
        return payment_failed_outcome(ERROR_PAYMENT_EMAIL_REQUIRED, identifier)
    product = load_validated_payment_product()
    if product is None:
        logger.error("payment product configuration is invalid")
        return payment_failed_outcome(ERROR_PAYMENT_RULESET_INVALID, identifier)
    payment_id = _new_id(payment_id_factory, prefix="pay")
    provider_reference = _new_id(reference_factory, prefix="psk")
    try:
        began = await repository.begin_checkout_attempt(
            assessment_id=identifier,
            owner_user_id=owner_user_id.strip(),
            payment_id=payment_id,
            provider_reference=provider_reference,
            product_id=product.product_id,
            billing_model=product.billing_model,
            provider=product.provider,
            amount_minor=product.amount_minor,
            currency=product.currency,
        )
    except Exception:
        logger.error("payment checkout persistence failed")
        return payment_service_unavailable(identifier)
    if began.status == "already_unlocked":
        return _already_unlocked_outcome(identifier, began.payment)
    if began.status == "existing_initialized" and began.payment is not None:
        return _initialized_outcome(began.payment)
    if began.status == "initializing":
        return payment_failed_outcome(ERROR_PAYMENT_INITIALIZING, identifier)
    if began.status == "not_found":
        return payment_failed_outcome(ERROR_ASSESSMENT_NOT_FOUND, identifier)
    if began.status == "not_owned":
        return payment_failed_outcome(ERROR_ASSESSMENT_NOT_OWNED, identifier)
    if began.status == "not_completed":
        return payment_failed_outcome(ERROR_ASSESSMENT_NOT_COMPLETED, identifier)
    if began.status != "created" or began.payment is None:
        return payment_service_unavailable(identifier)
    attempt = began.payment
    try:
        checkout = await provider.initialize_transaction(
            email=verified_email,
            amount_minor=product.amount_minor,
            currency=product.currency,
            reference=attempt.provider_reference,
        )
    except PaymentProviderUnavailable:
        await _mark_failed(repository, attempt.payment_id)
        return payment_service_unavailable(identifier)
    except PaymentProviderRejected:
        await _mark_failed(repository, attempt.payment_id)
        return payment_failed_outcome(ERROR_PAYMENT_INITIALIZATION_FAILED, identifier)
    except PaymentProviderError:
        await _mark_failed(repository, attempt.payment_id)
        return payment_failed_outcome(ERROR_PAYMENT_INITIALIZATION_FAILED, identifier)
    except Exception:
        logger.error("paystack initialize failed")
        await _mark_failed(repository, attempt.payment_id)
        return payment_service_unavailable(identifier)
    if checkout.reference != attempt.provider_reference:
        await _mark_failed(repository, attempt.payment_id)
        return payment_failed_outcome(ERROR_PAYMENT_INITIALIZATION_FAILED, identifier)
    try:
        initialized = await repository.mark_checkout_initialized(
            payment_id=attempt.payment_id,
            authorization_url=checkout.authorization_url,
        )
    except Exception:
        logger.error("payment initialization persistence failed")
        await _mark_failed(repository, attempt.payment_id)
        return payment_service_unavailable(identifier)
    if initialized is None or initialized.authorization_url is None:
        await _mark_failed(repository, attempt.payment_id)
        return payment_service_unavailable(identifier)
    return _initialized_outcome(initialized)


async def fulfill_verified_paystack_payment(
    *,
    repository: AssessmentRepository,
    provider: PaymentProvider,
    provider_reference: str,
) -> str:
    """Verify the transaction server-to-server, then unlock exactly once.

    Returns one of: unlocked, idempotent, retry, ignored, conflict.
    """
    reference = provider_reference.strip() if isinstance(provider_reference, str) else ""
    if not reference:
        return "ignored"
    try:
        payment = await repository.get_payment_by_provider_reference(reference)
    except Exception:
        logger.error("payment lookup failed")
        return "retry"
    if payment is None:
        return "retry"
    try:
        verified = await provider.verify_transaction(reference=reference)
    except PaymentProviderUnavailable:
        return "retry"
    except PaymentProviderRejected:
        return "conflict"
    except PaymentProviderError:
        return "conflict"
    except Exception:
        logger.error("paystack verify failed")
        return "retry"
    if not _verified_matches_local(verified, payment):
        return "conflict"
    try:
        result = await repository.fulfill_payment_and_unlock(
            payment_id=payment.payment_id,
            provider_reference=verified.reference,
            provider_transaction_id=verified.provider_transaction_id,
            verified_amount_minor=verified.amount_minor,
            verified_currency=verified.currency,
            paid_at=verified.paid_at,
        )
    except Exception:
        logger.error("payment fulfillment persistence failed")
        return "retry"
    if result.status in {"unlocked", "idempotent"}:
        return result.status
    if result.status == "not_found":
        return "retry"
    return "conflict"


def _verified_matches_local(verified: VerifiedPayment, payment: PaymentRecord) -> bool:
    return (
        verified.status == "success"
        and verified.reference == payment.provider_reference
        and verified.amount_minor == 15900
        and payment.amount_minor == 15900
        and verified.currency == "ZAR"
        and payment.currency == "ZAR"
        and verified.provider_transaction_id.strip() != ""
        and isinstance(verified.paid_at, datetime)
    )


async def _mark_failed(repository: AssessmentRepository, payment_id: str) -> None:
    try:
        await repository.mark_checkout_initialization_failed(payment_id=payment_id)
    except Exception:
        logger.error("payment initialization failure persistence failed")


def _initialized_outcome(payment: PaymentRecord) -> dict[str, Any]:
    return _validated_outcome(
        {
            "schema_version": SCHEMA_VERSION,
            "state": "PAYMENT_INITIALIZED",
            "assessment_id": payment.assessment_id,
            "payment_id": payment.payment_id,
            "access_state": "PREVIEW",
            "amount_minor": 15900,
            "currency": "ZAR",
            "provider": "paystack",
            "provider_reference": payment.provider_reference,
            "authorization_url": payment.authorization_url,
            "error_code": None,
        }
    )


def _already_unlocked_outcome(assessment_id: str, payment: PaymentRecord | None) -> dict[str, Any]:
    return _validated_outcome(
        {
            "schema_version": SCHEMA_VERSION,
            "state": "ALREADY_UNLOCKED",
            "assessment_id": assessment_id,
            "payment_id": None if payment is None else payment.payment_id,
            "access_state": "UNLOCKED",
            "amount_minor": 15900,
            "currency": "ZAR",
            "provider": "paystack",
            "provider_reference": None if payment is None else payment.provider_reference,
            "authorization_url": None,
            "error_code": None,
        }
    )


def _new_id(factory: Any | None, *, prefix: str) -> str:
    if factory is not None:
        value = factory()
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"{prefix}_{uuid4().hex}"


def _validated_outcome(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        draft_validator(SCHEMA_FILENAME).validate(payload)
    except ValidationError:
        logger.error("payment checkout outcome failed schema validation")
        return {
            "schema_version": SCHEMA_VERSION,
            "state": "FAILED",
            "assessment_id": str(payload.get("assessment_id") or ""),
            "payment_id": None,
            "access_state": None,
            "amount_minor": None,
            "currency": None,
            "provider": None,
            "provider_reference": None,
            "authorization_url": None,
            "error_code": ERROR_PAYMENT_SERVICE_UNAVAILABLE,
        }
    return payload

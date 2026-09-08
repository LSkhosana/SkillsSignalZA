"""Paystack webhook HTTP boundary.

Authenticates Paystack via HMAC SHA-512. Does not use Supabase Auth.
A signed event is a trigger only; Verify Transaction unlocks entitlement.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.resources import resolve_webhook_resources
from app.services.assessment_payment import fulfill_verified_paystack_payment

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_WEBHOOK_BODY_BYTES = 65536
WEBHOOK_SIGNATURE_HEADER = "x-paystack-signature"


@router.post(
    "/paystack/webhook",
    summary="Receive Paystack webhook events",
    description=(
        "Verify x-paystack-signature, ignore non-charge.success events, then "
        "confirm the transaction with Paystack before unlocking."
    ),
)
async def post_paystack_webhook(request: Request) -> JSONResponse:
    body, error_response = await _read_bounded_body(request)
    if error_response is not None:
        return error_response
    repository, provider = await resolve_webhook_resources(request.app)
    if repository is None or provider is None:
        return JSONResponse(content={"received": False}, status_code=503)
    signature = request.headers.get(WEBHOOK_SIGNATURE_HEADER)
    if not provider.webhook_signature_is_valid(body, signature):
        logger.error("paystack webhook signature rejected")
        return JSONResponse(content={"received": False}, status_code=400)
    payload = _parse_event(body)
    if payload is None:
        return JSONResponse(content={"received": True}, status_code=200)
    event_name = payload.get("event")
    if event_name != "charge.success":
        return JSONResponse(content={"received": True}, status_code=200)
    data = payload.get("data")
    reference = data.get("reference") if isinstance(data, dict) else None
    if not isinstance(reference, str) or not reference.strip():
        return JSONResponse(content={"received": True}, status_code=200)
    outcome = await fulfill_verified_paystack_payment(
        repository=repository,
        provider=provider,
        provider_reference=reference,
    )
    if outcome == "retry":
        return JSONResponse(content={"received": False}, status_code=503)
    return JSONResponse(content={"received": True}, status_code=200)


async def _read_bounded_body(request: Request) -> tuple[bytes, JSONResponse | None]:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared = int(content_length)
        except ValueError:
            declared = None
        else:
            if declared > MAX_WEBHOOK_BODY_BYTES:
                return b"", JSONResponse(content={"received": False}, status_code=413)
    body = await request.body()
    if len(body) > MAX_WEBHOOK_BODY_BYTES:
        return b"", JSONResponse(content={"received": False}, status_code=413)
    return body, None


def _parse_event(body: bytes) -> dict[str, object] | None:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload

"""Supabase Auth verifier tests. Mocked HTTP only; no live Auth calls."""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import httpx
import pytest

from app.auth.supabase import SupabaseAuthVerifier
from app.core.auth import (
    AuthenticatedPrincipal,
    AuthServiceUnavailable,
    parse_bearer_authorization,
)

VERIFIER_PATH = Path(__file__).resolve().parents[3] / "app" / "auth" / "supabase.py"
PUBLISHABLE = "publishable-key-not-secret"
SECRET = "super-secret-must-not-be-sent"
SUPABASE_URL = "https://example.invalid.supabase.co"
ACCESS = "user-access-token-value"


def _verifier(handler: object) -> SupabaseAuthVerifier:
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    client = httpx.AsyncClient(transport=transport)
    return SupabaseAuthVerifier(
        supabase_url=SUPABASE_URL,
        publishable_key=PUBLISHABLE,
        client=client,
    )


def test_parse_bearer_authorization_missing_and_malformed() -> None:
    assert parse_bearer_authorization(None) == (None, "AUTH_REQUIRED")
    assert parse_bearer_authorization("   ") == (None, "AUTH_REQUIRED")
    assert parse_bearer_authorization("Bearer") == (None, "AUTH_INVALID")
    assert parse_bearer_authorization("Token abc") == (None, "AUTH_INVALID")
    assert parse_bearer_authorization("Bearer ") == (None, "AUTH_INVALID")
    token, error = parse_bearer_authorization("bearer  access-token  ")
    assert error is None
    assert token == "access-token"


def test_valid_user_response_returns_subject_only() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={"id": "user-123", "email": "hidden@example.invalid", "role": "authenticated"},
        )

    principal = asyncio.run(_verifier(handler).verify_access_token(ACCESS))
    assert principal == AuthenticatedPrincipal(subject="user-123")
    request = captured[0]
    assert str(request.url) == f"{SUPABASE_URL}/auth/v1/user"
    assert request.headers["apikey"] == PUBLISHABLE
    assert request.headers["Authorization"] == f"Bearer {ACCESS}"
    assert SECRET not in str(request.headers)


def test_invalid_expired_and_malformed_user_payloads_return_none() -> None:
    def unauthorized(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "invalid"})

    def forbidden(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "forbidden"})

    def missing_id(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"email": "hidden@example.invalid"})

    def not_object(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["user-123"])

    def invalid_json(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json")

    def not_found(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "missing"})

    assert asyncio.run(_verifier(unauthorized).verify_access_token(ACCESS)) is None
    assert asyncio.run(_verifier(forbidden).verify_access_token(ACCESS)) is None
    assert asyncio.run(_verifier(missing_id).verify_access_token(ACCESS)) is None
    assert asyncio.run(_verifier(not_object).verify_access_token(ACCESS)) is None
    assert asyncio.run(_verifier(invalid_json).verify_access_token(ACCESS)) is None
    assert asyncio.run(_verifier(not_found).verify_access_token(ACCESS)) is None


def test_outage_and_unexpected_status_raise_unavailable() -> None:
    def boom(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    def server_error(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "down"})

    with pytest.raises(AuthServiceUnavailable):
        asyncio.run(_verifier(boom).verify_access_token(ACCESS))
    with pytest.raises(AuthServiceUnavailable):
        asyncio.run(_verifier(server_error).verify_access_token(ACCESS))


def test_verifier_does_not_log_bearer_or_use_secret_key() -> None:
    text = VERIFIER_PATH.read_text(encoding="utf-8")
    assert "SUPABASE_SECRET_KEY" not in text
    assert "secret_key" not in text
    for line in text.splitlines():
        if "logger." in line:
            assert "access_token" not in line
            assert "Authorization" not in line
            assert "Bearer" not in line
    tree = ast.parse(text)
    assert tree is not None

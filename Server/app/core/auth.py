"""Verified caller identity for Package O.

Routes and services depend only on AuthenticatedPrincipal. They must not
decode JWTs locally or trust client-supplied user identifiers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class AuthServiceUnavailable(Exception):
    """Auth provider could not be reached. Safe to map to HTTP 503."""


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """Stable verified subject. Never includes email, tokens, or JWT bodies."""

    subject: str


class AuthVerifier(Protocol):
    """Verify a caller access token against the identity provider."""

    async def verify_access_token(self, access_token: str) -> AuthenticatedPrincipal | None:
        """Return the verified subject, or None when the token is invalid."""


def parse_bearer_authorization(header: str | None) -> tuple[str | None, str | None]:
    """Return (access_token, error_code).

    error_code is AUTH_REQUIRED when the header is missing, AUTH_INVALID when
    the scheme/token is malformed, or None when a token was extracted.
    The token itself must never be logged.
    """
    if header is None or not header.strip():
        return None, "AUTH_REQUIRED"
    scheme, _, remainder = header.strip().partition(" ")
    if scheme.lower() != "bearer" or not remainder.strip():
        return None, "AUTH_INVALID"
    token = remainder.strip()
    if not token or token.lower() == "bearer":
        return None, "AUTH_INVALID"
    return token, None

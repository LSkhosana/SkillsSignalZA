"""Supabase Auth adapter. Verifies user access tokens via the Auth API."""

from __future__ import annotations

import logging

import httpx

from app.core.auth import AuthenticatedPrincipal, AuthServiceUnavailable

logger = logging.getLogger(__name__)


class SupabaseAuthVerifier:
    """Call GET /auth/v1/user with the publishable apikey. Never uses the secret key."""

    def __init__(
        self,
        *,
        supabase_url: str,
        publishable_key: str,
        client: httpx.AsyncClient,
    ) -> None:
        self._base_url = supabase_url.rstrip("/")
        self._publishable_key = publishable_key
        self._client = client

    async def verify_access_token(self, access_token: str) -> AuthenticatedPrincipal | None:
        try:
            response = await self._client.get(
                f"{self._base_url}/auth/v1/user",
                headers={
                    "apikey": self._publishable_key,
                    "Authorization": f"Bearer {access_token}",
                },
            )
        except httpx.HTTPError:
            logger.error("supabase auth verification failed")
            raise AuthServiceUnavailable from None
        if response.status_code == 200:
            try:
                payload = response.json()
            except ValueError:
                return None
            if not isinstance(payload, dict):
                return None
            subject = payload.get("id")
            if isinstance(subject, str) and subject.strip():
                return AuthenticatedPrincipal(subject=subject.strip())
            return None
        if response.status_code in {401, 403, 404}:
            return None
        logger.error("supabase auth verification unavailable")
        raise AuthServiceUnavailable

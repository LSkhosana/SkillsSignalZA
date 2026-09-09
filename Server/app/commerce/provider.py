"""Provider-neutral one-time payment ports.

Route and service code must depend on these types, not raw Paystack JSON.
Subscription operations are intentionally absent from Package P.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class PaymentCheckout:
    """Normalized Initialize Transaction handoff for a customer redirect."""

    reference: str
    authorization_url: str


@dataclass(frozen=True)
class VerifiedPayment:
    """Normalized Verify Transaction result used for entitlement fulfillment."""

    reference: str
    provider_transaction_id: str
    amount_minor: int
    currency: str
    paid_at: datetime
    status: str


class PaymentProvider(Protocol):
    """One-time checkout provider. Later packages may extend this port."""

    async def initialize_transaction(
        self,
        *,
        email: str,
        amount_minor: int,
        currency: str,
        reference: str,
        callback_url: str | None = None,
    ) -> PaymentCheckout:
        """Create a hosted checkout session from server-owned values only."""

    async def verify_transaction(self, *, reference: str) -> VerifiedPayment:
        """Confirm a transaction server-to-server. Webhook bodies are not proof."""

    def webhook_signature_is_valid(self, body: bytes, signature: str | None) -> bool:
        """Return True when HMAC SHA-512 matches the exact payload bytes."""

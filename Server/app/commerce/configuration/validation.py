"""Validate the checked-in V1 payment product before any checkout use."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.commerce.configuration import load_payment_product_v1

ACTIVE_CATALOG_VERSION = "1.0.0"
APPROVED_STATUS = "approved"
PRODUCT_ID = "readiness_report_v1"
BILLING_MODEL = "one_time"
AMOUNT_MINOR = 15900
CURRENCY = "ZAR"
PROVIDER = "paystack"


@dataclass(frozen=True)
class PaymentProduct:
    """Server-owned V1 one-time product. Clients cannot override these values."""

    catalog_version: str
    status: str
    product_id: str
    billing_model: str
    amount_minor: int
    currency: str
    provider: str


def load_validated_payment_product(
    document: dict[str, Any] | None = None,
) -> PaymentProduct | None:
    """Return the approved V1 product, or None when the catalog is invalid."""
    try:
        loaded = document if document is not None else load_payment_product_v1()
    except (OSError, TypeError, ValueError):
        return None
    if not isinstance(loaded, dict):
        return None
    catalog_version = loaded.get("catalog_version")
    status = loaded.get("status")
    product_id = loaded.get("product_id")
    billing_model = loaded.get("billing_model")
    amount_minor = loaded.get("amount_minor")
    currency = loaded.get("currency")
    provider = loaded.get("provider")
    if (
        catalog_version != ACTIVE_CATALOG_VERSION
        or status != APPROVED_STATUS
        or product_id != PRODUCT_ID
        or billing_model != BILLING_MODEL
        or amount_minor != AMOUNT_MINOR
        or not isinstance(amount_minor, int)
        or currency != CURRENCY
        or provider != PROVIDER
    ):
        return None
    return PaymentProduct(
        catalog_version=catalog_version,
        status=status,
        product_id=product_id,
        billing_model=billing_model,
        amount_minor=amount_minor,
        currency=currency,
        provider=provider,
    )

"""Payment product catalog tests. No network."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from app.commerce.configuration import PAYMENT_PRODUCT_V1_PATH, load_payment_product_v1
from app.commerce.configuration.validation import load_validated_payment_product

APPROVED_PAYMENT_PRODUCT_V1_SHA256 = (
    "a5f96f4a666afce22297b76453c1132960e21ef5bf127a341524a747c8ba3b70"
)
SERVER_ROOT = Path(__file__).resolve().parents[3]


def _canonical_sha256(document: dict[str, Any]) -> str:
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_approved_payment_product_is_locked_and_server_owned() -> None:
    document = load_payment_product_v1()
    assert _canonical_sha256(document) == APPROVED_PAYMENT_PRODUCT_V1_SHA256
    product = load_validated_payment_product()
    assert product is not None
    assert product.product_id == "readiness_report_v1"
    assert product.billing_model == "one_time"
    assert product.amount_minor == 15900
    assert product.currency == "ZAR"
    assert product.provider == "paystack"
    assert product.status == "approved"
    assert product.catalog_version == "1.0.0"
    raw = PAYMENT_PRODUCT_V1_PATH.read_text(encoding="utf-8")
    assert "sk_" not in raw
    assert "callback" not in raw.lower()
    assert "@" not in raw


def test_invalid_payment_product_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.commerce.configuration.validation.load_payment_product_v1",
        lambda: {"product_id": "other", "amount_minor": 1},
    )
    assert load_validated_payment_product() is None


def test_non_object_payment_product_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.commerce.configuration.load_json", lambda path: ["not-an-object"])
    with pytest.raises(TypeError, match="JSON object"):
        load_payment_product_v1()


def test_load_validated_handles_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> dict[str, Any]:
        raise OSError("missing")

    monkeypatch.setattr(
        "app.commerce.configuration.validation.load_payment_product_v1",
        boom,
    )
    assert load_validated_payment_product() is None
    assert load_validated_payment_product(["nope"]) is None  # type: ignore[arg-type]


def test_package_p_source_has_no_payfast_or_public_key() -> None:
    forbidden = ("payfast", "PayFast", "PAYFAST", "PAYSTACK_PUBLIC_KEY")
    for path in SERVER_ROOT.joinpath("app").rglob("*"):
        if path.suffix not in {".py", ".json", ".sql"}:
            continue
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text
    tree = ast.parse((SERVER_ROOT / "app" / "commerce" / "paystack.py").read_text(encoding="utf-8"))
    assert tree is not None

"""Versioned machine-readable payment product configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIGURATION_DIR = Path(__file__).resolve().parent
PAYMENT_PRODUCT_V1_PATH = CONFIGURATION_DIR / "payment_product_v1.json"


def load_json(path: Path) -> Any:
    """Load a UTF-8 JSON document from disk."""
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_payment_product_v1() -> dict[str, Any]:
    """Return the canonical V1 Readiness Report payment product document."""
    document = load_json(PAYMENT_PRODUCT_V1_PATH)
    if not isinstance(document, dict):
        msg = "payment_product_v1.json must contain a JSON object"
        raise TypeError(msg)
    return document

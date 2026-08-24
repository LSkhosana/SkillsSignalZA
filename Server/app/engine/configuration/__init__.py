"""Versioned machine-readable engine configuration.

Rubric weights, anchors, caps, bands, and rule identifiers live in JSON.
This package exposes those documents only; it does not compute scores.
"""

import json
from pathlib import Path
from typing import Any

CONFIGURATION_DIR = Path(__file__).resolve().parent
RUBRIC_V2_PATH = CONFIGURATION_DIR / "rubric_v2.json"


def load_json(path: Path) -> Any:
    """Load a UTF-8 JSON document from disk."""
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_rubric_v2() -> dict[str, Any]:
    """Return the canonical Rubric V2 configuration document."""
    document = load_json(RUBRIC_V2_PATH)
    if not isinstance(document, dict):
        msg = "rubric_v2.json must contain a JSON object"
        raise TypeError(msg)
    return document

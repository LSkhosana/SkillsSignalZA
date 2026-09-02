"""Versioned machine-readable engine configuration.

Rubric weights, anchors, caps, bands, rule identifiers, actions, and
projects live in JSON. This package exposes those documents only; it
does not compute scores or select recommendations.
"""

import json
from pathlib import Path
from typing import Any

CONFIGURATION_DIR = Path(__file__).resolve().parent
RUBRIC_V2_PATH = CONFIGURATION_DIR / "rubric_v2.json"
ACTION_CATALOG_V1_PATH = CONFIGURATION_DIR / "action_catalog_v1.json"
PROJECT_CATALOG_V1_PATH = CONFIGURATION_DIR / "project_catalog_v1.json"
EVIDENCE_RULES_V1_PATH = CONFIGURATION_DIR / "evidence_rules_v1.json"


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


def load_action_catalog_v1() -> dict[str, Any]:
    """Return the canonical Package B action catalogue."""
    document = load_json(ACTION_CATALOG_V1_PATH)
    if not isinstance(document, dict):
        msg = "action_catalog_v1.json must contain a JSON object"
        raise TypeError(msg)
    return document


def load_project_catalog_v1() -> dict[str, Any]:
    """Return the canonical Package B project catalogue."""
    document = load_json(PROJECT_CATALOG_V1_PATH)
    if not isinstance(document, dict):
        msg = "project_catalog_v1.json must contain a JSON object"
        raise TypeError(msg)
    return document


def load_evidence_rules_v1() -> dict[str, Any]:
    """Return the canonical Package H explicit-evidence rule registry."""
    document = load_json(EVIDENCE_RULES_V1_PATH)
    if not isinstance(document, dict):
        msg = "evidence_rules_v1.json must contain a JSON object"
        raise TypeError(msg)
    return document

"""Package M report-copy registry structure, version, and hash lock."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from app.engine.configuration import load_report_copy_v1
from app.engine.reporting.outcomes import (
    CONTRACT_VERSION,
    REPORT_VERSION,
    REQUIRED_CAP_RULE_IDS,
    REQUIRED_EVIDENCE_ANCHORS,
    REQUIRED_QUALIFICATION_ROUTES,
    RUBRIC_VERSION,
)

APPROVED_REPORT_COPY_SHA256 = "bbd74d7116facb863e917fc875e0cae28d9de492ca850de9b38b42141a9d362a"
FORBIDDEN_COPY = (
    "hiring guarantee",
    "guaranteed job",
    "employability",
    "will be hired",
    "probability of employment",
)


def _canonical_sha256(document: Mapping[str, Any]) -> str:
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_report_copy_metadata_and_canonical_hash_are_locked() -> None:
    copy = load_report_copy_v1()
    assert copy["report_version"] == REPORT_VERSION
    assert copy["contract_version"] == CONTRACT_VERSION
    assert copy["rubric_version"] == RUBRIC_VERSION
    assert copy["status"] == "approved"
    assert _canonical_sha256(copy) == APPROVED_REPORT_COPY_SHA256


def test_report_copy_contains_required_customer_labels() -> None:
    copy = load_report_copy_v1()
    for key in REQUIRED_EVIDENCE_ANCHORS:
        assert copy["evidence_anchor_labels"][key]
    for key in REQUIRED_QUALIFICATION_ROUTES:
        assert copy["qualification_route_labels"][key]
    for key in REQUIRED_CAP_RULE_IDS:
        assert copy["cap_rule_labels"][key]
    assert copy["benchmark"]["scope_statement"]
    assert copy["benchmark"]["disclaimer"]
    blob = json.dumps(copy).lower()
    for phrase in FORBIDDEN_COPY:
        assert phrase not in blob

"""Canonical outcomes for the Package M reporting engine."""

from __future__ import annotations

from typing import Any

REPORT_VERSION = "1.0.0"
REPORT_SCHEMA_VERSION = "readiness.report.v1"
PREVIEW_SCHEMA_VERSION = "readiness.preview.v1"
REPORTING_VERSION = "readiness.reporting.v1"
CONTRACT_VERSION = "1.2.0"
RUBRIC_VERSION = "V2"
REVIEW_SENTINEL = "PROJECT_RECOMMENDATION_REVIEW_REQUIRED"
ERROR_REPORT_VERSION_NOT_FOUND = "REPORT_VERSION_NOT_FOUND"
ERROR_REPORT_RULESET_INVALID = "REPORT_RULESET_INVALID"
ERROR_REPORT_BUILD_FAILED = "REPORT_BUILD_FAILED"
ERROR_ASSESSMENT_NOT_FOUND = "ASSESSMENT_NOT_FOUND"
ERROR_ASSESSMENT_NOT_COMPLETED = "ASSESSMENT_NOT_COMPLETED"
ERROR_ASSESSMENT_RESULT_MISSING = "ASSESSMENT_RESULT_MISSING"
REQUIRED_EVIDENCE_ANCHORS = (
    "demonstrated",
    "documented",
    "named_only",
    "missing_unverifiable",
)
REQUIRED_QUALIFICATION_ROUTES = (
    "se.qual.completed",
    "se.qual.in_progress",
    "se.qual.experience",
    "se.qual.bootcamp",
    "se.qual.adjacent",
    "se.qual.none",
    "da.qual.completed",
    "da.qual.in_progress",
    "da.qual.experience",
    "da.qual.bootcamp",
    "da.qual.adjacent",
    "da.qual.none",
)
REQUIRED_CAP_RULE_IDS = (
    "rubric.v2.se.cap.cv_only_projects",
    "rubric.v2.da.cap.cv_only_projects",
    "rubric.v2.se.cap.no_language",
    "rubric.v2.da.cap.no_sql",
    "rubric.v2.da.cap.google_sheets_ceiling",
)


class ReportingHalt(Exception):
    """Stop report assembly with a stable, non-leaking error code."""

    def __init__(self, error_code: str) -> None:
        self.error_code = error_code


def reporting_failure(error_code: str) -> dict[str, Any]:
    """Return a safe engine failure without candidate or config text."""
    return {"state": "FAILED", "error_code": error_code}


def is_report_payload(payload: object) -> bool:
    return isinstance(payload, dict) and payload.get("schema_version") == REPORT_SCHEMA_VERSION

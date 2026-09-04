"""Free Readiness Report preview derived from a completed full report."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from jsonschema.exceptions import ValidationError

from app.engine.reporting.outcomes import (
    ERROR_REPORT_BUILD_FAILED,
    ERROR_REPORT_RULESET_INVALID,
    PREVIEW_SCHEMA_VERSION,
    ReportingHalt,
    is_report_payload,
    reporting_failure,
)
from app.engine.schema_registry import draft_validator


def build_readiness_preview(report_payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return the locked free-preview surface of a completed full report."""
    try:
        return _build(report_payload)
    except ReportingHalt as exc:
        return reporting_failure(exc.error_code)
    except Exception:
        return reporting_failure(ERROR_REPORT_BUILD_FAILED)


def _build(report_payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not is_report_payload(report_payload):
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    assert isinstance(report_payload, Mapping)
    summary = report_payload["score_summary"]
    payload = {
        "schema_version": PREVIEW_SCHEMA_VERSION,
        "report_version": report_payload["report_version"],
        "assessment_id": report_payload["assessment_id"],
        "run_id": report_payload["run_id"],
        "track": report_payload["track"],
        "track_label": report_payload["track_label"],
        "final_score": summary["final_score"],
        "score_max": summary["score_max"],
        "band_id": summary["band_id"],
        "band_label": summary["band_label"],
        "strongest_area": summary["strongest_area"],
        "priority_gap": summary["priority_gap"],
    }
    try:
        draft_validator("readiness_preview.schema.json").validate(payload)
    except ValidationError:
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID) from None
    return payload

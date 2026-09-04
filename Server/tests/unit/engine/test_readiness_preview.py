"""Package M free-preview boundary tests."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.engine.reporting import build_readiness_preview, build_readiness_report
from app.engine.reporting.outcomes import (
    ERROR_REPORT_BUILD_FAILED,
    ERROR_REPORT_RULESET_INVALID,
    PREVIEW_SCHEMA_VERSION,
)
from app.engine.schema_registry import SCHEMA_DIR, draft_validator

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "golden_candidates"
PAID_ONLY_KEYS = (
    "category_breakdown",
    "strengths",
    "material_gaps",
    "priority_actions",
    "project_recommendation",
    "criterion_breakdown",
    "benchmark",
    "candidate_instruction",
    "required_output",
    "completion_check",
    "evidence_note",
    "category_caps",
    "overall_caps",
    "source_snapshot",
    "explicit_text",
    "evidence_ids",
    "evidence_facts",
    "source_records",
)


def _golden(filename: str) -> dict[str, Any]:
    payload = json.loads((FIXTURE_DIR / filename).read_text(encoding="utf-8"))
    return deepcopy(payload["expected"]["assessment_result"])


def test_preview_matches_full_report_locked_fields() -> None:
    report = build_readiness_report(_golden("c03_se_no_language_cap.json"))
    preview = build_readiness_preview(report)
    draft_validator("readiness_preview.schema.json").validate(preview)
    assert preview["schema_version"] == PREVIEW_SCHEMA_VERSION
    assert preview["final_score"] == report["score_summary"]["final_score"]
    assert preview["band_id"] == report["score_summary"]["band_id"]
    assert preview["band_label"] == report["score_summary"]["band_label"]
    assert preview["strongest_area"] == report["score_summary"]["strongest_area"]
    assert preview["priority_gap"] == report["score_summary"]["priority_gap"]
    assert (SCHEMA_DIR / "readiness_preview.schema.json").is_file()
    assert (
        draft_validator("readiness_preview.schema.json")
        .schema["$id"]
        .endswith("readiness-preview.json")
    )


def test_preview_excludes_paid_only_fields() -> None:
    preview = build_readiness_preview(
        build_readiness_report(_golden("c03_se_no_language_cap.json"))
    )
    keys = set(preview)
    for name in PAID_ONLY_KEYS:
        assert name not in keys
    blob = json.dumps(preview)
    for name in PAID_ONLY_KEYS:
        assert f'"{name}"' not in blob


def test_score_100_preview_has_null_priority_gap() -> None:
    report = build_readiness_report(_golden("c01_se_full_score.json"))
    preview = build_readiness_preview(report)
    assert report["score_summary"]["priority_gap"] is None
    assert preview["priority_gap"] is None
    assert preview["final_score"] == 100


def test_preview_rejects_non_report_payloads() -> None:
    failed = build_readiness_preview(
        {"state": "FAILED", "error_code": ERROR_REPORT_RULESET_INVALID}
    )
    assert failed == {"state": "FAILED", "error_code": ERROR_REPORT_RULESET_INVALID}
    assert build_readiness_preview(None)["error_code"] == ERROR_REPORT_RULESET_INVALID
    exploded = build_readiness_preview({"schema_version": "readiness.report.v1"})
    assert exploded["error_code"] == ERROR_REPORT_BUILD_FAILED

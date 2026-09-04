"""Package M full Readiness Report assembly tests."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.engine.configuration import (
    load_action_catalog_v1,
    load_project_catalog_v1,
    load_report_copy_v1,
    load_rubric_v2,
)
from app.engine.reporting import build_readiness_report
from app.engine.reporting.outcomes import (
    ERROR_REPORT_BUILD_FAILED,
    ERROR_REPORT_RULESET_INVALID,
    ERROR_REPORT_VERSION_NOT_FOUND,
    REPORT_SCHEMA_VERSION,
)
from app.engine.schema_registry import SCHEMA_DIR, draft_validator

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "golden_candidates"
PAID_LEAK_KEYS = (
    "explicit_text",
    "evidence_ids",
    "evidence_facts",
    "source_records",
    "source_snapshot",
    "cv_hash",
    "content_hash",
    "submitted_url",
    "original_filename",
    "storage_path",
    "locator",
)
SECRET_SENTINEL = "SKILLSIGNALZA_GOLDEN_SECRET_DO_NOT_LEAK_7f9c2e"


def _golden(filename: str) -> dict[str, Any]:
    payload = json.loads((FIXTURE_DIR / filename).read_text(encoding="utf-8"))
    return deepcopy(payload["expected"]["assessment_result"])


def _dump(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def test_completed_se_and_da_results_build_schema_valid_reports() -> None:
    se = build_readiness_report(_golden("c01_se_full_score.json"))
    da = build_readiness_report(_golden("c02_da_full_score.json"))
    validator = draft_validator("readiness_report.schema.json")
    validator.validate(se)
    validator.validate(da)
    assert se["schema_version"] == REPORT_SCHEMA_VERSION
    assert se["track"] == "software_engineering"
    assert da["track"] == "data_analytics"
    assert (SCHEMA_DIR / "readiness_report.schema.json").is_file()
    assert validator.schema["$id"].endswith("readiness-report.json")


def test_score_band_caps_and_labels_copy_canonical_and_rubric_values() -> None:
    result = _golden("c03_se_no_language_cap.json")
    report = build_readiness_report(result)
    rubric = load_rubric_v2()
    track = rubric["tracks"]["software_engineering"]
    band = next(item for item in rubric["score_bands"] if item["id"] == result["band"])
    summary = report["score_summary"]
    assert summary["final_score"] == result["final_score"]
    assert summary["raw_total"] == result["raw_total"]
    assert summary["band_id"] == result["band"]
    assert summary["band_label"] == band["label"]
    assert summary["applicable_overall_cap"] == result["applicable_overall_cap"]
    assert summary["overall_caps"][0]["rule_id"] == result["overall_caps"][0]["rule_id"]
    assert summary["overall_caps"][0]["cap"] == result["overall_caps"][0]["cap"]
    assert (
        summary["overall_caps"][0]["rule_label"]
        == load_report_copy_v1()["cap_rule_labels"][result["overall_caps"][0]["rule_id"]]
    )
    assert report["track_label"] == track["display_name"]
    assert [row["category_id"] for row in report["category_breakdown"]] == [
        item["id"] for item in track["categories"]
    ]
    assert [row["criterion_id"] for row in report["criterion_breakdown"]] == [
        item["id"] for item in track["criteria"]
    ]
    for row, category in zip(report["category_breakdown"], track["categories"], strict=True):
        assert row["label"] == category["display_name"]
        assert row["score"] == next(
            item["final_score"]
            for item in result["category_results"]
            if item["category_id"] == category["id"]
        )


def test_strongest_area_uses_category_percentage_and_rubric_order_tie_break() -> None:
    result = _golden("c01_se_full_score.json")
    full = build_readiness_report(result)
    assert full["score_summary"]["strongest_area"]["category_id"] == "se.core"
    assert full["score_summary"]["strongest_area"]["percentage"] == 100
    mutated = deepcopy(result)
    for row in mutated["category_results"]:
        if row["category_id"] == "se.core":
            row["final_score"] = 7
        elif row["category_id"] == "se.tools":
            row["final_score"] = 4
        else:
            row["final_score"] = 0
    tied = build_readiness_report(mutated)
    # 7/35 and 4/20 are both 20 percent; rubric order keeps se.core first.
    assert tied["score_summary"]["strongest_area"]["category_id"] == "se.core"
    assert tied["score_summary"]["strongest_area"]["percentage"] == 20
    later = deepcopy(result)
    for row in later["category_results"]:
        row["final_score"] = 0
        if row["category_id"] == "se.readiness":
            row["final_score"] = 10
    winner = build_readiness_report(later)
    assert winner["score_summary"]["strongest_area"]["category_id"] == "se.readiness"


def test_gaps_strengths_and_actions_preserve_canonical_order() -> None:
    result = _golden("c03_se_no_language_cap.json")
    report = build_readiness_report(result)
    assert [item["criterion_id"] for item in report["strengths"]] == [
        item["criterion_id"] for item in result["strengths"]
    ]
    assert [item["criterion_id"] for item in report["material_gaps"]] == [
        item["criterion_id"] for item in result["material_gaps"]
    ]
    assert (
        report["score_summary"]["priority_gap"]["criterion_id"]
        == result["material_gaps"][0]["criterion_id"]
    )
    assert [item["action_id"] for item in report["priority_actions"]] == [
        item["action_id"] for item in result["priority_actions"]
    ]
    catalog = {item["action_id"]: item for item in load_action_catalog_v1()["actions"]}
    for action, canonical in zip(
        report["priority_actions"], result["priority_actions"], strict=True
    ):
        expected = catalog[canonical["action_id"]]
        assert action["candidate_instruction"] == expected["candidate_instruction"]
        assert action["required_output"] == expected["required_output"]
        assert action["completion_check"] == expected["completion_check"]
        assert action["action_type"] == expected["action_type"]


def test_action_mismatch_and_unknown_ids_fail_safely() -> None:
    result = _golden("c03_se_no_language_cap.json")
    mismatch = deepcopy(result)
    mismatch["priority_actions"][0]["required_output"] = "not-the-catalogue-output"
    failed = build_readiness_report(mismatch)
    assert failed == {"state": "FAILED", "error_code": ERROR_REPORT_RULESET_INVALID}
    unknown_action = deepcopy(result)
    unknown_action["priority_actions"][0]["action_id"] = "action.v1.does.not.exist"
    assert build_readiness_report(unknown_action)["error_code"] == ERROR_REPORT_RULESET_INVALID
    unknown_band = deepcopy(result)
    unknown_band["band"] = "not_a_band"
    assert build_readiness_report(unknown_band)["error_code"] == ERROR_REPORT_RULESET_INVALID
    unknown_cap = deepcopy(result)
    unknown_cap["overall_caps"] = [{"rule_id": "rubric.v2.unknown.cap", "cap": 10}]
    assert build_readiness_report(unknown_cap)["error_code"] == ERROR_REPORT_RULESET_INVALID


def test_project_recommendation_expands_or_stays_review_required() -> None:
    review = build_readiness_report(_golden("c01_se_full_score.json"))
    assert review["project_recommendation"] == {"status": "REVIEW_REQUIRED"}
    result = _golden("c07_da_no_sql_cap.json")
    report = build_readiness_report(result)
    project = report["project_recommendation"]
    catalog = next(
        item
        for item in load_project_catalog_v1()["projects"]
        if item["project_id"] == result["project_recommendation"]["project_id"]
    )
    assert project["status"] == "RECOMMENDED"
    assert project["project_id"] == catalog["project_id"]
    assert project["title"] == catalog["title"]
    assert project["scenario"] == catalog["scenario"]
    assert project["catalogue_version"] == result["project_recommendation"]["catalogue_version"]
    assert project["required_outputs"] == catalog["required_outputs"]
    mutated = deepcopy(result)
    mutated["project_recommendation"] = {
        **result["project_recommendation"],
        "project_id": "se.project.01_operations_workflow",
    }
    assert build_readiness_report(mutated)["error_code"] == ERROR_REPORT_RULESET_INVALID


def test_criterion_notes_preserved_and_raw_evidence_absent() -> None:
    result = _golden("c03_se_no_language_cap.json")
    report = build_readiness_report(result)
    notes = {item["criterion_id"]: item["evidence_note"] for item in result["criterion_results"]}
    assert len(report["criterion_breakdown"]) == 26
    for row in report["criterion_breakdown"]:
        assert row["evidence_note"] == notes[row["criterion_id"]]
    blob = _dump(report)
    for key in PAID_LEAK_KEYS:
        assert f'"{key}"' not in blob
    assert SECRET_SENTINEL not in blob
    assert "https://" not in blob
    assert "traceback" not in blob.lower()


def test_non_completed_invalid_and_version_mismatch_are_rejected() -> None:
    assert build_readiness_report(None)["error_code"] == ERROR_REPORT_RULESET_INVALID
    result = _golden("c01_se_full_score.json")
    result["status"] = "REVIEW_REQUIRED"
    assert build_readiness_report(result)["error_code"] == ERROR_REPORT_RULESET_INVALID
    mismatch = _golden("c01_se_full_score.json")
    mismatch["contract_version"] = "1.1.0"
    assert build_readiness_report(mismatch)["error_code"] == ERROR_REPORT_RULESET_INVALID
    assert (
        build_readiness_report(_golden("c01_se_full_score.json"), report_version="9.9.9")[
            "error_code"
        ]
        == ERROR_REPORT_VERSION_NOT_FOUND
    )
    broken_copy = deepcopy(load_report_copy_v1())
    broken_copy.pop("evidence_anchor_labels")
    failed = build_readiness_report(_golden("c01_se_full_score.json"), report_copy=broken_copy)
    assert failed["error_code"] == ERROR_REPORT_RULESET_INVALID
    assert "evidence_anchor" not in json.dumps(failed)
    assert SECRET_SENTINEL not in json.dumps(failed)
    completed = _golden("c01_se_full_score.json")
    copy = deepcopy(load_report_copy_v1())
    copy["status"] = "draft"
    assert (
        build_readiness_report(completed, report_copy=copy)["error_code"]
        == ERROR_REPORT_RULESET_INVALID
    )
    copy = deepcopy(load_report_copy_v1())
    copy["report_version"] = "0.0.1"
    assert (
        build_readiness_report(completed, report_copy=copy)["error_code"]
        == ERROR_REPORT_VERSION_NOT_FOUND
    )
    copy = deepcopy(load_report_copy_v1())
    copy["contract_version"] = "1.1.0"
    assert (
        build_readiness_report(completed, report_copy=copy)["error_code"]
        == ERROR_REPORT_RULESET_INVALID
    )
    copy = deepcopy(load_report_copy_v1())
    copy["qualification_route_labels"] = {}
    assert (
        build_readiness_report(completed, report_copy=copy)["error_code"]
        == ERROR_REPORT_RULESET_INVALID
    )
    copy = deepcopy(load_report_copy_v1())
    copy["benchmark"] = {"scope_statement": "ok"}
    assert (
        build_readiness_report(completed, report_copy=copy)["error_code"]
        == ERROR_REPORT_RULESET_INVALID
    )
    assert build_readiness_report(completed, rubric=123)["error_code"] == ERROR_REPORT_BUILD_FAILED


def test_inconsistent_canonical_ids_and_projects_fail_safely() -> None:
    result = _golden("c01_se_full_score.json")
    duplicate = deepcopy(result)
    duplicate["category_results"].append(deepcopy(duplicate["category_results"][0]))
    assert build_readiness_report(duplicate)["error_code"] == ERROR_REPORT_RULESET_INVALID
    points = deepcopy(result)
    points["category_results"][0]["max_points"] = 99
    assert build_readiness_report(points)["error_code"] == ERROR_REPORT_RULESET_INVALID
    criterion = deepcopy(result)
    criterion["criterion_results"][0]["category_id"] = "se.readiness"
    assert build_readiness_report(criterion)["error_code"] == ERROR_REPORT_RULESET_INVALID
    selected = _golden("c07_da_no_sql_cap.json")
    version = deepcopy(selected)
    version["project_recommendation"]["catalogue_version"] = "9.9.9"
    assert build_readiness_report(version)["error_code"] == ERROR_REPORT_RULESET_INVALID
    missing_project = deepcopy(selected)
    missing_project["project_recommendation"]["project_id"] = "da.project.does_not_exist"
    assert build_readiness_report(missing_project)["error_code"] == ERROR_REPORT_RULESET_INVALID
    bad_shape = deepcopy(selected)
    bad_shape["project_recommendation"] = ["not-a-project"]
    assert build_readiness_report(bad_shape)["error_code"] == ERROR_REPORT_RULESET_INVALID


def test_repeated_builds_are_byte_equivalent() -> None:
    result = _golden("c07_da_no_sql_cap.json")
    first = build_readiness_report(result)
    second = build_readiness_report(result)
    assert _dump(first) == _dump(second)
    digest = hashlib.sha256(_dump(first).encode("utf-8")).hexdigest()
    assert hashlib.sha256(_dump(second).encode("utf-8")).hexdigest() == digest


def test_reporting_engine_does_not_import_scorer_or_pipeline() -> None:
    root = Path(__file__).resolve().parents[3] / "app" / "engine" / "reporting"
    text = "".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
    assert "score_assessment" not in text
    assert "run_assessment_pipeline" not in text
    assert "score_frozen_assessment" not in text

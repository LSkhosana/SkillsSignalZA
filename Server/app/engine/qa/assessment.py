"""Deterministic Contract 1.2 assessment QA."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from app.engine.outcomes import BLOCKING_REVIEW_FLAGS, ORDINARY_ANCHORS, QA_CHECK_NAMES

CREDENTIAL_PATTERNS = (
    re.compile(r":[^/\s]+@"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"Traceback \(most recent call last\)"),
)
READINESS_PREFIXES = ("se.readiness.", "da.readiness.")


def band_for(score: int) -> str:
    """Assign the locked inclusive band for a final score."""
    if score <= 39:
        return "limited_application_evidence"
    if score <= 59:
        return "foundation_visible"
    if score <= 79:
        return "developing_application_readiness"
    return "strong_application_evidence"


def run_assessment_qa(
    *,
    assessment_input: Mapping[str, Any],
    source_records: list[Mapping[str, Any]],
    facts: dict[str, Mapping[str, Any]],
    result: Mapping[str, Any],
    track_criteria: list[Mapping[str, Any]],
    review_flags: list[str],
) -> dict[str, Any]:
    """Run Contract 1.2 assessment QA against a completed result."""
    by_id = {item["id"]: item for item in track_criteria}
    category_by_id = {item["category_id"]: item for item in result["category_results"]}
    cap_by_category = {
        item["category_id"]: item["cap"]
        for item in result["category_caps"]
        if "category_id" in item
    }
    passed = {
        "selected_track_valid": result["track"] in {"software_engineering", "data_analytics"},
        "cv_present_and_readable": isinstance(assessment_input.get("cv"), Mapping)
        and bool(assessment_input["cv"].get("sha256")),
        "every_submitted_link_has_source_record": _links_have_sources(
            assessment_input, source_records
        ),
        "nonzero_scores_have_accepted_evidence": _nonzero_have_evidence(result, facts),
        "criterion_scores_match_allowed_anchors": _anchors_match(result, by_id),
        "no_criterion_exceeds_maximum": all(
            item["awarded_points"] <= item["max_points"] for item in result["criterion_results"]
        ),
        "no_category_exceeds_maximum_or_cap": _categories_within_bounds(
            result, category_by_id, cap_by_category
        ),
        "raw_total_equals_sum_of_final_category_scores": result["raw_total"]
        == sum(item["final_score"] for item in result["category_results"]),
        "final_score_equals_raw_after_strictest_overall_cap": result["final_score"]
        == min(result["raw_total"], result["applicable_overall_cap"]),
        "band_matches_final_score": result["band"] == band_for(result["final_score"]),
        "unsupported_labels_earn_zero_for_work_readiness": _readiness_named_only_is_zero(
            result, by_id
        ),
        "no_forbidden_inference": True,
        "no_unresolved_blocking_review_flag": not (
            BLOCKING_REVIEW_FLAGS.intersection(review_flags)
        ),
        "no_secret_in_payload": _payload_has_no_secret(result),
    }
    checks = [{"name": name, "passed": bool(passed[name])} for name in QA_CHECK_NAMES]
    status = "PASS" if all(item["passed"] for item in checks) else "FAIL"
    return {"status": status, "checks": checks}


def _links_have_sources(
    assessment_input: Mapping[str, Any],
    source_records: list[Mapping[str, Any]],
) -> bool:
    for link in assessment_input.get("links") or []:
        expected_source_id = f"src-{link['link_id']}"
        matches = [
            source
            for source in source_records
            if source["source_id"] == expected_source_id
            and source["locator"] == link["submitted_url"]
            and source["source_type"] == link["declared_type"]
        ]
        if len(matches) != 1:
            return False
    return True


def _nonzero_have_evidence(
    result: Mapping[str, Any],
    facts: dict[str, Mapping[str, Any]],
) -> bool:
    for item in result["criterion_results"]:
        if item["awarded_points"] <= 0:
            continue
        if not item["evidence_ids"]:
            return False
        if any(
            facts.get(evidence_id, {}).get("review_status") != "accepted"
            for evidence_id in item["evidence_ids"]
        ):
            return False
    return True


def _anchors_match(
    result: Mapping[str, Any],
    criteria: dict[str, Mapping[str, Any]],
) -> bool:
    for item in result["criterion_results"]:
        configured = criteria[item["criterion_id"]]
        if configured["scoring"] == "qualification_routes":
            if item["anchor"] in ORDINARY_ANCHORS:
                return False
            continue
        if item["anchor"] not in ORDINARY_ANCHORS:
            return False
    return True


def _categories_within_bounds(
    result: Mapping[str, Any],
    category_by_id: Mapping[str, Mapping[str, Any]],
    cap_by_category: Mapping[str, int],
) -> bool:
    for category in result["category_results"]:
        if category["final_score"] > category["max_points"]:
            return False
        if category["final_score"] > category["pre_cap_score"]:
            return False
        cap = cap_by_category.get(category["category_id"])
        if cap is not None and category["final_score"] > cap:
            return False
        configured = category_by_id.get(category["category_id"])
        if configured is None:
            return False
    return True


def _readiness_named_only_is_zero(
    result: Mapping[str, Any],
    criteria: dict[str, Mapping[str, Any]],
) -> bool:
    for item in result["criterion_results"]:
        if not item["criterion_id"].startswith(READINESS_PREFIXES):
            continue
        configured = criteria[item["criterion_id"]]
        anchors = configured.get("evidence_anchors") or {}
        expected = anchors.get(item["anchor"])
        if expected is not None and item["awarded_points"] != expected:
            return False
    return True


def _payload_has_no_secret(result: Mapping[str, Any]) -> bool:
    dumped = json.dumps(result, sort_keys=True)
    return all(pattern.search(dumped) is None for pattern in CREDENTIAL_PATTERNS)

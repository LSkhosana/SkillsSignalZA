"""JSON Schema tests for Package A engine contracts."""

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from app.engine.configuration import RUBRIC_V2_PATH, load_json

SCHEMA_DIR = Path(__file__).resolve().parents[3] / "app" / "schemas"
ASSESSMENT_INPUT_SCHEMA_PATH = SCHEMA_DIR / "assessment_input.schema.json"
EVIDENCE_FACT_SCHEMA_PATH = SCHEMA_DIR / "evidence_fact.schema.json"
ASSESSMENT_RESULT_SCHEMA_PATH = SCHEMA_DIR / "assessment_result.schema.json"
SCORING_CONTEXT_SCHEMA_PATH = SCHEMA_DIR / "scoring_context.schema.json"
SCHEMA_PATHS = (
    ASSESSMENT_INPUT_SCHEMA_PATH,
    EVIDENCE_FACT_SCHEMA_PATH,
    ASSESSMENT_RESULT_SCHEMA_PATH,
    SCORING_CONTEXT_SCHEMA_PATH,
)
DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

VALID_ASSESSMENT_INPUT = {
    "contract_version": "1.1.0",
    "rubric_version": "V2",
    "track": "software_engineering",
    "candidate_ref": "opaque-candidate-id",
    "cv": {
        "document_id": "doc-id",
        "media_type": "application/pdf",
        "sha256": EMPTY_SHA256,
        "original_filename": "candidate-cv.pdf",
    },
    "links": [
        {
            "link_id": "link-1",
            "submitted_url": "https://example.com/candidate-project",
            "declared_type": "project",
        }
    ],
    "submitted_at": "2026-08-21T09:00:00Z",
}

VALID_EVIDENCE_FACT = {
    "evidence_id": "ev-001",
    "source_id": "cv-001",
    "locator": "page 2, Projects",
    "fact_type": "skill_application",
    "subject": "python",
    "explicit_text": "Built a Flask API in Python",
    "evidence_level": "documented",
    "attribution_status": "attributed",
    "rule_id": "extract.explicit-language.v1",
    "review_status": "accepted",
}

APPROVED_RESULT_ANCHORS = (
    "demonstrated",
    "documented",
    "named_only",
    "missing_unverifiable",
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

VALID_ASSESSMENT_RESULT = {
    "assessment_id": "assessment-id",
    "run_id": "run-id",
    "contract_version": "1.1.0",
    "rubric_version": "V2",
    "track": "software_engineering",
    "status": "COMPLETED",
    "assessed_at": "2026-08-21T10:00:00Z",
    "source_snapshot": {
        "cv_hash": EMPTY_SHA256,
        "link_content_hashes": [],
    },
    "category_results": [
        {
            "category_id": "se.core",
            "max_points": 35,
            "pre_cap_score": 0,
            "final_score": 0,
        }
    ],
    "criterion_results": [
        {
            "criterion_id": "se.core.programming_language",
            "category_id": "se.core",
            "max_points": 12,
            "anchor": "documented",
            "awarded_points": 9,
            "evidence_ids": ["ev-001"],
            "rule_ids": ["rubric.v2.se.core.programming_language"],
            "evidence_note": "Python application described in CV project entry.",
            "flags": [],
        }
    ],
    "category_caps": [],
    "raw_total": 82,
    "overall_caps": [
        {
            "rule_id": "rubric.v2.se.cap.no_language",
            "cap": 59,
        }
    ],
    "applicable_overall_cap": 59,
    "final_score": 59,
    "band": "foundation_visible",
    "strengths": [],
    "material_gaps": [],
    "priority_actions": [],
    "project_recommendation": None,
    "flags": [],
    "qa": {
        "status": "PASS",
        "checks": [],
    },
}

VALID_EVIDENCE_PRIORITY_ACTION = {
    "action_id": "action.v1.se.core.programming_language.documented",
    "criterion_id": "se.core.programming_language",
    "current_anchor": "documented",
    "target_anchor": "demonstrated",
    "required_output": "Accessible source code plus a language-specific implementation note.",
    "completion_check": "The language is named explicitly and working code is locatable.",
    "priority_order": 1,
}

VALID_SCORING_CONTEXT = {
    "contract_version": "1.2.0",
    "rubric_version": "V2",
    "track": "software_engineering",
    "criterion_bindings": [
        {
            "criterion_id": "se.alignment.qualification",
            "anchor": "se.qual.none",
            "evidence_ids": [],
        }
    ],
    "rule_triggers": [],
    "review_flags": [],
    "project_exclusion_ids": [],
}

VALID_QUALIFICATION_PRIORITY_ACTION = {
    "action_id": "action.v1.se.alignment.qualification.completed",
    "criterion_id": "se.alignment.qualification",
    "current_anchor": "se.qual.completed",
    "target_anchor": "se.qual.completed",
    "required_output": "Qualification name, institution, completion status, and year.",
    "completion_check": "The wording matches the submitted evidence without implied skills.",
    "priority_order": 1,
}


def _validator(schema: dict[str, Any]) -> Draft202012Validator:
    return Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)


def _assert_valid(schema: dict[str, Any], instance: object) -> None:
    _validator(schema).validate(instance)


def _assert_invalid(schema: dict[str, Any], instance: object) -> None:
    with pytest.raises(ValidationError):
        _assert_valid(schema, instance)


@pytest.fixture(scope="module")
def assessment_input_schema() -> dict[str, Any]:
    return load_json(ASSESSMENT_INPUT_SCHEMA_PATH)


@pytest.fixture(scope="module")
def evidence_fact_schema() -> dict[str, Any]:
    return load_json(EVIDENCE_FACT_SCHEMA_PATH)


@pytest.fixture(scope="module")
def assessment_result_schema() -> dict[str, Any]:
    return load_json(ASSESSMENT_RESULT_SCHEMA_PATH)


@pytest.fixture(scope="module")
def scoring_context_schema() -> dict[str, Any]:
    return load_json(SCORING_CONTEXT_SCHEMA_PATH)


def test_engine_json_files_parse() -> None:
    for path in (RUBRIC_V2_PATH, *SCHEMA_PATHS):
        document = load_json(path)
        assert isinstance(document, dict)


def test_schemas_are_valid_draft_2020_12() -> None:
    for path in SCHEMA_PATHS:
        schema = load_json(path)
        assert schema["$schema"] == DRAFT_2020_12
        Draft202012Validator.check_schema(schema)


def test_valid_assessment_input_passes(assessment_input_schema: dict[str, Any]) -> None:
    _assert_valid(assessment_input_schema, VALID_ASSESSMENT_INPUT)


def test_invalid_track_input_fails(assessment_input_schema: dict[str, Any]) -> None:
    payload = deepcopy(VALID_ASSESSMENT_INPUT)
    payload["track"] = "product_management"
    _assert_invalid(assessment_input_schema, payload)


def test_missing_cv_input_fails(assessment_input_schema: dict[str, Any]) -> None:
    payload = deepcopy(VALID_ASSESSMENT_INPUT)
    del payload["cv"]
    _assert_invalid(assessment_input_schema, payload)


def test_unsupported_cv_media_type_fails(assessment_input_schema: dict[str, Any]) -> None:
    payload = deepcopy(VALID_ASSESSMENT_INPUT)
    payload["cv"]["media_type"] = "image/png"
    _assert_invalid(assessment_input_schema, payload)


def test_valid_evidence_fact_passes(evidence_fact_schema: dict[str, Any]) -> None:
    _assert_valid(evidence_fact_schema, VALID_EVIDENCE_FACT)


def test_unrecognized_evidence_level_fails(evidence_fact_schema: dict[str, Any]) -> None:
    payload = deepcopy(VALID_EVIDENCE_FACT)
    payload["evidence_level"] = "strong"
    _assert_invalid(evidence_fact_schema, payload)


def test_unrecognized_fact_type_fails(evidence_fact_schema: dict[str, Any]) -> None:
    payload = deepcopy(VALID_EVIDENCE_FACT)
    payload["fact_type"] = "inferred_skill"
    _assert_invalid(evidence_fact_schema, payload)


def test_valid_completed_result_passes(assessment_result_schema: dict[str, Any]) -> None:
    assert VALID_ASSESSMENT_RESULT["status"] == "COMPLETED"
    _assert_valid(assessment_result_schema, VALID_ASSESSMENT_RESULT)


def test_not_scorable_cannot_validate_as_scored_result(
    assessment_result_schema: dict[str, Any],
) -> None:
    payload = deepcopy(VALID_ASSESSMENT_RESULT)
    payload["status"] = "NOT_SCORABLE"
    _assert_invalid(assessment_result_schema, payload)


def test_failed_cannot_validate_as_scored_result(
    assessment_result_schema: dict[str, Any],
) -> None:
    payload = deepcopy(VALID_ASSESSMENT_RESULT)
    payload["status"] = "FAILED"
    _assert_invalid(assessment_result_schema, payload)


def test_unfinished_status_cannot_validate_as_scored_result(
    assessment_result_schema: dict[str, Any],
) -> None:
    payload = deepcopy(VALID_ASSESSMENT_RESULT)
    payload["status"] = "SCORING"
    _assert_invalid(assessment_result_schema, payload)


def test_unknown_anchor_fails(assessment_result_schema: dict[str, Any]) -> None:
    payload = deepcopy(VALID_ASSESSMENT_RESULT)
    payload["criterion_results"][0]["anchor"] = "advanced"
    _assert_invalid(assessment_result_schema, payload)


@pytest.mark.parametrize("anchor", APPROVED_RESULT_ANCHORS)
def test_approved_evidence_and_qualification_anchors_pass(
    assessment_result_schema: dict[str, Any],
    anchor: str,
) -> None:
    payload = deepcopy(VALID_ASSESSMENT_RESULT)
    payload["criterion_results"][0]["anchor"] = anchor
    _assert_valid(assessment_result_schema, payload)


def test_evidence_priority_action_validates(assessment_result_schema: dict[str, Any]) -> None:
    payload = deepcopy(VALID_ASSESSMENT_RESULT)
    payload["priority_actions"] = [VALID_EVIDENCE_PRIORITY_ACTION]
    _assert_valid(assessment_result_schema, payload)


def test_qualification_priority_action_validates(assessment_result_schema: dict[str, Any]) -> None:
    payload = deepcopy(VALID_ASSESSMENT_RESULT)
    payload["priority_actions"] = [VALID_QUALIFICATION_PRIORITY_ACTION]
    _assert_valid(assessment_result_schema, payload)


@pytest.mark.parametrize("anchor", APPROVED_RESULT_ANCHORS)
def test_approved_priority_action_anchors_pass(
    assessment_result_schema: dict[str, Any],
    anchor: str,
) -> None:
    payload = deepcopy(VALID_ASSESSMENT_RESULT)
    action = deepcopy(VALID_EVIDENCE_PRIORITY_ACTION)
    action["current_anchor"] = anchor
    action["target_anchor"] = anchor
    payload["priority_actions"] = [action]
    _assert_valid(assessment_result_schema, payload)


def test_unknown_priority_action_anchor_fails(assessment_result_schema: dict[str, Any]) -> None:
    payload = deepcopy(VALID_ASSESSMENT_RESULT)
    action = deepcopy(VALID_EVIDENCE_PRIORITY_ACTION)
    action["current_anchor"] = "advanced"
    payload["priority_actions"] = [action]
    _assert_invalid(assessment_result_schema, payload)


def test_legacy_priority_action_evidence_level_fields_fail(
    assessment_result_schema: dict[str, Any],
) -> None:
    payload = deepcopy(VALID_ASSESSMENT_RESULT)
    action = {
        "action_id": VALID_EVIDENCE_PRIORITY_ACTION["action_id"],
        "criterion_id": VALID_EVIDENCE_PRIORITY_ACTION["criterion_id"],
        "current_evidence_level": "documented",
        "target_evidence_level": "demonstrated",
        "required_output": VALID_EVIDENCE_PRIORITY_ACTION["required_output"],
        "completion_check": VALID_EVIDENCE_PRIORITY_ACTION["completion_check"],
        "priority_order": 1,
    }
    payload["priority_actions"] = [action]
    _assert_invalid(assessment_result_schema, payload)


def test_result_score_over_100_fails(assessment_result_schema: dict[str, Any]) -> None:
    payload = deepcopy(VALID_ASSESSMENT_RESULT)
    payload["final_score"] = 101
    _assert_invalid(assessment_result_schema, payload)


def test_non_integer_score_fails(assessment_result_schema: dict[str, Any]) -> None:
    payload = deepcopy(VALID_ASSESSMENT_RESULT)
    payload["final_score"] = 59.5
    _assert_invalid(assessment_result_schema, payload)


def test_valid_scoring_context_passes(scoring_context_schema: dict[str, Any]) -> None:
    _assert_valid(scoring_context_schema, VALID_SCORING_CONTEXT)


def test_unknown_scoring_context_property_fails(scoring_context_schema: dict[str, Any]) -> None:
    payload = deepcopy(VALID_SCORING_CONTEXT)
    payload["inferred_from_expected"] = True
    _assert_invalid(scoring_context_schema, payload)


def test_unknown_scoring_context_binding_property_fails(
    scoring_context_schema: dict[str, Any],
) -> None:
    payload = deepcopy(VALID_SCORING_CONTEXT)
    payload["criterion_bindings"][0]["awarded_points"] = 10
    _assert_invalid(scoring_context_schema, payload)


def test_wrong_scoring_context_contract_version_fails(
    scoring_context_schema: dict[str, Any],
) -> None:
    payload = deepcopy(VALID_SCORING_CONTEXT)
    payload["contract_version"] = "1.1.0"
    _assert_invalid(scoring_context_schema, payload)


def test_unexpected_closed_object_properties_fail(
    assessment_input_schema: dict[str, Any],
    evidence_fact_schema: dict[str, Any],
    assessment_result_schema: dict[str, Any],
    scoring_context_schema: dict[str, Any],
) -> None:
    extra_input = deepcopy(VALID_ASSESSMENT_INPUT)
    extra_input["age"] = 21
    extra_cv = deepcopy(VALID_ASSESSMENT_INPUT)
    extra_cv["cv"]["full_name"] = "not-a-scoring-input"
    extra_fact = deepcopy(VALID_EVIDENCE_FACT)
    extra_fact["inferred_parent_skill"] = "python"
    extra_result = deepcopy(VALID_ASSESSMENT_RESULT)
    extra_result["hiring_probability"] = 0.8
    extra_context = deepcopy(VALID_SCORING_CONTEXT)
    extra_context["filename"] = "c01_se_full_score.json"
    _assert_invalid(assessment_input_schema, extra_input)
    _assert_invalid(assessment_input_schema, extra_cv)
    _assert_invalid(evidence_fact_schema, extra_fact)
    _assert_invalid(assessment_result_schema, extra_result)
    _assert_invalid(scoring_context_schema, extra_context)

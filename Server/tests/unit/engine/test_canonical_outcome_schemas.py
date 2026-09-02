"""Negative schema tests for Packages I–K canonical outcomes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema.exceptions import ValidationError

from app.engine.context import assemble_scoring_context
from app.engine.schema_registry import draft_validator

EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
GOLDEN_RESULT_PATH = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "golden_candidates"
    / "c22_secret_exclusion.json"
)


def _scoring_context() -> dict:
    return assemble_scoring_context(
        track="software_engineering",
        evidence_facts=[],
        source_records=[
            {
                "source_id": "src-cv",
                "source_type": "cv",
                "submitted_by_candidate": True,
                "access_status": "accessible",
                "ownership_status": "attributed",
                "retrieved_at": "2026-09-02T08:00:00Z",
                "content_hash": EMPTY_SHA256,
                "extractor_version": "extract.cv.v1",
                "locator": "page 1",
                "notes": "cv",
            }
        ],
    )["scoring_context"]


def _i_base(**overrides: object) -> dict:
    payload = {
        "state": "COMPLETED",
        "error_code": None,
        "classifier_version": "classify.higher.v1",
        "contract_version": "1.2.0",
        "rubric_version": "V2",
        "track": "software_engineering",
        "source_records": [],
        "evidence_facts": [],
        "review_flags": [],
    }
    payload.update(overrides)
    return payload


def _j_base(**overrides: object) -> dict:
    payload = {
        "state": "COMPLETED",
        "error_code": None,
        "assembler_version": "assemble.context.v1",
        "contract_version": "1.2.0",
        "rubric_version": "V2",
        "track": "software_engineering",
        "scoring_context": _scoring_context(),
        "review_flags": [],
    }
    payload.update(overrides)
    return payload


def _k_base(**overrides: object) -> dict:
    payload = {
        "state": "COMPLETED",
        "error_code": None,
        "pipeline_version": "assessment.pipeline.v1",
        "assessment_id": "assessment-1",
        "run_id": "run-1",
        "contract_version": "1.2.0",
        "rubric_version": "V2",
        "track": "software_engineering",
        "assessment_result": json.loads(GOLDEN_RESULT_PATH.read_text(encoding="utf-8"))["expected"][
            "assessment_result"
        ],
        "source_records": [],
        "evidence_facts": [],
        "scoring_context": _scoring_context(),
        "review_flags": [],
        "stages": ["validate_input"],
    }
    payload.update(overrides)
    return payload


def test_canonical_completed_payloads_are_accepted() -> None:
    draft_validator("higher_order_classification.schema.json").validate(_i_base())
    draft_validator("scoring_context_assembly.schema.json").validate(_j_base())
    draft_validator("assessment_pipeline.schema.json").validate(_k_base())


def test_package_i_rejects_impossible_payloads() -> None:
    validator = draft_validator("higher_order_classification.schema.json")
    with pytest.raises(ValidationError):
        validator.validate(_i_base(state="COMPLETED", error_code="OWNERSHIP_UNCLEAR"))
    with pytest.raises(ValidationError):
        validator.validate(_i_base(state="REVIEW_REQUIRED", error_code=None, review_flags=[]))
    with pytest.raises(ValidationError):
        validator.validate(
            _i_base(
                state="HIGHER_ORDER_CLASSIFICATION_FAILED",
                error_code="SOURCE_MISMATCH",
                evidence_facts=[
                    {
                        "evidence_id": "ev-0001",
                        "source_id": "src-cv",
                        "locator": "page 1",
                        "fact_type": "skill_name",
                        "subject": "python",
                        "explicit_text": "Python",
                        "evidence_level": "named_only",
                        "attribution_status": "attributed",
                        "rule_id": "normalize.v1.skill.python",
                        "review_status": "accepted",
                    }
                ],
            )
        )
    with pytest.raises(ValidationError):
        validator.validate(
            _i_base(evidence_facts=[{"evidence_id": "ev-0001", "subject": "python"}])
        )


def test_package_j_rejects_impossible_payloads() -> None:
    validator = draft_validator("scoring_context_assembly.schema.json")
    with pytest.raises(ValidationError):
        validator.validate(_j_base(state="COMPLETED", error_code="REVIEW_REQUIRED"))
    with pytest.raises(ValidationError):
        validator.validate(
            _j_base(state="REVIEW_REQUIRED", error_code="OWNERSHIP_UNCLEAR", review_flags=[])
        )
    with pytest.raises(ValidationError):
        validator.validate(_j_base(scoring_context=None))
    with pytest.raises(ValidationError):
        validator.validate(
            _j_base(
                state="SCORING_CONTEXT_ASSEMBLY_FAILED",
                error_code="UNKNOWN_SUBJECT",
                scoring_context=_scoring_context(),
            )
        )


def test_package_k_rejects_impossible_payloads() -> None:
    validator = draft_validator("assessment_pipeline.schema.json")
    with pytest.raises(ValidationError):
        validator.validate(_k_base(assessment_result=None))
    with pytest.raises(ValidationError):
        validator.validate(_k_base(scoring_context=None))
    with pytest.raises(ValidationError):
        validator.validate(_k_base(error_code="COMPLETED"))
    with pytest.raises(ValidationError):
        validator.validate(_k_base(review_flags=["OWNERSHIP_UNCLEAR"]))
    with pytest.raises(ValidationError):
        validator.validate(
            _k_base(
                state="REVIEW_REQUIRED",
                error_code="REVIEW_REQUIRED",
                assessment_result={"status": "COMPLETED"},
                review_flags=["OWNERSHIP_UNCLEAR"],
            )
        )
    with pytest.raises(ValidationError):
        validator.validate(
            _k_base(
                state="REVIEW_REQUIRED",
                error_code="REVIEW_REQUIRED",
                assessment_result=None,
                review_flags=[],
            )
        )
    with pytest.raises(ValidationError):
        validator.validate(
            _k_base(
                state="NOT_SCORABLE",
                error_code="CV_UNREADABLE",
                assessment_result={"status": "COMPLETED"},
            )
        )
    with pytest.raises(ValidationError):
        validator.validate(
            _k_base(
                state="ASSESSMENT_PIPELINE_FAILED",
                error_code=None,
                assessment_result=None,
            )
        )

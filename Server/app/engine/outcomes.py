"""Domain outcomes returned by the deterministic scoring engine."""

from __future__ import annotations

from typing import Any, Literal

EngineState = Literal[
    "COMPLETED",
    "REVIEW_REQUIRED",
    "INPUT_INVALID",
    "TRACK_INVALID",
    "RULESET_NOT_FOUND",
    "RULESET_INVALID",
    "QA_FAILED",
    "FAILED",
]

REVIEW_SENTINEL = "PROJECT_RECOMMENDATION_REVIEW_REQUIRED"
BLOCKING_REVIEW_FLAGS = frozenset(
    {
        "TRACK_MISMATCH",
        "MATERIAL_SOURCE_CONTRADICTION",
        "OWNERSHIP_UNCLEAR",
        "AUTHENTICITY_UNCLEAR",
        "MATERIAL_CLASSIFICATION_AMBIGUITY",
    }
)
ORDINARY_ANCHORS = frozenset({"demonstrated", "documented", "named_only", "missing_unverifiable"})
QUALIFICATION_CRITERIA = {
    "software_engineering": "se.alignment.qualification",
    "data_analytics": "da.alignment.qualification",
}
NONE_ROUTES = {
    "software_engineering": "se.qual.none",
    "data_analytics": "da.qual.none",
}
PROJECT_SOURCE_TYPES = frozenset(
    {
        "repository",
        "portfolio",
        "project",
        "deployed_project",
        "kaggle",
        "dashboard",
        "other_professional",
    }
)
QA_CHECK_NAMES = (
    "selected_track_valid",
    "cv_present_and_readable",
    "every_submitted_link_has_source_record",
    "nonzero_scores_have_accepted_evidence",
    "criterion_scores_match_allowed_anchors",
    "no_criterion_exceeds_maximum",
    "no_category_exceeds_maximum_or_cap",
    "raw_total_equals_sum_of_final_category_scores",
    "final_score_equals_raw_after_strictest_overall_cap",
    "band_matches_final_score",
    "unsupported_labels_earn_zero_for_work_readiness",
    "no_forbidden_inference",
    "no_unresolved_blocking_review_flag",
    "no_secret_in_payload",
)


def engine_outcome(
    state: EngineState,
    *,
    error_code: str | None = None,
    assessment_result: dict[str, Any] | None = None,
    flags: list[str] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Return a canonical non-HTTP scoring outcome."""
    raw_present = assessment_result is not None
    outcome: dict[str, Any] = {
        "state": state,
        "error_code": error_code or (None if state == "COMPLETED" else state),
        "assessment_result": assessment_result,
        "flags": list(flags or []),
        "raw_score_present": raw_present,
        "final_score_present": raw_present,
        "band_present": raw_present,
    }
    outcome.update(extra)
    return outcome

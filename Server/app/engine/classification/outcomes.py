"""Canonical Package I higher-order classification outcomes."""

from __future__ import annotations

from typing import Any, Literal

from app.engine.outcomes import BLOCKING_REVIEW_FLAGS

ClassificationState = Literal["COMPLETED", "REVIEW_REQUIRED", "HIGHER_ORDER_CLASSIFICATION_FAILED"]

CLASSIFIER_VERSION = "classify.higher.v1"
CONTRACT_VERSION = "1.2.0"
RUBRIC_VERSION = "V2"
APPROVED_TRACKS = frozenset({"software_engineering", "data_analytics"})
SOURCE_TYPE_CV = "cv"
ACCESSIBLE = "accessible"
FLAG_ORDER = (
    "TRACK_MISMATCH",
    "MATERIAL_SOURCE_CONTRADICTION",
    "OWNERSHIP_UNCLEAR",
    "AUTHENTICITY_UNCLEAR",
    "MATERIAL_CLASSIFICATION_AMBIGUITY",
)
ERROR_INVALID_TRACK = "INVALID_TRACK"
ERROR_INVALID_NORMALIZATION = "INVALID_NORMALIZATION"
ERROR_NORMALIZATION_FAILED = "NORMALIZATION_FAILED"
ERROR_INVALID_CV_EXTRACTION = "INVALID_CV_EXTRACTION"
ERROR_INVALID_LINK_RETRIEVAL = "INVALID_LINK_RETRIEVAL"
ERROR_RULESET_INVALID = "RULESET_INVALID"
ERROR_CLASSIFIER_EXCEPTION = "CLASSIFIER_EXCEPTION"
ERROR_DUPLICATE_EVIDENCE_ID = "DUPLICATE_EVIDENCE_ID"
ERROR_INVALID_EVIDENCE_FACT = "INVALID_EVIDENCE_FACT"
ERROR_SOURCE_MISMATCH = "SOURCE_MISMATCH"
ERROR_UNKNOWN_SOURCE = "UNKNOWN_SOURCE"
ERROR_DUPLICATE_SOURCE_ID = "DUPLICATE_SOURCE_ID"


class ClassificationFailure(Exception):
    """Safe named Package I failure."""

    def __init__(self, error_code: str, track: str) -> None:
        self.error_code = error_code
        self.track = track
        super().__init__(error_code)


def canonical_outcome(
    *,
    state: ClassificationState,
    error_code: str | None,
    track: str,
    source_records: list[dict[str, Any]],
    evidence_facts: list[dict[str, Any]],
    review_flags: list[str],
) -> dict[str, Any]:
    """Return a schema-shaped Package I outcome."""
    return {
        "state": state,
        "error_code": error_code,
        "classifier_version": CLASSIFIER_VERSION,
        "contract_version": CONTRACT_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "track": track,
        "source_records": source_records,
        "evidence_facts": evidence_facts,
        "review_flags": review_flags,
    }


def failed_outcome(error_code: str, *, track: str) -> dict[str, Any]:
    """Return a safe non-score classification failure."""
    return canonical_outcome(
        state="HIGHER_ORDER_CLASSIFICATION_FAILED",
        error_code=error_code,
        track=track,
        source_records=[],
        evidence_facts=[],
        review_flags=[],
    )


def ordered_unique_flags(flags: list[str]) -> list[str]:
    """Return blocking/review flags without duplicates, in canonical order."""
    present = {flag for flag in flags if flag}
    ordered = [flag for flag in FLAG_ORDER if flag in present]
    extras = [flag for flag in flags if flag and flag not in FLAG_ORDER and flag in present]
    seen: set[str] = set()
    rest: list[str] = []
    for flag in extras:
        if flag not in seen:
            seen.add(flag)
            rest.append(flag)
    return ordered + rest


def review_state(flags: list[str]) -> tuple[ClassificationState, str | None]:
    """Return COMPLETED or REVIEW_REQUIRED from blocking flags."""
    blocking = [flag for flag in flags if flag in BLOCKING_REVIEW_FLAGS]
    if blocking:
        return "REVIEW_REQUIRED", blocking[0]
    return "COMPLETED", None

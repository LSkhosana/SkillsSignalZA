"""Canonical Package H evidence-normalization outcomes, limits, and error codes."""

from __future__ import annotations

from typing import Any, Literal

NormalizationState = Literal["COMPLETED", "REVIEW_REQUIRED", "EVIDENCE_NORMALIZATION_FAILED"]

NORMALIZER_VERSION = "normalize.evidence.v1"
CONTRACT_VERSION = "1.2.0"
RUBRIC_VERSION = "V2"
APPROVED_TRACKS = frozenset({"software_engineering", "data_analytics"})
MAX_EVIDENCE_FACTS = 5000
NAMED_ONLY_BOUNDED_CHARS = 240
REVIEW_FLAG_OWNERSHIP_UNCLEAR = "OWNERSHIP_UNCLEAR"
OWNERSHIP_VALUES = frozenset({"attributed", "unclear", "conflicting"})
ACCESSIBLE = "accessible"
SOURCE_TYPE_CV = "cv"

ERROR_INVALID_TRACK = "INVALID_TRACK"
ERROR_INVALID_CV_EXTRACTION = "INVALID_CV_EXTRACTION"
ERROR_CV_NOT_EXTRACTABLE = "CV_NOT_EXTRACTABLE"
ERROR_INVALID_LINK_RETRIEVAL = "INVALID_LINK_RETRIEVAL"
ERROR_DUPLICATE_SOURCE_ID = "DUPLICATE_SOURCE_ID"
ERROR_MALFORMED_SOURCE_STRUCTURE = "MALFORMED_SOURCE_STRUCTURE"
ERROR_RULESET_INVALID = "RULESET_INVALID"
ERROR_FACT_LIMIT_EXCEEDED = "FACT_LIMIT_EXCEEDED"
ERROR_CLASSIFIER_EXCEPTION = "CLASSIFIER_EXCEPTION"


class NormalizationFailure(Exception):
    """Safe, named normalization failure without candidate payload."""

    def __init__(self, error_code: str, track: str) -> None:
        self.error_code = error_code
        self.track = track
        super().__init__(error_code)


def canonical_outcome(
    *,
    state: NormalizationState,
    error_code: str | None,
    track: str,
    source_records: list[dict[str, Any]],
    evidence_facts: list[dict[str, Any]],
    review_flags: list[str],
) -> dict[str, Any]:
    """Return a schema-shaped Package H outcome."""
    return {
        "state": state,
        "error_code": error_code,
        "normalizer_version": NORMALIZER_VERSION,
        "contract_version": CONTRACT_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "track": track,
        "source_records": source_records,
        "evidence_facts": evidence_facts,
        "review_flags": review_flags,
    }


def failed_outcome(error_code: str, *, track: str) -> dict[str, Any]:
    """Return a safe non-score normalization failure."""
    return canonical_outcome(
        state="EVIDENCE_NORMALIZATION_FAILED",
        error_code=error_code,
        track=track,
        source_records=[],
        evidence_facts=[],
        review_flags=[],
    )

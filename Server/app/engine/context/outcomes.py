"""Canonical Package J scoring-context assembly outcomes."""

from __future__ import annotations

from typing import Any, Literal

from app.engine.outcomes import BLOCKING_REVIEW_FLAGS

AssemblyState = Literal["COMPLETED", "REVIEW_REQUIRED", "SCORING_CONTEXT_ASSEMBLY_FAILED"]

ASSEMBLER_VERSION = "assemble.context.v1"
CONTRACT_VERSION = "1.2.0"
RUBRIC_VERSION = "V2"
APPROVED_TRACKS = frozenset({"software_engineering", "data_analytics"})
ERROR_INVALID_TRACK = "INVALID_TRACK"
ERROR_INVALID_EVIDENCE_FACT = "INVALID_EVIDENCE_FACT"
ERROR_DUPLICATE_EVIDENCE_ID = "DUPLICATE_EVIDENCE_ID"
ERROR_DUPLICATE_SOURCE_ID = "DUPLICATE_SOURCE_ID"
ERROR_UNKNOWN_SOURCE = "UNKNOWN_SOURCE"
ERROR_UNKNOWN_FACT_TYPE = "UNKNOWN_FACT_TYPE"
ERROR_RULESET_INVALID = "RULESET_INVALID"
ERROR_UNRECOGNIZED_REVIEW_FLAG = "UNRECOGNIZED_REVIEW_FLAG"
ERROR_IMPOSSIBLE_QUALIFICATION = "IMPOSSIBLE_QUALIFICATION"
ERROR_CONTEXT_INVALID = "CONTEXT_INVALID"
ERROR_ASSEMBLER_EXCEPTION = "ASSEMBLER_EXCEPTION"
LEVEL_RANK = {"demonstrated": 3, "documented": 2, "named_only": 1, "missing_unverifiable": 0}
QUAL_RANK = {
    "completed": 6,
    "in_progress": 5,
    "experience": 4,
    "bootcamp": 3,
    "adjacent": 2,
    "none": 1,
}


class AssemblyFailure(Exception):
    """Safe named Package J failure."""

    def __init__(self, error_code: str, track: str) -> None:
        self.error_code = error_code
        self.track = track
        super().__init__(error_code)


def canonical_outcome(
    *,
    state: AssemblyState,
    error_code: str | None,
    track: str,
    scoring_context: dict[str, Any] | None,
    review_flags: list[str],
) -> dict[str, Any]:
    """Return a schema-shaped Package J outcome."""
    return {
        "state": state,
        "error_code": error_code,
        "assembler_version": ASSEMBLER_VERSION,
        "contract_version": CONTRACT_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "track": track,
        "scoring_context": scoring_context,
        "review_flags": review_flags,
    }


def failed_outcome(error_code: str, *, track: str) -> dict[str, Any]:
    """Return a safe non-score assembly failure."""
    return canonical_outcome(
        state="SCORING_CONTEXT_ASSEMBLY_FAILED",
        error_code=error_code,
        track=track,
        scoring_context=None,
        review_flags=[],
    )


def review_state(flags: list[str]) -> tuple[AssemblyState, str | None]:
    """Return COMPLETED or REVIEW_REQUIRED from blocking flags."""
    blocking = [flag for flag in flags if flag in BLOCKING_REVIEW_FLAGS]
    if blocking:
        return "REVIEW_REQUIRED", blocking[0]
    return "COMPLETED", None

"""In-memory CV-first assessment pipeline (Package K)."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from copy import deepcopy
from datetime import datetime
from typing import Any

from jsonschema.exceptions import ValidationError

from app.engine.classification import classify_higher_order_evidence
from app.engine.context import assemble_scoring_context
from app.engine.evidence import normalize_evidence
from app.engine.extraction import extract_cv, normalize_submitted_url, retrieve_candidate_link
from app.engine.schema_registry import draft_validator
from app.engine.scoring import score_assessment

PIPELINE_VERSION = "assessment.pipeline.v1"
CONTRACT_VERSION = "1.2.0"
RUBRIC_VERSION = "V2"
ERROR_INVALID_ASSESSMENT_INPUT = "INVALID_ASSESSMENT_INPUT"
ERROR_CV_MISSING = "CV_MISSING"
ERROR_CV_HASH_MISMATCH = "CV_HASH_MISMATCH"
ERROR_CV_UNREADABLE = "CV_UNREADABLE"
ERROR_LINK_TYPE_AMBIGUITY = "MATERIAL_CLASSIFICATION_AMBIGUITY"
ERROR_NORMALIZATION_FAILED = "NORMALIZATION_FAILED"
ERROR_CLASSIFICATION_FAILED = "CLASSIFICATION_FAILED"
ERROR_CONTEXT_ASSEMBLY_FAILED = "CONTEXT_ASSEMBLY_FAILED"
ERROR_ORCHESTRATION_EXCEPTION = "ORCHESTRATION_EXCEPTION"


def run_assessment_pipeline(
    *,
    assessment_input: dict[str, Any],
    cv_file_bytes: bytes,
    assessment_id: str,
    run_id: str,
    assessed_at: str,
    retrieve_link: Callable[..., dict[str, Any]] = retrieve_candidate_link,
) -> dict[str, Any]:
    """Run F -> G -> H -> I -> J -> scoring in memory without persistence."""
    try:
        return _run(
            assessment_input=assessment_input,
            cv_file_bytes=cv_file_bytes,
            assessment_id=assessment_id,
            run_id=run_id,
            assessed_at=assessed_at,
            retrieve_link=retrieve_link,
        )
    except PipelineHalt as exc:
        return _pipeline_outcome(
            state=exc.state,
            error_code=exc.error_code,
            assessment_id=assessment_id if isinstance(assessment_id, str) else "",
            run_id=run_id if isinstance(run_id, str) else "",
            track=exc.track,
            assessment_result=None,
            source_records=exc.source_records,
            evidence_facts=exc.evidence_facts,
            scoring_context=exc.scoring_context,
            review_flags=exc.review_flags,
            stages=exc.stages,
        )
    except Exception:
        return _pipeline_outcome(
            state="ASSESSMENT_PIPELINE_FAILED",
            error_code=ERROR_ORCHESTRATION_EXCEPTION,
            assessment_id=assessment_id if isinstance(assessment_id, str) else "",
            run_id=run_id if isinstance(run_id, str) else "",
            track="",
            assessment_result=None,
            source_records=[],
            evidence_facts=[],
            scoring_context=None,
            review_flags=[],
            stages=[],
        )


class PipelineHalt(Exception):
    """Named pipeline stop without leaking candidate payload."""

    def __init__(
        self,
        state: str,
        error_code: str,
        *,
        track: str = "",
        source_records: list[dict[str, Any]] | None = None,
        evidence_facts: list[dict[str, Any]] | None = None,
        scoring_context: dict[str, Any] | None = None,
        review_flags: list[str] | None = None,
        stages: list[str] | None = None,
    ) -> None:
        self.state = state
        self.error_code = error_code
        self.track = track
        self.source_records = source_records or []
        self.evidence_facts = evidence_facts or []
        self.scoring_context = scoring_context
        self.review_flags = review_flags or []
        self.stages = stages or []
        super().__init__(error_code)


def _run(
    *,
    assessment_input: object,
    cv_file_bytes: object,
    assessment_id: object,
    run_id: object,
    assessed_at: object,
    retrieve_link: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    stages: list[str] = []
    if not _valid_identity(assessment_id, run_id, assessed_at):
        raise PipelineHalt("ASSESSMENT_PIPELINE_FAILED", ERROR_INVALID_ASSESSMENT_INPUT)
    if not isinstance(assessment_input, dict):
        raise PipelineHalt("ASSESSMENT_PIPELINE_FAILED", ERROR_INVALID_ASSESSMENT_INPUT)
    try:
        draft_validator("assessment_input.schema.json").validate(assessment_input)
    except (ValidationError, TypeError, ValueError):
        raise PipelineHalt("ASSESSMENT_PIPELINE_FAILED", ERROR_INVALID_ASSESSMENT_INPUT) from None
    stages.append("validate_input")
    track = str(assessment_input["track"])
    if not isinstance(cv_file_bytes, (bytes, bytearray)):
        raise PipelineHalt("NOT_SCORABLE", ERROR_CV_MISSING, track=track, stages=stages)
    digest = hashlib.sha256(bytes(cv_file_bytes)).hexdigest()
    declared = str(assessment_input["cv"]["sha256"]).lower()
    if digest != declared:
        raise PipelineHalt(
            "ASSESSMENT_PIPELINE_FAILED", ERROR_CV_HASH_MISMATCH, track=track, stages=stages
        )
    stages.append("verify_cv_hash")
    cv_outcome = extract_cv(
        bytes(cv_file_bytes),
        document_id=str(assessment_input["cv"]["document_id"]),
        original_filename=str(assessment_input["cv"]["original_filename"]),
        declared_media_type=str(assessment_input["cv"]["media_type"]),
        extracted_at=str(assessed_at),
    )
    stages.append("extract_cv")
    if cv_outcome.get("state") != "COMPLETED":
        raise PipelineHalt("NOT_SCORABLE", ERROR_CV_UNREADABLE, track=track, stages=stages)
    if str(cv_outcome["document"].get("sha256") or "").lower() != declared:
        raise PipelineHalt(
            "ASSESSMENT_PIPELINE_FAILED", ERROR_CV_HASH_MISMATCH, track=track, stages=stages
        )
    links, ambiguity = _canonical_links(list(assessment_input.get("links") or []))
    if ambiguity:
        source = [cv_outcome["source_record"]] if cv_outcome.get("source_record") else []
        raise PipelineHalt(
            "REVIEW_REQUIRED",
            ERROR_LINK_TYPE_AMBIGUITY,
            track=track,
            source_records=source,
            review_flags=["MATERIAL_CLASSIFICATION_AMBIGUITY"],
            stages=stages,
        )
    retrieved: list[dict[str, Any]] = []
    for link in links:
        retrieved.append(
            retrieve_link(
                link["submitted_url"],
                link_id=link["link_id"],
                declared_type=link["declared_type"],
                retrieved_at=str(assessed_at),
            )
        )
    stages.append("retrieve_links")
    normalization = normalize_evidence(
        track=track,
        cv_extraction=cv_outcome,
        link_retrievals=retrieved,
    )
    stages.append("normalize_evidence")
    if normalization.get("state") == "EVIDENCE_NORMALIZATION_FAILED":
        raise PipelineHalt(
            "ASSESSMENT_PIPELINE_FAILED",
            ERROR_NORMALIZATION_FAILED,
            track=track,
            stages=stages,
        )
    classified = classify_higher_order_evidence(
        track=track,
        normalization=normalization,
        cv_extraction=cv_outcome,
        link_retrievals=retrieved,
    )
    stages.append("classify_higher_order")
    if classified.get("state") == "HIGHER_ORDER_CLASSIFICATION_FAILED":
        raise PipelineHalt(
            "ASSESSMENT_PIPELINE_FAILED",
            ERROR_CLASSIFICATION_FAILED,
            track=track,
            stages=stages,
        )
    assembly = assemble_scoring_context(
        track=track,
        evidence_facts=list(classified["evidence_facts"]),
        source_records=list(classified["source_records"]),
        review_flags=list(classified["review_flags"]),
    )
    stages.append("assemble_scoring_context")
    if assembly.get("state") == "SCORING_CONTEXT_ASSEMBLY_FAILED":
        raise PipelineHalt(
            "ASSESSMENT_PIPELINE_FAILED",
            ERROR_CONTEXT_ASSEMBLY_FAILED,
            track=track,
            stages=stages,
        )
    scoring_input = deepcopy(assessment_input)
    scoring_input["links"] = links
    scoring = score_assessment(
        scoring_input,
        classified["evidence_facts"],
        assembly["scoring_context"],
        classified["source_records"],
        assessment_id=str(assessment_id),
        run_id=str(run_id),
        assessed_at=str(assessed_at),
    )
    stages.append("score_assessment")
    scoring_state = scoring.get("state")
    if scoring_state == "REVIEW_REQUIRED":
        return _pipeline_outcome(
            state="REVIEW_REQUIRED",
            error_code="REVIEW_REQUIRED",
            assessment_id=str(assessment_id),
            run_id=str(run_id),
            track=track,
            assessment_result=None,
            source_records=list(classified["source_records"]),
            evidence_facts=list(classified["evidence_facts"]),
            scoring_context=assembly["scoring_context"],
            review_flags=list(scoring.get("flags") or assembly["review_flags"]),
            stages=stages,
        )
    if scoring_state in {"RULESET_NOT_FOUND", "RULESET_INVALID", "QA_FAILED"}:
        raise PipelineHalt(
            "ASSESSMENT_PIPELINE_FAILED",
            str(scoring.get("error_code") or scoring_state),
            track=track,
            source_records=list(classified["source_records"]),
            evidence_facts=list(classified["evidence_facts"]),
            scoring_context=assembly["scoring_context"],
            stages=stages,
        )
    if scoring_state != "COMPLETED":
        raise PipelineHalt(
            "ASSESSMENT_PIPELINE_FAILED",
            str(scoring.get("error_code") or "SCORING_FAILED"),
            track=track,
            stages=stages,
        )
    outcome = _pipeline_outcome(
        state="COMPLETED",
        error_code=None,
        assessment_id=str(assessment_id),
        run_id=str(run_id),
        track=track,
        assessment_result=scoring["assessment_result"],
        source_records=list(classified["source_records"]),
        evidence_facts=list(classified["evidence_facts"]),
        scoring_context=assembly["scoring_context"],
        review_flags=[],
        stages=stages,
    )
    draft_validator("assessment_pipeline.schema.json").validate(outcome)
    return outcome


def _canonical_links(links: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    retained: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    for link in links:
        try:
            normalized = normalize_submitted_url(str(link["submitted_url"]))
        except (ValueError, TypeError):
            retained.append(link)
            continue
        declared = str(link["declared_type"])
        previous = seen.get(normalized)
        if previous is None:
            seen[normalized] = declared
            retained.append(link)
            continue
        if previous != declared:
            return retained, True
    return retained, False


def _valid_identity(assessment_id: object, run_id: object, assessed_at: object) -> bool:
    if not isinstance(assessment_id, str) or not assessment_id.strip():
        return False
    if not isinstance(run_id, str) or not run_id.strip():
        return False
    try:
        _parse_rfc3339(assessed_at)
    except (TypeError, ValueError):
        return False
    return True


def _parse_rfc3339(value: object) -> datetime:
    """Parse timezone-aware RFC 3339 before any Package F call."""
    if not isinstance(value, str):
        msg = "assessed_at must be a string"
        raise TypeError(msg)
    text = value.strip()
    if not text or "T" not in text:
        msg = "assessed_at must be RFC 3339"
        raise ValueError(msg)
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        msg = "assessed_at must be timezone-aware"
        raise ValueError(msg)
    return parsed


def _pipeline_outcome(
    *,
    state: str,
    error_code: str | None,
    assessment_id: str,
    run_id: str,
    track: str,
    assessment_result: dict[str, Any] | None,
    source_records: list[dict[str, Any]],
    evidence_facts: list[dict[str, Any]],
    scoring_context: dict[str, Any] | None,
    review_flags: list[str],
    stages: list[str],
) -> dict[str, Any]:
    outcome = {
        "state": state,
        "error_code": error_code,
        "pipeline_version": PIPELINE_VERSION,
        "assessment_id": assessment_id,
        "run_id": run_id,
        "contract_version": CONTRACT_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "track": track,
        "assessment_result": assessment_result,
        "source_records": source_records,
        "evidence_facts": evidence_facts,
        "scoring_context": scoring_context,
        "review_flags": review_flags,
        "stages": stages,
    }
    draft_validator("assessment_pipeline.schema.json").validate(outcome)
    return outcome

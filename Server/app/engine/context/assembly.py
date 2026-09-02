"""Package J scoring-context / criterion-binding assembly."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from app.engine.classification.cues import has_cue, token_pattern
from app.engine.configuration import (
    load_criterion_binding_rules_v1,
    load_json,
    load_project_catalog_v1,
    load_rubric_v2,
)
from app.engine.context.outcomes import (
    APPROVED_TRACKS,
    ASSEMBLER_VERSION,
    CONTRACT_VERSION,
    ERROR_ASSEMBLER_EXCEPTION,
    ERROR_CONTEXT_INVALID,
    ERROR_DUPLICATE_EVIDENCE_ID,
    ERROR_DUPLICATE_SOURCE_ID,
    ERROR_IMPOSSIBLE_QUALIFICATION,
    ERROR_INVALID_EVIDENCE_FACT,
    ERROR_INVALID_TRACK,
    ERROR_RULESET_INVALID,
    ERROR_UNKNOWN_FACT_TYPE,
    ERROR_UNKNOWN_SOURCE,
    ERROR_UNRECOGNIZED_REVIEW_FLAG,
    LEVEL_RANK,
    QUAL_RANK,
    RUBRIC_VERSION,
    AssemblyFailure,
    canonical_outcome,
    failed_outcome,
    review_state,
)
from app.engine.outcomes import BLOCKING_REVIEW_FLAGS, NONE_ROUTES, QUALIFICATION_CRITERIA

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"
FACT_TYPES = {
    "skill_name",
    "skill_application",
    "tool_name",
    "tool_application",
    "project_proof",
    "project_context",
    "project_process",
    "project_outcome",
    "qualification",
    "professional_behaviour",
    "role_alignment",
    "document_quality",
}
FINDING_CUES = token_pattern(
    ["finding", "findings", "insight", "insights", "recommendation", "recommendations"]
)
SCOREABLE_ACCESS = frozenset({"accessible"})
CV_SOURCE = "cv"


def assemble_scoring_context(
    *,
    track: str,
    evidence_facts: list[dict[str, Any]],
    source_records: list[dict[str, Any]],
    review_flags: list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    """Bind accepted evidence facts into the frozen scoring-context contract."""
    safe_track = track if isinstance(track, str) else ""
    try:
        return _assemble(
            track=track,
            evidence_facts=evidence_facts,
            source_records=source_records,
            review_flags=review_flags,
        )
    except AssemblyFailure as exc:
        return failed_outcome(exc.error_code, track=exc.track)
    except Exception:
        return failed_outcome(ERROR_ASSEMBLER_EXCEPTION, track=safe_track)


def _assemble(
    *,
    track: object,
    evidence_facts: object,
    source_records: object,
    review_flags: object,
) -> dict[str, Any]:
    safe_track = track if isinstance(track, str) else ""
    if safe_track not in APPROVED_TRACKS:
        raise AssemblyFailure(ERROR_INVALID_TRACK, safe_track)
    try:
        registry = load_criterion_binding_rules_v1()
        rubric = load_rubric_v2()
        projects = load_project_catalog_v1()
    except (OSError, TypeError, ValueError, KeyError):
        raise AssemblyFailure(ERROR_RULESET_INVALID, safe_track) from None
    if registry.get("assembler_version") != ASSEMBLER_VERSION:
        raise AssemblyFailure(ERROR_RULESET_INVALID, safe_track)
    facts = _validated_facts(evidence_facts, safe_track)
    sources = _validated_sources(source_records, safe_track)
    source_by_id = {str(item["source_id"]): item for item in sources}
    _assert_fact_sources(facts, source_by_id, safe_track)
    flags = _validated_flags(review_flags, registry, safe_track)
    eligible = [fact for fact in facts if _source_is_scoreable(source_by_id.get(fact["source_id"]))]
    for fact in eligible:
        if fact.get("attribution_status") == "conflicting":
            flags.append("MATERIAL_SOURCE_CONTRADICTION")
        source = source_by_id[fact["source_id"]]
        if source.get("source_type") != CV_SOURCE and fact.get("attribution_status") == "unclear":
            flags.append("OWNERSHIP_UNCLEAR")
    track_spec = registry["tracks"][safe_track]
    bindings: list[dict[str, Any]] = []
    qualification_anchor = _qualification_route(
        safe_track, eligible, flags, registry, track_spec, safe_track
    )
    for spec in track_spec["criteria"]:
        criterion_id = spec["criterion_id"]
        if spec.get("kind") == "qualification":
            bindings.append(
                {
                    "criterion_id": criterion_id,
                    "anchor": qualification_anchor,
                    "evidence_ids": [
                        fact["evidence_id"]
                        for fact in eligible
                        if fact["fact_type"] == "qualification"
                    ],
                }
            )
            continue
        chosen = _bind_ordinary(spec, eligible)
        bindings.append(chosen)
    unique_flags = _ordered_flags(flags, registry)
    triggers = _rule_triggers(safe_track, eligible, registry)
    exclusions = _project_exclusions(safe_track, unique_flags, bindings, eligible, projects)
    scoring_context = {
        "contract_version": CONTRACT_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "track": safe_track,
        "criterion_bindings": bindings,
        "rule_triggers": triggers,
        "review_flags": unique_flags,
        "project_exclusion_ids": exclusions,
    }
    _assert_binding_coverage(bindings, rubric, safe_track)
    try:
        _validator("scoring_context.schema.json").validate(scoring_context)
    except (ValidationError, TypeError, ValueError):
        raise AssemblyFailure(ERROR_CONTEXT_INVALID, safe_track) from None
    state, error_code = review_state(unique_flags)
    outcome = canonical_outcome(
        state=state,
        error_code=error_code,
        track=safe_track,
        scoring_context=scoring_context,
        review_flags=unique_flags,
    )
    _validator("scoring_context_assembly.schema.json").validate(outcome)
    return outcome


def _bind_ordinary(spec: dict[str, Any], facts: list[dict[str, Any]]) -> dict[str, Any]:
    primary = _eligible_facts(spec.get("subjects") or [], spec, facts)
    selected = primary
    if not selected:
        selected = _eligible_facts(spec.get("fallback_subjects") or [], spec, facts)
    if not selected:
        return {
            "criterion_id": spec["criterion_id"],
            "anchor": "missing_unverifiable",
            "evidence_ids": [],
        }
    best = max(LEVEL_RANK[fact["evidence_level"]] for fact in selected)
    winners = [
        fact
        for fact in selected
        if LEVEL_RANK[fact["evidence_level"]] == best
        and fact["evidence_level"] != "missing_unverifiable"
    ]
    if not winners:
        return {
            "criterion_id": spec["criterion_id"],
            "anchor": "missing_unverifiable",
            "evidence_ids": [],
        }
    return {
        "criterion_id": spec["criterion_id"],
        "anchor": winners[0]["evidence_level"],
        "evidence_ids": [fact["evidence_id"] for fact in winners],
    }


def _eligible_facts(
    subjects: list[str], spec: dict[str, Any], facts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    wanted = set(subjects)
    found: list[dict[str, Any]] = []
    for fact in facts:
        if fact["subject"] not in wanted:
            continue
        if (
            spec["criterion_id"] == "da.projects.findings"
            and fact["subject"] == "analytics_project_outcome"
            and not has_cue(str(fact["explicit_text"]), FINDING_CUES)
        ):
            continue
        found.append(fact)
    return found


def _qualification_route(
    track: str,
    facts: list[dict[str, Any]],
    flags: list[str],
    registry: dict[str, Any],
    track_spec: dict[str, Any],
    safe_track: str,
) -> str:
    prefix = "se" if track == "software_engineering" else "da"
    none_route = NONE_ROUTES[track]
    quals = [fact for fact in facts if fact["fact_type"] == "qualification"]
    completed = token_pattern(list(registry["completed_cues"]))
    in_progress = token_pattern(list(registry["in_progress_cues"]))
    fields = token_pattern(
        list(
            registry["se_relevant_fields"]
            if track == "software_engineering"
            else registry["da_relevant_fields"]
        )
    )
    application = [
        fact for fact in facts if fact["fact_type"] in {"skill_application", "tool_application"}
    ]
    text = " ".join(str(fact["explicit_text"]) for fact in quals)
    routes: list[str] = []
    relevant = has_cue(text, fields)
    if quals and relevant and has_cue(text, completed):
        routes.append("completed")
    if quals and relevant and has_cue(text, in_progress):
        routes.append("in_progress")
    bootcampish = any(
        fact["subject"] in {"bootcamp", "certificate", "certification", "higher_certificate"}
        for fact in quals
    )
    if bootcampish and application:
        routes.append("bootcamp")
    years = any("year" in str(fact["explicit_text"]).casefold() for fact in facts) and not quals
    if years:
        flags.append("MATERIAL_CLASSIFICATION_AMBIGUITY")
        return none_route
    if quals and not routes:
        flags.append("MATERIAL_CLASSIFICATION_AMBIGUITY")
        return none_route
    if not routes:
        return none_route
    best = max(routes, key=lambda item: QUAL_RANK[item])
    return f"{prefix}.qual.{best}"


def _rule_triggers(track: str, facts: list[dict[str, Any]], registry: dict[str, Any]) -> list[str]:
    triggers: list[str] = []
    if track == "data_analytics":
        sheets = [
            fact
            for fact in facts
            if fact["subject"] == "google_sheets"
            and fact["evidence_level"] != "missing_unverifiable"
        ]
        excel = [
            fact
            for fact in facts
            if fact["subject"] == "excel" and fact["evidence_level"] != "missing_unverifiable"
        ]
        if any(fact["evidence_level"] == "demonstrated" for fact in sheets) and not excel:
            triggers.append(registry["google_sheets_ceiling_rule_id"])
        if any(fact["subject"] == "context_free_dashboard_screenshot" for fact in facts):
            triggers.append(registry["context_free_dashboard_rule_id"])
    return triggers


def _project_exclusions(
    track: str,
    flags: list[str],
    bindings: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    projects: dict[str, Any],
) -> list[str]:
    recognized = set(projects.get("global_exclusion_conditions") or [])
    for project in projects["projects"]:
        recognized.update(project.get("exclusion_conditions") or [])
    found: list[str] = []
    if any(flag in BLOCKING_REVIEW_FLAGS for flag in flags):
        found.append("blocking_review_unresolved")
    if "TRACK_MISMATCH" in flags:
        found.append("track_mismatch")
    if not any(fact["subject"] == "python" for fact in facts):
        found.append("python_not_explicit")
    if track == "software_engineering":
        systems = next(
            item for item in bindings if item["criterion_id"] == "se.core.application_systems"
        )
        if systems["anchor"] == "missing_unverifiable":
            found.append("api_foundation_missing_unverifiable")
    return [item for item in found if item in recognized]


def _source_is_scoreable(source: dict[str, Any] | None) -> bool:
    if source is None:
        return False
    if source.get("submitted_by_candidate") is not True:
        return False
    if source.get("source_type") == CV_SOURCE:
        return True
    return source.get("access_status") in SCOREABLE_ACCESS


def _validated_facts(evidence_facts: object, track: str) -> list[dict[str, Any]]:
    if not isinstance(evidence_facts, list):
        raise AssemblyFailure(ERROR_INVALID_EVIDENCE_FACT, track)
    validator = _validator("evidence_fact.schema.json")
    seen: set[str] = set()
    validated: list[dict[str, Any]] = []
    for fact in evidence_facts:
        if not isinstance(fact, dict):
            raise AssemblyFailure(ERROR_INVALID_EVIDENCE_FACT, track)
        try:
            validator.validate(fact)
        except ValidationError:
            raise AssemblyFailure(ERROR_INVALID_EVIDENCE_FACT, track) from None
        if fact["fact_type"] not in FACT_TYPES:
            raise AssemblyFailure(ERROR_UNKNOWN_FACT_TYPE, track)
        evidence_id = fact["evidence_id"]
        if evidence_id in seen:
            raise AssemblyFailure(ERROR_DUPLICATE_EVIDENCE_ID, track)
        seen.add(evidence_id)
        validated.append(deepcopy(fact))
    return validated


def _validated_sources(source_records: object, track: str) -> list[dict[str, Any]]:
    if not isinstance(source_records, list):
        raise AssemblyFailure(ERROR_UNKNOWN_SOURCE, track)
    seen: set[str] = set()
    validated: list[dict[str, Any]] = []
    for record in source_records:
        if not isinstance(record, dict) or not record.get("source_id"):
            raise AssemblyFailure(ERROR_UNKNOWN_SOURCE, track)
        source_id = str(record["source_id"])
        if source_id in seen:
            raise AssemblyFailure(ERROR_DUPLICATE_SOURCE_ID, track)
        seen.add(source_id)
        validated.append(deepcopy(record))
    return validated


def _assert_fact_sources(
    facts: list[dict[str, Any]], source_by_id: dict[str, dict[str, Any]], track: str
) -> None:
    for fact in facts:
        if fact["source_id"] not in source_by_id:
            raise AssemblyFailure(ERROR_UNKNOWN_SOURCE, track)


def _validated_flags(review_flags: object, registry: dict[str, Any], track: str) -> list[str]:
    if review_flags is None:
        return []
    if not isinstance(review_flags, (list, tuple)):
        raise AssemblyFailure(ERROR_UNRECOGNIZED_REVIEW_FLAG, track)
    recognized = set(registry["recognized_flags"])
    flags: list[str] = []
    for flag in review_flags:
        if not isinstance(flag, str) or flag not in recognized:
            raise AssemblyFailure(ERROR_UNRECOGNIZED_REVIEW_FLAG, track)
        flags.append(flag)
    return flags


def _ordered_flags(flags: list[str], registry: dict[str, Any]) -> list[str]:
    order = list(registry["flag_order"])
    present = {flag for flag in flags if flag}
    return [flag for flag in order if flag in present]


def _assert_binding_coverage(
    bindings: list[dict[str, Any]], rubric: dict[str, Any], track: str
) -> None:
    expected = [item["id"] for item in rubric["tracks"][track]["criteria"]]
    got = [item["criterion_id"] for item in bindings]
    if got != expected:
        raise AssemblyFailure(ERROR_CONTEXT_INVALID, track)
    if QUALIFICATION_CRITERIA[track] not in got:
        raise AssemblyFailure(ERROR_IMPOSSIBLE_QUALIFICATION, track)


def _validator(filename: str) -> Draft202012Validator:
    schema = load_json(SCHEMA_DIR / filename)
    if not isinstance(schema, dict):
        msg = f"{filename} must contain a JSON object"
        raise TypeError(msg)
    return Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)

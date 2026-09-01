"""Pure Contract 1.2 scoring implementation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from app.engine.configuration.validation import (
    ACTIVE_CONTRACT_VERSION,
    ACTIVE_RUBRIC_VERSION,
    EngineConfiguration,
    load_validated_engine_configuration,
    recognized_project_exclusions,
    recognized_rule_ids,
)
from app.engine.outcomes import (
    BLOCKING_REVIEW_FLAGS,
    NONE_ROUTES,
    ORDINARY_ANCHORS,
    PROJECT_SOURCE_TYPES,
    QUALIFICATION_CRITERIA,
    REVIEW_SENTINEL,
    engine_outcome,
)
from app.engine.qa import band_for, run_assessment_qa

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"
IDENTITY_FIELDS = {"assessment_id", "run_id", "submitted_at", "assessed_at"}


def score_assessment(
    assessment_input: Mapping[str, Any],
    evidence_facts: Sequence[Mapping[str, Any]],
    scoring_context: Mapping[str, Any],
    source_records: Sequence[Mapping[str, Any]],
    *,
    assessment_id: str,
    run_id: str,
    assessed_at: str,
    configuration: EngineConfiguration | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score one frozen assessment run from structured inputs only.

    This entry point performs no HTTP, database, logging, environment lookup,
    or filesystem mutation. Configuration is loaded through the validated
    loader unless the caller supplies an already-loaded configuration.
    """
    loaded = configuration
    if loaded is None:
        loaded = load_validated_engine_configuration()
    if isinstance(loaded, dict) and loaded.get("state") in {
        "RULESET_INVALID",
        "RULESET_NOT_FOUND",
    }:
        return loaded
    if not isinstance(loaded, EngineConfiguration):
        return engine_outcome("RULESET_INVALID", error_code="RULESET_INVALID")

    invalid = _validate_scoring_inputs(
        assessment_input,
        evidence_facts,
        scoring_context,
        source_records,
        loaded,
    )
    if invalid is not None:
        return invalid

    flags = list(scoring_context["review_flags"])
    blocking = [flag for flag in flags if flag in BLOCKING_REVIEW_FLAGS]
    if blocking:
        sql_binding = next(
            (
                item
                for item in scoring_context["criterion_bindings"]
                if item["criterion_id"] == "da.core.sql"
            ),
            None,
        )
        extra: dict[str, Any] = {"review_flag": blocking[0]}
        if sql_binding is not None:
            extra["frozen_sql_evidence_level"] = sql_binding["anchor"]
        return engine_outcome(
            "REVIEW_REQUIRED",
            error_code="REVIEW_REQUIRED",
            flags=blocking,
            **extra,
        )

    result = _score_completed(
        deepcopy(dict(assessment_input)),
        [dict(item) for item in evidence_facts],
        deepcopy(dict(scoring_context)),
        [dict(item) for item in source_records],
        loaded,
        assessment_id=assessment_id,
        run_id=run_id,
        assessed_at=assessed_at,
    )
    qa = result["qa"]
    if qa["status"] != "PASS":
        return engine_outcome("QA_FAILED", error_code="QA_FAILED", flags=flags)
    return engine_outcome("COMPLETED", assessment_result=result, flags=result["flags"])


def canonical_result(document: Mapping[str, Any]) -> dict[str, Any]:
    """Return a result with fixture-approved identity fields removed."""
    return _strip_identity(document)


def _validate_scoring_inputs(
    assessment_input: Mapping[str, Any],
    evidence_facts: Sequence[Mapping[str, Any]],
    scoring_context: Mapping[str, Any],
    source_records: Sequence[Mapping[str, Any]],
    configuration: EngineConfiguration,
) -> dict[str, Any] | None:
    try:
        _schema_validator("assessment_input.schema.json").validate(assessment_input)
        _schema_validator("scoring_context.schema.json").validate(scoring_context)
        fact_validator = _schema_validator("evidence_fact.schema.json")
        for fact in evidence_facts:
            fact_validator.validate(fact)
    except ValidationError:
        return engine_outcome("INPUT_INVALID", error_code="INPUT_INVALID")

    track = scoring_context["track"]
    if track not in configuration.rubric["tracks"]:
        return engine_outcome("TRACK_INVALID", error_code="TRACK_INVALID")
    versions = {
        assessment_input["contract_version"],
        assessment_input["rubric_version"],
        scoring_context["contract_version"],
        scoring_context["rubric_version"],
        configuration.rubric["contract_version"],
        configuration.rubric["rubric_version"],
    }
    if assessment_input["track"] != track:
        return engine_outcome("INPUT_INVALID", error_code="INPUT_INVALID")
    if ACTIVE_CONTRACT_VERSION not in versions or ACTIVE_RUBRIC_VERSION not in versions:
        return engine_outcome("INPUT_INVALID", error_code="INPUT_INVALID")
    if (
        assessment_input["contract_version"] != ACTIVE_CONTRACT_VERSION
        or scoring_context["contract_version"] != ACTIVE_CONTRACT_VERSION
        or assessment_input["rubric_version"] != ACTIVE_RUBRIC_VERSION
        or scoring_context["rubric_version"] != ACTIVE_RUBRIC_VERSION
    ):
        return engine_outcome("INPUT_INVALID", error_code="INPUT_INVALID")

    source_ids = [source["source_id"] for source in source_records]
    if len(source_ids) != len(set(source_ids)):
        return engine_outcome("INPUT_INVALID", error_code="INPUT_INVALID")
    facts = {fact["evidence_id"]: fact for fact in evidence_facts}
    if len(facts) != len(evidence_facts):
        return engine_outcome("INPUT_INVALID", error_code="INPUT_INVALID")
    for fact in evidence_facts:
        if fact["source_id"] not in source_ids:
            return engine_outcome("INPUT_INVALID", error_code="INPUT_INVALID")

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
            return engine_outcome("INPUT_INVALID", error_code="INPUT_INVALID")

    track_criteria = configuration.rubric["tracks"][track]["criteria"]
    track_ids = {item["id"] for item in track_criteria}
    qualification_id = QUALIFICATION_CRITERIA[track]
    routes = {item["id"] for item in configuration.rubric["tracks"][track]["qualification_routes"]}
    bindings = scoring_context["criterion_bindings"]
    bound_ids = [item["criterion_id"] for item in bindings]
    if len(bound_ids) != len(set(bound_ids)):
        return engine_outcome("INPUT_INVALID", error_code="INPUT_INVALID")
    qualification_bindings = [item for item in bindings if item["criterion_id"] == qualification_id]
    if len(qualification_bindings) != 1:
        return engine_outcome("INPUT_INVALID", error_code="INPUT_INVALID")
    if qualification_bindings[0]["anchor"] not in routes:
        return engine_outcome("INPUT_INVALID", error_code="INPUT_INVALID")
    approved_rules = recognized_rule_ids(configuration.rubric)
    approved_exclusions = recognized_project_exclusions(configuration.project_catalog)
    triggers = scoring_context["rule_triggers"]
    exclusions = scoring_context["project_exclusion_ids"]
    if len(triggers) != len(set(triggers)) or any(rule not in approved_rules for rule in triggers):
        return engine_outcome("INPUT_INVALID", error_code="INPUT_INVALID")
    if len(exclusions) != len(set(exclusions)) or any(
        item not in approved_exclusions for item in exclusions
    ):
        return engine_outcome("INPUT_INVALID", error_code="INPUT_INVALID")
    if len(scoring_context["review_flags"]) != len(set(scoring_context["review_flags"])):
        return engine_outcome("INPUT_INVALID", error_code="INPUT_INVALID")

    for binding in bindings:
        if binding["criterion_id"] not in track_ids:
            return engine_outcome("INPUT_INVALID", error_code="INPUT_INVALID")
        for evidence_id in binding["evidence_ids"]:
            if evidence_id not in facts:
                return engine_outcome("INPUT_INVALID", error_code="INPUT_INVALID")
        if binding["criterion_id"] == qualification_id:
            if binding["anchor"] != NONE_ROUTES[track] and not binding["evidence_ids"]:
                return engine_outcome("INPUT_INVALID", error_code="INPUT_INVALID")
            continue
        if binding["anchor"] not in ORDINARY_ANCHORS:
            return engine_outcome("INPUT_INVALID", error_code="INPUT_INVALID")
        if binding["anchor"] != "missing_unverifiable" and not binding["evidence_ids"]:
            return engine_outcome("INPUT_INVALID", error_code="INPUT_INVALID")
    return None


def _score_completed(
    assessment_input: dict[str, Any],
    evidence_facts: list[dict[str, Any]],
    scoring_context: dict[str, Any],
    source_records: list[dict[str, Any]],
    configuration: EngineConfiguration,
    *,
    assessment_id: str,
    run_id: str,
    assessed_at: str,
) -> dict[str, Any]:
    track_id = scoring_context["track"]
    track = configuration.rubric["tracks"][track_id]
    facts = {fact["evidence_id"]: fact for fact in evidence_facts}
    bindings = {item["criterion_id"]: item for item in scoring_context["criterion_bindings"]}
    triggers = set(scoring_context["rule_triggers"])
    qualification_id = QUALIFICATION_CRITERIA[track_id]
    routes = {item["id"]: item["points"] for item in track["qualification_routes"]}

    criterion_results: list[dict[str, Any]] = []
    for criterion in track["criteria"]:
        criterion_id = criterion["id"]
        binding = bindings.get(criterion_id)
        if binding is None:
            anchor = (
                "missing_unverifiable"
                if criterion_id != qualification_id
                else NONE_ROUTES[track_id]
            )
            evidence_ids: list[str] = []
        else:
            anchor = binding["anchor"]
            evidence_ids = list(binding["evidence_ids"])
        awarded, rule_ids = _award_points(criterion, anchor, routes, triggers)
        if criterion_id != qualification_id and binding is None:
            anchor = "missing_unverifiable"
        note = _evidence_note(criterion["display_name"], anchor, evidence_ids)
        criterion_results.append(
            {
                "criterion_id": criterion_id,
                "category_id": criterion["category_id"],
                "max_points": criterion["max_points"],
                "anchor": anchor,
                "awarded_points": awarded,
                "evidence_ids": evidence_ids,
                "rule_ids": rule_ids,
                "evidence_note": note,
                "flags": [],
            }
        )

    by_id = {item["criterion_id"]: item for item in criterion_results}
    category_caps: list[dict[str, Any]] = []
    category_results: list[dict[str, Any]] = []
    for category in track["categories"]:
        members = [item for item in criterion_results if item["category_id"] == category["id"]]
        pre_cap = sum(item["awarded_points"] for item in members)
        final = pre_cap
        triggered = _triggered_category_cap(track, category["id"], source_records)
        if triggered is not None:
            category_caps.append(triggered)
            final = min(pre_cap, triggered["cap"])
        category_results.append(
            {
                "category_id": category["id"],
                "max_points": category["max_points"],
                "pre_cap_score": pre_cap,
                "final_score": final,
            }
        )

    raw_total = sum(item["final_score"] for item in category_results)
    overall_caps = _triggered_overall_caps(track, by_id)
    applicable = min([cap["cap"] for cap in overall_caps] + [100])
    final_score = min(raw_total, applicable)
    strengths = _ordered_strengths(criterion_results)
    overall_priority_ids = _overall_gap_criterion_ids(track, overall_caps)
    category_priority_ids = {
        item["criterion_id"]
        for cap in category_caps
        for item in criterion_results
        if item["category_id"] == cap.get("category_id")
    }
    gaps = _ordered_gaps(criterion_results, overall_priority_ids, category_priority_ids)
    actions = _priority_actions(configuration.action_catalog, by_id, gaps)
    recommendation = _select_project(
        configuration.project_catalog,
        track_id,
        criterion_results,
        evidence_facts,
        scoring_context["project_exclusion_ids"],
        flags=[],
    )
    result = {
        "assessment_id": assessment_id,
        "run_id": run_id,
        "contract_version": ACTIVE_CONTRACT_VERSION,
        "rubric_version": ACTIVE_RUBRIC_VERSION,
        "track": track_id,
        "status": "COMPLETED",
        "assessed_at": assessed_at,
        "source_snapshot": _source_snapshot(assessment_input, source_records),
        "category_results": category_results,
        "criterion_results": criterion_results,
        "category_caps": category_caps,
        "raw_total": raw_total,
        "overall_caps": overall_caps,
        "applicable_overall_cap": applicable,
        "final_score": final_score,
        "band": band_for(final_score),
        "strengths": strengths,
        "material_gaps": gaps,
        "priority_actions": actions,
        "project_recommendation": recommendation,
        "flags": [],
        "qa": {"status": "PASS", "checks": []},
    }
    result["qa"] = run_assessment_qa(
        assessment_input=assessment_input,
        source_records=source_records,
        facts=facts,
        result=result,
        track_criteria=track["criteria"],
        review_flags=list(scoring_context["review_flags"]),
    )
    return result


def _award_points(
    criterion: Mapping[str, Any],
    anchor: str,
    routes: Mapping[str, int],
    triggers: set[str],
) -> tuple[int, list[str]]:
    rule_ids = [criterion["rule_id"]]
    if criterion["scoring"] == "qualification_routes":
        return routes[anchor], rule_ids
    awarded = criterion["evidence_anchors"][anchor]
    if (
        criterion["id"] == "da.core.spreadsheets"
        and "rubric.v2.da.cap.google_sheets_ceiling" in triggers
    ):
        awarded = min(awarded, 5)
        rule_ids.append("rubric.v2.da.cap.google_sheets_ceiling")
    if (
        criterion["id"] == "da.projects.context"
        and "rubric.v2.da.rule.context_free_dashboard" in triggers
    ):
        awarded = 0
        rule_ids.append("rubric.v2.da.rule.context_free_dashboard")
    if criterion["id"] == "da.tools.power_bi_alignment" and anchor != "missing_unverifiable":
        awarded = min(awarded, criterion["max_points"])
    return min(awarded, criterion["max_points"]), rule_ids


def _evidence_note(display_name: str, anchor: str, evidence_ids: list[str]) -> str:
    if not evidence_ids and anchor in {"missing_unverifiable", *NONE_ROUTES.values()}:
        return f"No accepted evidence was present for {display_name}."
    return f"{display_name} scored from locked {anchor} evidence."


def _triggered_category_cap(
    track: Mapping[str, Any],
    category_id: str,
    source_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    if _has_accessible_project_link(source_records):
        return None
    for cap in track["category_caps"]:
        if cap["category_id"] != category_id:
            continue
        if cap["trigger"] == "no_accessible_candidate_submitted_project_link":
            return {
                "rule_id": cap["rule_id"],
                "cap": cap["cap_points"],
                "category_id": category_id,
            }
    return None


def _has_accessible_project_link(source_records: Sequence[Mapping[str, Any]]) -> bool:
    return any(
        source.get("source_type") in PROJECT_SOURCE_TYPES
        and source.get("submitted_by_candidate") is True
        and source.get("access_status") == "accessible"
        for source in source_records
    )


def _triggered_overall_caps(
    track: Mapping[str, Any],
    by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    triggered: list[dict[str, Any]] = []
    for cap in track["overall_caps"]:
        related = by_id[cap["related_criterion_id"]]
        named_only_counts = cap.get("named_only_counts_as_evidence", False)
        missing = related["anchor"] == "missing_unverifiable"
        if named_only_counts and related["anchor"] == "named_only":
            missing = False
        if missing:
            triggered.append({"rule_id": cap["rule_id"], "cap": cap["cap_points"]})
    return triggered


def _overall_gap_criterion_ids(
    track: Mapping[str, Any],
    overall_caps: Sequence[Mapping[str, Any]],
) -> set[str]:
    related = {cap["rule_id"]: cap["related_criterion_id"] for cap in track["overall_caps"]}
    return {related[item["rule_id"]] for item in overall_caps if item["rule_id"] in related}


def _ordered_strengths(criterion_results: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    strengths = [
        {
            "criterion_id": item["criterion_id"],
            "awarded_points": item["awarded_points"],
            "max_points": item["max_points"],
        }
        for item in criterion_results
        if item["awarded_points"] > 0
    ]
    strengths.sort(
        key=lambda item: (
            -(item["awarded_points"] / item["max_points"] if item["max_points"] else 0),
            -item["awarded_points"],
            -item["max_points"],
            item["criterion_id"],
        )
    )
    return strengths[:5]


def _ordered_gaps(
    criterion_results: Sequence[Mapping[str, Any]],
    overall_cap_ids: set[str],
    category_cap_ids: set[str],
) -> list[dict[str, Any]]:
    gaps = []
    for item in criterion_results:
        point_gap = item["max_points"] - item["awarded_points"]
        if point_gap <= 0:
            continue
        gaps.append(
            {
                "criterion_id": item["criterion_id"],
                "point_gap": point_gap,
                "gap_ratio": point_gap / item["max_points"],
                "max_points": item["max_points"],
            }
        )
    gaps.sort(
        key=lambda item: (
            0 if item["criterion_id"] in overall_cap_ids else 1,
            0 if item["criterion_id"] in category_cap_ids else 1,
            -item["point_gap"],
            -item["max_points"],
            item["criterion_id"],
        )
    )
    return [
        {
            "criterion_id": item["criterion_id"],
            "point_gap": item["point_gap"],
            "gap_ratio": item["gap_ratio"],
        }
        for item in gaps
    ]


def _priority_actions(
    action_catalog: Mapping[str, Any],
    by_id: Mapping[str, Mapping[str, Any]],
    gaps: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    selected = []
    for index, gap in enumerate(gaps[:5], start=1):
        criterion = by_id[gap["criterion_id"]]
        matches = [
            action
            for action in action_catalog["actions"]
            if action["criterion_id"] == criterion["criterion_id"]
            and action["current_anchor"] == criterion["anchor"]
        ]
        catalog_action = matches[0]
        selected.append(
            {
                "action_id": catalog_action["action_id"],
                "criterion_id": catalog_action["criterion_id"],
                "current_anchor": catalog_action["current_anchor"],
                "target_anchor": catalog_action["target_anchor"],
                "required_output": catalog_action["required_output"],
                "completion_check": catalog_action["completion_check"],
                "priority_order": index,
            }
        )
    return selected


def _select_project(
    project_catalog: Mapping[str, Any],
    track: str,
    criterion_results: Sequence[Mapping[str, Any]],
    facts: Sequence[Mapping[str, Any]],
    project_exclusion_ids: Sequence[str],
    flags: Sequence[str],
) -> object:
    gap_by_id = {
        item["criterion_id"]: item["max_points"] - item["awarded_points"]
        for item in criterion_results
        if item["max_points"] - item["awarded_points"] > 0
    }
    python_explicit = any(
        fact["subject"].lower() == "python" and fact["evidence_level"] != "missing_unverifiable"
        for fact in facts
        if fact["fact_type"] in {"skill_name", "skill_application"}
    )
    api_missing = any(
        item["criterion_id"] == "se.core.application_systems"
        and item["anchor"] == "missing_unverifiable"
        for item in criterion_results
    )
    explicit_exclusions = set(project_exclusion_ids)
    eligible: list[tuple[int, str, Mapping[str, Any]]] = []
    for project in project_catalog["projects"]:
        exclusions = set(project["exclusion_conditions"])
        if project["track"] != track and "track_mismatch" in exclusions:
            continue
        if flags and "blocking_review_unresolved" in exclusions:
            continue
        if "python_not_explicit" in exclusions and not python_explicit:
            continue
        if "api_foundation_missing_unverifiable" in exclusions and api_missing:
            continue
        if explicit_exclusions.intersection(exclusions):
            continue
        coverage = sum(
            gap_by_id[criterion_id]
            for criterion_id in project["core_criterion_ids"]
            if criterion_id in gap_by_id
        )
        if coverage <= 0:
            continue
        eligible.append((coverage, project["project_id"], project))
    eligible.sort(key=lambda item: (-item[0], item[1]))
    if not eligible:
        return REVIEW_SENTINEL
    winner = eligible[0][2]
    return {
        "project_id": winner["project_id"],
        "catalogue_version": winner["catalog_version"],
    }


def _source_snapshot(
    assessment_input: Mapping[str, Any],
    source_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    hashes = [
        source["content_hash"]
        for source in source_records
        if source.get("source_type") != "cv" and isinstance(source.get("content_hash"), str)
    ]
    return {
        "cv_hash": assessment_input["cv"]["sha256"],
        "link_content_hashes": hashes,
    }


def _schema_validator(filename: str) -> Draft202012Validator:
    schema = _load_schema(filename)
    return Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)


def _load_schema(filename: str) -> dict[str, Any]:
    import json

    with (SCHEMA_DIR / filename).open(encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document, dict):
        msg = f"{filename} must contain a JSON object"
        raise TypeError(msg)
    return document


def _strip_identity(node: object) -> object:
    if isinstance(node, Mapping):
        return {
            key: _strip_identity(value) for key, value in node.items() if key not in IDENTITY_FIELDS
        }
    if isinstance(node, list):
        return [_strip_identity(item) for item in node]
    return node

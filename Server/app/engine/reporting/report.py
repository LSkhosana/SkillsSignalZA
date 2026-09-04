"""Pure deterministic Readiness Report assembly.

Consumes a completed canonical assessment_result. Does not score, call
Package K, re-rank strengths/gaps/actions, or inspect raw CV/link content.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from jsonschema.exceptions import ValidationError

from app.engine.configuration import (
    load_action_catalog_v1,
    load_project_catalog_v1,
    load_report_copy_v1,
    load_rubric_v2,
)
from app.engine.reporting.outcomes import (
    CONTRACT_VERSION,
    ERROR_REPORT_BUILD_FAILED,
    ERROR_REPORT_RULESET_INVALID,
    ERROR_REPORT_VERSION_NOT_FOUND,
    REPORT_SCHEMA_VERSION,
    REPORT_VERSION,
    REQUIRED_CAP_RULE_IDS,
    REQUIRED_EVIDENCE_ANCHORS,
    REQUIRED_QUALIFICATION_ROUTES,
    REVIEW_SENTINEL,
    RUBRIC_VERSION,
    ReportingHalt,
    reporting_failure,
)
from app.engine.schema_registry import draft_validator


def build_readiness_report(
    assessment_result: Mapping[str, Any] | None,
    *,
    report_version: str = REPORT_VERSION,
    report_copy: Mapping[str, Any] | None = None,
    rubric: Mapping[str, Any] | None = None,
    action_catalog: Mapping[str, Any] | None = None,
    project_catalog: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble a schema-valid full Readiness Report from a completed result."""
    try:
        return _build(
            assessment_result,
            report_version=report_version,
            report_copy=report_copy,
            rubric=rubric,
            action_catalog=action_catalog,
            project_catalog=project_catalog,
        )
    except ReportingHalt as exc:
        return reporting_failure(exc.error_code)
    except Exception:
        return reporting_failure(ERROR_REPORT_BUILD_FAILED)


def _build(
    assessment_result: Mapping[str, Any] | None,
    *,
    report_version: str,
    report_copy: Mapping[str, Any] | None,
    rubric: Mapping[str, Any] | None,
    action_catalog: Mapping[str, Any] | None,
    project_catalog: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(assessment_result, Mapping):
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    try:
        draft_validator("assessment_result.schema.json").validate(dict(assessment_result))
    except ValidationError:
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID) from None
    if assessment_result.get("status") != "COMPLETED":
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    if report_version != REPORT_VERSION:
        raise ReportingHalt(ERROR_REPORT_VERSION_NOT_FOUND)
    if assessment_result.get("contract_version") != CONTRACT_VERSION:
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    if assessment_result.get("rubric_version") != RUBRIC_VERSION:
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)

    copy = _validated_copy(report_copy if report_copy is not None else load_report_copy_v1())
    if str(copy.get("report_version")) != report_version:
        raise ReportingHalt(ERROR_REPORT_VERSION_NOT_FOUND)
    if copy.get("contract_version") != assessment_result.get("contract_version"):
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    if copy.get("rubric_version") != assessment_result.get("rubric_version"):
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)

    rubric_doc = dict(rubric if rubric is not None else load_rubric_v2())
    actions_doc = dict(action_catalog if action_catalog is not None else load_action_catalog_v1())
    projects_doc = dict(
        project_catalog if project_catalog is not None else load_project_catalog_v1()
    )
    track = str(assessment_result["track"])
    track_cfg = _track_config(rubric_doc, track)
    categories = list(track_cfg["categories"])
    criteria = list(track_cfg["criteria"])
    category_by_id = {str(item["id"]): item for item in categories}
    criterion_by_id = {str(item["id"]): item for item in criteria}
    band_by_id = {str(item["id"]): item for item in rubric_doc.get("score_bands", [])}
    result_categories = list(assessment_result["category_results"])
    result_criteria = list(assessment_result["criterion_results"])
    _assert_unique_ids(result_categories, "category_id")
    _assert_unique_ids(result_criteria, "criterion_id")
    category_result_by_id = {str(item["category_id"]): item for item in result_categories}
    criterion_result_by_id = {str(item["criterion_id"]): item for item in result_criteria}
    if set(category_result_by_id) != set(category_by_id):
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    if set(criterion_result_by_id) != set(criterion_by_id):
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    for criterion_id, criterion in criterion_by_id.items():
        row = criterion_result_by_id[criterion_id]
        if str(row["category_id"]) != str(criterion["category_id"]):
            raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
        if int(row["max_points"]) != int(criterion["max_points"]):
            raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)

    band_id = str(assessment_result["band"])
    band = band_by_id.get(band_id)
    if not isinstance(band, Mapping):
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    final_score = int(assessment_result["final_score"])
    if final_score < 0 or final_score > 100:
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)

    category_breakdown = _category_breakdown(categories, category_result_by_id)
    strongest_area = _strongest_area(category_breakdown, [str(item["id"]) for item in categories])
    material_gaps = [
        _gap_row(item, criterion_by_id, category_by_id, criterion_result_by_id, copy)
        for item in assessment_result["material_gaps"]
    ]
    priority_gap = material_gaps[0] if material_gaps else None
    strengths = [
        _strength_row(item, criterion_by_id, category_by_id, criterion_result_by_id, copy)
        for item in assessment_result["strengths"]
    ]
    priority_actions = [
        _action_row(item, criterion_by_id, actions_doc, copy)
        for item in assessment_result["priority_actions"]
    ]
    payload = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "report_version": report_version,
        "assessment_id": str(assessment_result["assessment_id"]),
        "run_id": str(assessment_result["run_id"]),
        "contract_version": CONTRACT_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "track": track,
        "track_label": str(track_cfg["display_name"]),
        "assessed_at": str(assessment_result["assessed_at"]),
        "benchmark": {
            "scope_statement": str(copy["benchmark"]["scope_statement"]),
            "disclaimer": str(copy["benchmark"]["disclaimer"]),
        },
        "score_summary": {
            "final_score": final_score,
            "score_max": 100,
            "raw_total": int(assessment_result["raw_total"]),
            "band_id": band_id,
            "band_label": str(band["label"]),
            "strongest_area": strongest_area,
            "priority_gap": priority_gap,
            "category_caps": [
                _category_cap(item, category_by_id, copy)
                for item in assessment_result["category_caps"]
            ],
            "overall_caps": [
                _overall_cap(item, copy) for item in assessment_result["overall_caps"]
            ],
            "applicable_overall_cap": int(assessment_result["applicable_overall_cap"]),
        },
        "category_breakdown": category_breakdown,
        "strengths": strengths,
        "material_gaps": material_gaps,
        "priority_actions": priority_actions,
        "project_recommendation": _project_row(
            assessment_result.get("project_recommendation"), track, projects_doc
        ),
        "criterion_breakdown": [
            _criterion_row(item, criterion_result_by_id, category_by_id, copy) for item in criteria
        ],
    }
    try:
        draft_validator("readiness_report.schema.json").validate(payload)
    except ValidationError:
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID) from None
    return payload


def _validated_copy(document: Mapping[str, Any]) -> dict[str, Any]:
    copy = dict(document)
    if copy.get("status") != "approved":
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    if copy.get("contract_version") != CONTRACT_VERSION:
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    if copy.get("rubric_version") != RUBRIC_VERSION:
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    anchors = copy.get("evidence_anchor_labels")
    routes = copy.get("qualification_route_labels")
    caps = copy.get("cap_rule_labels")
    benchmark = copy.get("benchmark")
    if not isinstance(anchors, Mapping) or not isinstance(routes, Mapping):
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    if not isinstance(caps, Mapping) or not isinstance(benchmark, Mapping):
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    for key in REQUIRED_EVIDENCE_ANCHORS:
        if not _nonempty_text(anchors.get(key)):
            raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    for key in REQUIRED_QUALIFICATION_ROUTES:
        if not _nonempty_text(routes.get(key)):
            raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    for key in REQUIRED_CAP_RULE_IDS:
        if not _nonempty_text(caps.get(key)):
            raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    if not _nonempty_text(benchmark.get("scope_statement")):
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    if not _nonempty_text(benchmark.get("disclaimer")):
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    return copy


def _track_config(rubric: Mapping[str, Any], track: str) -> Mapping[str, Any]:
    tracks = rubric.get("tracks")
    if not isinstance(tracks, Mapping):
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    config = tracks.get(track)
    if not isinstance(config, Mapping):
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    if not isinstance(config.get("categories"), list) or not isinstance(
        config.get("criteria"), list
    ):
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    return config


def _assert_unique_ids(rows: Sequence[Mapping[str, Any]], key: str) -> None:
    seen: set[str] = set()
    for row in rows:
        value = str(row[key])
        if value in seen:
            raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
        seen.add(value)


def _whole_percent(score: int, max_points: int) -> int:
    if max_points <= 0:
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    ratio = (Decimal(score) * Decimal(100)) / Decimal(max_points)
    return int(ratio.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _category_breakdown(
    categories: Sequence[Mapping[str, Any]],
    results: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for category in categories:
        category_id = str(category["id"])
        result = results[category_id]
        if int(result["max_points"]) != int(category["max_points"]):
            raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
        score = int(result["final_score"])
        max_points = int(category["max_points"])
        rows.append(
            {
                "category_id": category_id,
                "label": str(category["display_name"]),
                "score": score,
                "max_points": max_points,
                "percentage": _whole_percent(score, max_points),
                "pre_cap_score": int(result["pre_cap_score"]),
            }
        )
    return rows


def _strongest_area(
    rows: Sequence[Mapping[str, Any]], rubric_order: Sequence[str]
) -> dict[str, Any]:
    order = {category_id: index for index, category_id in enumerate(rubric_order)}

    def sort_key(row: Mapping[str, Any]) -> tuple[Decimal, int]:
        ratio = Decimal(int(row["score"])) / Decimal(int(row["max_points"]))
        return (ratio, -order[str(row["category_id"])])

    winner = max(rows, key=sort_key)
    return {
        "category_id": str(winner["category_id"]),
        "label": str(winner["label"]),
        "score": int(winner["score"]),
        "max_points": int(winner["max_points"]),
        "percentage": int(winner["percentage"]),
    }


def _anchor_label(anchor: str, copy: Mapping[str, Any]) -> str:
    anchors = copy["evidence_anchor_labels"]
    routes = copy["qualification_route_labels"]
    if anchor in anchors:
        return str(anchors[anchor])
    if anchor in routes:
        return str(routes[anchor])
    raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)


def _criterion_lookup(
    criterion_id: str,
    criterion_by_id: Mapping[str, Mapping[str, Any]],
    category_by_id: Mapping[str, Mapping[str, Any]],
    criterion_results: Mapping[str, Mapping[str, Any]],
) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]:
    criterion = criterion_by_id.get(criterion_id)
    result = criterion_results.get(criterion_id)
    if not isinstance(criterion, Mapping) or not isinstance(result, Mapping):
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    category = category_by_id.get(str(criterion["category_id"]))
    if not isinstance(category, Mapping):
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    return criterion, category, result


def _strength_row(
    item: Mapping[str, Any],
    criterion_by_id: Mapping[str, Mapping[str, Any]],
    category_by_id: Mapping[str, Mapping[str, Any]],
    criterion_results: Mapping[str, Mapping[str, Any]],
    copy: Mapping[str, Any],
) -> dict[str, Any]:
    criterion_id = str(item["criterion_id"])
    criterion, category, result = _criterion_lookup(
        criterion_id, criterion_by_id, category_by_id, criterion_results
    )
    return {
        "criterion_id": criterion_id,
        "criterion_label": str(criterion["display_name"]),
        "category_id": str(category["id"]),
        "category_label": str(category["display_name"]),
        "awarded_points": int(result["awarded_points"]),
        "max_points": int(result["max_points"]),
        "anchor": str(result["anchor"]),
        "anchor_label": _anchor_label(str(result["anchor"]), copy),
        "evidence_note": str(result["evidence_note"]),
    }


def _gap_row(
    item: Mapping[str, Any],
    criterion_by_id: Mapping[str, Mapping[str, Any]],
    category_by_id: Mapping[str, Mapping[str, Any]],
    criterion_results: Mapping[str, Mapping[str, Any]],
    copy: Mapping[str, Any],
) -> dict[str, Any]:
    criterion_id = str(item["criterion_id"])
    criterion, category, result = _criterion_lookup(
        criterion_id, criterion_by_id, category_by_id, criterion_results
    )
    return {
        "criterion_id": criterion_id,
        "criterion_label": str(criterion["display_name"]),
        "category_id": str(category["id"]),
        "category_label": str(category["display_name"]),
        "point_gap": int(item["point_gap"]),
        "gap_ratio": item["gap_ratio"],
        "current_anchor": str(result["anchor"]),
        "current_anchor_label": _anchor_label(str(result["anchor"]), copy),
        "awarded_points": int(result["awarded_points"]),
        "max_points": int(result["max_points"]),
    }


def _action_row(
    item: Mapping[str, Any],
    criterion_by_id: Mapping[str, Mapping[str, Any]],
    action_catalog: Mapping[str, Any],
    copy: Mapping[str, Any],
) -> dict[str, Any]:
    action_id = str(item["action_id"])
    catalog_action = _action_by_id(action_catalog, action_id)
    for field in (
        "criterion_id",
        "current_anchor",
        "target_anchor",
        "required_output",
        "completion_check",
    ):
        if item.get(field) != catalog_action.get(field):
            raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    criterion = criterion_by_id.get(str(item["criterion_id"]))
    if not isinstance(criterion, Mapping):
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    return {
        "priority_order": int(item["priority_order"]),
        "action_id": action_id,
        "criterion_id": str(item["criterion_id"]),
        "criterion_label": str(criterion["display_name"]),
        "current_anchor": str(item["current_anchor"]),
        "current_anchor_label": _anchor_label(str(item["current_anchor"]), copy),
        "target_anchor": str(item["target_anchor"]),
        "target_anchor_label": _anchor_label(str(item["target_anchor"]), copy),
        "candidate_instruction": str(catalog_action["candidate_instruction"]),
        "required_output": str(catalog_action["required_output"]),
        "completion_check": str(catalog_action["completion_check"]),
        "action_type": str(catalog_action["action_type"]),
    }


def _action_by_id(catalog: Mapping[str, Any], action_id: str) -> Mapping[str, Any]:
    actions = catalog.get("actions")
    if not isinstance(actions, list):
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    for action in actions:
        if isinstance(action, Mapping) and action.get("action_id") == action_id:
            return action
    raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)


def _project_row(
    recommendation: object,
    track: str,
    project_catalog: Mapping[str, Any],
) -> dict[str, Any] | None:
    if recommendation is None:
        return None
    if recommendation == REVIEW_SENTINEL:
        return {"status": "REVIEW_REQUIRED"}
    if not isinstance(recommendation, Mapping):
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    project_id = str(recommendation.get("project_id", ""))
    catalogue_version = str(recommendation.get("catalogue_version", ""))
    project = _project_by_id(project_catalog, project_id)
    if str(project.get("track")) != track:
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    catalog_version = str(project.get("catalog_version", ""))
    if catalogue_version != catalog_version:
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    row: dict[str, Any] = {
        "status": "RECOMMENDED",
        "project_id": project_id,
        "title": str(project["title"]),
        "scenario": str(project["scenario"]),
        "required_foundations": list(project["required_foundations"]),
        "required_outputs": list(project["required_outputs"]),
        "completion_checks": list(project["completion_checks"]),
        "source_blueprint": str(project["source_blueprint"]),
        "catalogue_version": catalogue_version,
    }
    if "data_requirement" in project:
        row["data_requirement"] = str(project["data_requirement"])
    return row


def _project_by_id(catalog: Mapping[str, Any], project_id: str) -> Mapping[str, Any]:
    projects = catalog.get("projects")
    if not isinstance(projects, list):
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    for project in projects:
        if isinstance(project, Mapping) and project.get("project_id") == project_id:
            return project
    raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)


def _criterion_row(
    criterion: Mapping[str, Any],
    criterion_results: Mapping[str, Mapping[str, Any]],
    category_by_id: Mapping[str, Mapping[str, Any]],
    copy: Mapping[str, Any],
) -> dict[str, Any]:
    criterion_id = str(criterion["id"])
    result = criterion_results[criterion_id]
    category = category_by_id[str(criterion["category_id"])]
    return {
        "criterion_id": criterion_id,
        "criterion_label": str(criterion["display_name"]),
        "category_id": str(category["id"]),
        "category_label": str(category["display_name"]),
        "awarded_points": int(result["awarded_points"]),
        "max_points": int(result["max_points"]),
        "anchor": str(result["anchor"]),
        "anchor_label": _anchor_label(str(result["anchor"]), copy),
        "evidence_note": str(result["evidence_note"]),
        "flags": list(result.get("flags") or []),
    }


def _category_cap(
    item: Mapping[str, Any],
    category_by_id: Mapping[str, Mapping[str, Any]],
    copy: Mapping[str, Any],
) -> dict[str, Any]:
    rule_id = str(item["rule_id"])
    category_id = str(item["category_id"])
    category = category_by_id.get(category_id)
    if not isinstance(category, Mapping):
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    return {
        "rule_id": rule_id,
        "rule_label": _cap_label(rule_id, copy),
        "category_id": category_id,
        "category_label": str(category["display_name"]),
        "cap": int(item["cap"]),
    }


def _overall_cap(item: Mapping[str, Any], copy: Mapping[str, Any]) -> dict[str, Any]:
    rule_id = str(item["rule_id"])
    return {
        "rule_id": rule_id,
        "rule_label": _cap_label(rule_id, copy),
        "cap": int(item["cap"]),
    }


def _cap_label(rule_id: str, copy: Mapping[str, Any]) -> str:
    labels = copy["cap_rule_labels"]
    if rule_id not in labels or not _nonempty_text(labels.get(rule_id)):
        raise ReportingHalt(ERROR_REPORT_RULESET_INVALID)
    return str(labels[rule_id])


def _nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())

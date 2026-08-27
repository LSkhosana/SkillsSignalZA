"""Configuration-validation tests for the Package B action catalogue."""

import hashlib
import json
from collections.abc import Mapping
from typing import Any

import pytest

from app.engine.configuration import (
    load_action_catalog_v1,
    load_rubric_v2,
)

APPROVED_TRACKS = ("software_engineering", "data_analytics")
EVIDENCE_LEVELS = (
    "missing_unverifiable",
    "named_only",
    "documented",
    "demonstrated",
)
EVIDENCE_RANK = {level: index for index, level in enumerate(EVIDENCE_LEVELS)}
LOCKED_ACTION_TYPES = {
    "missing_unverifiable": "create_evidence",
    "named_only": "add_context",
    "documented": "demonstrate_evidence",
    "demonstrated": "package_evidence",
}
QUALIFICATION_SUFFIXES = (
    "completed",
    "in_progress",
    "experience",
    "bootcamp",
    "adjacent",
    "none",
)
APPROVED_ACTION_CATALOG_SHA256 = "73448765ed3c90313af39ebe4900a56f3152d6f12fc32555e6d044ffb1927e12"
FORBIDDEN_ACTION_TEXT = (
    "hiring guarantee",
    "guaranteed job",
    "guaranteed employment",
    "employability",
    "increase your score",
    "raise your score",
    "score increase",
    "will raise",
    "coursera",
    "udemy",
    "edx",
    "datacamp",
    "linkedin learning",
    "claim work you did not",
    "invent metrics",
    "misrepresent",
)
PROJECT_ADDRESSABLE = {
    "se.core.programming_language": True,
    "se.core.programming_concepts": True,
    "se.core.application_systems": True,
    "se.core.database_fundamentals": True,
    "se.core.debugging_testing": True,
    "se.tools.version_control": True,
    "se.tools.framework_library": True,
    "se.tools.database_platform": True,
    "se.tools.dev_environment": True,
    "se.tools.repository_platform": True,
    "se.tools.deployment_cloud": True,
    "se.projects.accessibility": True,
    "se.projects.problem_relevance": True,
    "se.projects.depth_ownership": True,
    "se.projects.documentation": True,
    "se.projects.outcome": True,
    "se.alignment.target_role": False,
    "se.alignment.claim_specificity": False,
    "se.alignment.description_evidence": False,
    "se.alignment.readability": False,
    "se.readiness.communication": True,
    "se.readiness.collaboration": True,
    "se.readiness.professional_exposure": False,
    "se.readiness.initiative": True,
    "se.readiness.self_management": True,
    "da.core.sql": True,
    "da.core.spreadsheets": True,
    "da.core.analysis_statistics": True,
    "da.core.cleaning": True,
    "da.core.reporting": True,
    "da.tools.bi_visualisation": True,
    "da.tools.power_bi_alignment": True,
    "da.tools.programming": True,
    "da.tools.database_environment": True,
    "da.tools.transformation_cloud": True,
    "da.tools.integration": True,
    "da.projects.accessibility": True,
    "da.projects.context": True,
    "da.projects.process": True,
    "da.projects.findings": True,
    "da.projects.reproducibility": True,
    "da.alignment.target_role": False,
    "da.alignment.claim_specificity": False,
    "da.alignment.description_evidence": False,
    "da.alignment.readability": False,
    "da.readiness.problem_solving": True,
    "da.readiness.attention_detail": True,
    "da.readiness.collaboration": True,
    "da.readiness.communication": True,
    "da.readiness.self_management": True,
}


def _criteria(rubric: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        criterion
        for track_id in APPROVED_TRACKS
        for criterion in rubric["tracks"][track_id]["criteria"]
    ]


def _non_qualification_criteria(rubric: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        criterion
        for criterion in _criteria(rubric)
        if criterion["scoring"] != "qualification_routes"
    ]


def _qualification_criteria(rubric: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        criterion
        for criterion in _criteria(rubric)
        if criterion["scoring"] == "qualification_routes"
    ]


def _is_project_criterion(criterion_id: str) -> bool:
    return criterion_id.startswith(("se.projects.", "da.projects."))


def _track_prefix(criterion_id: str) -> str:
    return criterion_id.split(".", maxsplit=1)[0]


def _walk_text(node: object) -> list[str]:
    values: list[str] = []
    if isinstance(node, str):
        values.append(node)
    elif isinstance(node, Mapping):
        for value in node.values():
            values.extend(_walk_text(value))
    elif isinstance(node, list):
        for item in node:
            values.extend(_walk_text(item))
    return values


def _canonical_sha256(document: Mapping[str, Any]) -> str:
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _expected_target_anchor(action: Mapping[str, Any]) -> str:
    current = action["current_anchor"]
    if "qualification_route_id" in action:
        return current
    if _is_project_criterion(action["criterion_id"]) or current in {
        "documented",
        "demonstrated",
    }:
        return "demonstrated"
    return "documented"


@pytest.fixture(scope="module")
def rubric() -> dict[str, Any]:
    return load_rubric_v2()


@pytest.fixture(scope="module")
def catalog() -> dict[str, Any]:
    return load_action_catalog_v1()


@pytest.fixture(scope="module")
def actions(catalog: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return list(catalog["actions"])


def test_action_catalog_metadata_matches_contract(catalog: Mapping[str, Any]) -> None:
    assert catalog["contract_version"] == "1.0.0"
    assert catalog["rubric_version"] == "V2"
    assert catalog["catalog_version"] == "1.0.0"
    assert catalog["status"] == "approved"


def test_exactly_50_non_qualification_criteria(rubric: Mapping[str, Any]) -> None:
    assert len(_non_qualification_criteria(rubric)) == 50


def test_every_non_qualification_criterion_has_four_unique_evidence_actions(
    rubric: Mapping[str, Any],
    actions: list[Mapping[str, Any]],
) -> None:
    by_criterion: dict[str, list[Mapping[str, Any]]] = {}
    for action in actions:
        if action["current_anchor"] in EVIDENCE_LEVELS:
            by_criterion.setdefault(action["criterion_id"], []).append(action)
    expected_ids = {criterion["id"] for criterion in _non_qualification_criteria(rubric)}
    assert set(by_criterion) == expected_ids
    for criterion_id, criterion_actions in by_criterion.items():
        anchors = [action["current_anchor"] for action in criterion_actions]
        assert anchors == list(EVIDENCE_LEVELS), criterion_id
        action_ids = [action["action_id"] for action in criterion_actions]
        assert len(action_ids) == len(set(action_ids)) == 4


def test_exactly_12_qualification_route_actions(
    rubric: Mapping[str, Any],
    actions: list[Mapping[str, Any]],
) -> None:
    qualification_actions = [action for action in actions if "qualification_route_id" in action]
    assert len(qualification_actions) == 12
    by_track: dict[str, int] = {"se": 0, "da": 0}
    for action in qualification_actions:
        by_track[_track_prefix(action["criterion_id"])] += 1
    assert by_track == {"se": 6, "da": 6}
    expected_ids = {criterion["id"] for criterion in _qualification_criteria(rubric)}
    assert {action["criterion_id"] for action in qualification_actions} == expected_ids


def test_total_action_count_is_212(actions: list[Mapping[str, Any]]) -> None:
    assert len(actions) == 212


def test_every_action_references_an_existing_rubric_criterion(
    rubric: Mapping[str, Any],
    actions: list[Mapping[str, Any]],
) -> None:
    criterion_ids = {criterion["id"] for criterion in _criteria(rubric)}
    for action in actions:
        assert action["criterion_id"] in criterion_ids


def test_qualification_actions_reference_same_track_routes(
    rubric: Mapping[str, Any],
    actions: list[Mapping[str, Any]],
) -> None:
    routes_by_track = {
        track_id: {route["id"] for route in rubric["tracks"][track_id]["qualification_routes"]}
        for track_id in APPROVED_TRACKS
    }
    for action in actions:
        if "qualification_route_id" not in action:
            continue
        prefix = _track_prefix(action["criterion_id"])
        track_id = "software_engineering" if prefix == "se" else "data_analytics"
        assert action["qualification_route_id"] in routes_by_track[track_id]
        assert action["current_anchor"] == action["qualification_route_id"]
        assert action["target_anchor"] == action["qualification_route_id"]
        suffix = action["qualification_route_id"].removeprefix(f"{prefix}.qual.")
        assert suffix in QUALIFICATION_SUFFIXES


def test_action_ids_are_unique_and_follow_locked_format(actions: list[Mapping[str, Any]]) -> None:
    ids = [action["action_id"] for action in actions]
    assert len(ids) == len(set(ids))
    for action in actions:
        if "qualification_route_id" in action:
            prefix = _track_prefix(action["criterion_id"])
            suffix = action["qualification_route_id"].removeprefix(f"{prefix}.qual.")
            expected = f"action.v1.{action['criterion_id']}.{suffix}"
        else:
            expected = f"action.v1.{action['criterion_id']}.{action['current_anchor']}"
        assert action["action_id"] == expected


def test_missing_and_named_only_actions_never_target_a_lower_level(
    actions: list[Mapping[str, Any]],
) -> None:
    for action in actions:
        if action["current_anchor"] not in {"missing_unverifiable", "named_only"}:
            continue
        assert EVIDENCE_RANK[action["target_anchor"]] >= EVIDENCE_RANK[action["current_anchor"]]


def test_documented_actions_target_demonstrated(actions: list[Mapping[str, Any]]) -> None:
    for action in actions:
        if action["current_anchor"] == "documented":
            assert action["target_anchor"] == "demonstrated"


def test_demonstrated_actions_remain_demonstrated_and_use_package_evidence(
    actions: list[Mapping[str, Any]],
) -> None:
    for action in actions:
        if action["current_anchor"] == "demonstrated":
            assert action["target_anchor"] == "demonstrated"
            assert action["action_type"] == "package_evidence"


def test_ordinary_evidence_action_types_are_locked(actions: list[Mapping[str, Any]]) -> None:
    for action in actions:
        if action["current_anchor"] in LOCKED_ACTION_TYPES:
            assert action["action_type"] == LOCKED_ACTION_TYPES[action["current_anchor"]]
            assert "target_evidence_level" not in action


def test_every_action_has_non_empty_instruction_output_and_check(
    actions: list[Mapping[str, Any]],
) -> None:
    for action in actions:
        assert action["candidate_instruction"].strip()
        assert action["required_output"].strip()
        assert action["completion_check"].strip()


def test_project_criteria_target_demonstrated_for_weaker_states(
    actions: list[Mapping[str, Any]],
) -> None:
    for action in actions:
        if not _is_project_criterion(action["criterion_id"]):
            continue
        if action["current_anchor"] in {"missing_unverifiable", "named_only", "documented"}:
            assert action["target_anchor"] == "demonstrated"


def test_target_anchors_match_locked_mapping(actions: list[Mapping[str, Any]]) -> None:
    for action in actions:
        assert action["target_anchor"] == _expected_target_anchor(action)


def test_qualification_packaging_does_not_change_the_scored_route(
    actions: list[Mapping[str, Any]],
) -> None:
    for action in actions:
        if "qualification_route_id" not in action:
            continue
        assert action["current_anchor"] == action["target_anchor"]


def test_project_addressable_matches_criterion_matrix(actions: list[Mapping[str, Any]]) -> None:
    for action in actions:
        if action["criterion_id"] not in PROJECT_ADDRESSABLE:
            assert "qualification_route_id" in action
            assert action["project_addressable"] is False
            continue
        assert action["project_addressable"] is PROJECT_ADDRESSABLE[action["criterion_id"]]


def test_no_forbidden_recommendation_language(catalog: Mapping[str, Any]) -> None:
    combined = " ".join(_walk_text(catalog)).lower()
    for phrase in FORBIDDEN_ACTION_TEXT:
        assert phrase not in combined, phrase


def test_selection_policy_limits_priority_actions_without_forcing_a_minimum(
    catalog: Mapping[str, Any],
) -> None:
    policy = catalog["selection_policy"]
    assert policy["priority_action_limit"] == 5
    assert policy["active_hard_cap_gaps_first"] is True
    assert policy["force_minimum"] is False


def test_load_action_catalog_v1_rejects_non_object(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.engine.configuration.load_json", lambda path: ["not-an-object"])
    with pytest.raises(TypeError, match="JSON object"):
        load_action_catalog_v1()


def test_approved_action_catalog_canonical_hash_is_locked(catalog: Mapping[str, Any]) -> None:
    assert _canonical_sha256(catalog) == APPROVED_ACTION_CATALOG_SHA256

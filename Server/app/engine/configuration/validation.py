"""Load and validate versioned scoring configuration before any candidate score."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.engine.configuration import (
    load_action_catalog_v1,
    load_project_catalog_v1,
    load_rubric_v2,
)
from app.engine.outcomes import engine_outcome

ACTIVE_CONTRACT_VERSION = "1.2.0"
ACTIVE_RUBRIC_VERSION = "V2"
ACTIVE_CATALOG_VERSION = "1.0.0"
APPROVED_TRACKS = ("software_engineering", "data_analytics")
ORDINARY_ANCHORS = (
    "missing_unverifiable",
    "named_only",
    "documented",
    "demonstrated",
)


@dataclass(frozen=True)
class EngineConfiguration:
    """Validated rubric, action catalogue, and project catalogue."""

    rubric: dict[str, Any]
    action_catalog: dict[str, Any]
    project_catalog: dict[str, Any]


def load_validated_engine_configuration(
    *,
    contract_version: str = ACTIVE_CONTRACT_VERSION,
    rubric_version: str = ACTIVE_RUBRIC_VERSION,
    action_catalog_version: str = ACTIVE_CATALOG_VERSION,
    project_catalog_version: str = ACTIVE_CATALOG_VERSION,
    rubric: dict[str, Any] | None = None,
    action_catalog: dict[str, Any] | None = None,
    project_catalog: dict[str, Any] | None = None,
) -> EngineConfiguration | dict[str, Any]:
    """Load explicit configuration versions and validate Contract 1.2 invariants."""
    known = (
        contract_version == ACTIVE_CONTRACT_VERSION
        and rubric_version == ACTIVE_RUBRIC_VERSION
        and action_catalog_version == ACTIVE_CATALOG_VERSION
        and project_catalog_version == ACTIVE_CATALOG_VERSION
    )
    if not known and rubric is None:
        return engine_outcome("RULESET_NOT_FOUND", error_code="RULESET_NOT_FOUND")
    try:
        loaded_rubric = rubric if rubric is not None else load_rubric_v2()
        loaded_actions = action_catalog if action_catalog is not None else load_action_catalog_v1()
        loaded_projects = (
            project_catalog if project_catalog is not None else load_project_catalog_v1()
        )
    except (OSError, TypeError, ValueError):
        return engine_outcome("RULESET_INVALID", error_code="RULESET_INVALID")
    configuration = EngineConfiguration(
        rubric=loaded_rubric,
        action_catalog=loaded_actions,
        project_catalog=loaded_projects,
    )
    if not _configuration_is_valid(configuration, contract_version, rubric_version):
        return engine_outcome("RULESET_INVALID", error_code="RULESET_INVALID")
    return configuration


def recognized_rule_ids(rubric: dict[str, Any]) -> set[str]:
    """Return every configuration rule ID the scoring context may declare."""
    ids: set[str] = set()
    for track in rubric["tracks"].values():
        for criterion in track["criteria"]:
            ids.add(criterion["rule_id"])
        for collection in ("category_caps", "overall_caps", "criterion_caps", "special_rules"):
            for item in track.get(collection, []):
                ids.add(item["rule_id"])
    return ids


def recognized_project_exclusions(project_catalog: dict[str, Any]) -> set[str]:
    """Return exclusion IDs the scoring context may declare."""
    ids = set(project_catalog.get("global_exclusion_conditions") or [])
    for project in project_catalog["projects"]:
        ids.update(project.get("exclusion_conditions") or [])
    return ids


def _configuration_is_valid(
    configuration: EngineConfiguration,
    contract_version: str,
    rubric_version: str,
) -> bool:
    rubric = configuration.rubric
    actions = configuration.action_catalog
    projects = configuration.project_catalog
    if rubric.get("contract_version") != contract_version:
        return False
    if rubric.get("rubric_version") != rubric_version:
        return False
    if actions.get("contract_version") != contract_version:
        return False
    if projects.get("contract_version") != contract_version:
        return False
    if actions.get("catalog_version") != ACTIVE_CATALOG_VERSION:
        return False
    if projects.get("catalog_version") != ACTIVE_CATALOG_VERSION:
        return False
    if list(rubric.get("supported_tracks") or []) != list(APPROVED_TRACKS):
        return False
    if not _bands_cover_zero_to_one_hundred(rubric.get("score_bands") or []):
        return False
    criterion_ids: set[str] = set()
    category_ids: set[str] = set()
    rule_ids: set[str] = set()
    for track_id in APPROVED_TRACKS:
        track = rubric["tracks"].get(track_id)
        if not isinstance(track, dict):
            return False
        categories = track["categories"]
        criteria = track["criteria"]
        if sum(item["max_points"] for item in categories) != 100:
            return False
        if sum(item["max_points"] for item in criteria) != 100:
            return False
        by_category = {item["id"]: 0 for item in categories}
        for criterion in criteria:
            by_category[criterion["category_id"]] += criterion["max_points"]
            if criterion["id"] in criterion_ids:
                return False
            criterion_ids.add(criterion["id"])
            if criterion["rule_id"] in rule_ids:
                return False
            rule_ids.add(criterion["rule_id"])
        for category in categories:
            if category["id"] in category_ids:
                return False
            category_ids.add(category["id"])
            if by_category[category["id"]] != category["max_points"]:
                return False
        routes = track["qualification_routes"]
        highest = max(route["points"] for route in routes)
        if track_id == "software_engineering" and highest != 10:
            return False
        if track_id == "data_analytics" and highest != 7:
            return False
        for cap in track["overall_caps"]:
            if cap["rule_id"] in rule_ids:
                return False
            rule_ids.add(cap["rule_id"])
            if cap["cap_points"] > 100:
                return False
        for cap in track["category_caps"]:
            if cap["rule_id"] in rule_ids:
                return False
            rule_ids.add(cap["rule_id"])
            if cap["cap_points"] > cap["category_maximum"]:
                return False
        for cap in track.get("criterion_caps", []):
            if cap["rule_id"] in rule_ids:
                return False
            rule_ids.add(cap["rule_id"])
            if cap["cap_points"] > cap["criterion_maximum"]:
                return False
        for rule in track.get("special_rules", []):
            if rule["rule_id"] in rule_ids:
                return False
            rule_ids.add(rule["rule_id"])
        no_language = [
            cap for cap in track["overall_caps"] if cap["rule_id"].endswith(".no_language")
        ]
        no_sql = [cap for cap in track["overall_caps"] if cap["rule_id"].endswith(".no_sql")]
        if track_id == "software_engineering" and not (
            no_language and no_language[0]["cap_points"] == 59
        ):
            return False
        if track_id == "data_analytics" and not (no_sql and no_sql[0]["cap_points"] == 79):
            return False
    action_ids: set[str] = set()
    for action in actions["actions"]:
        if action["action_id"] in action_ids:
            return False
        action_ids.add(action["action_id"])
        if action["criterion_id"] not in criterion_ids:
            return False
        if action["current_anchor"] not in (
            *ORDINARY_ANCHORS,
            *_qualification_route_ids(rubric),
        ):
            return False
    if len(actions["actions"]) != 212:
        return False
    project_ids: set[str] = set()
    for project in projects["projects"]:
        if project["project_id"] in project_ids:
            return False
        project_ids.add(project["project_id"])
        if project["track"] not in APPROVED_TRACKS:
            return False
        if any(criterion_id not in criterion_ids for criterion_id in project["core_criterion_ids"]):
            return False
    return len(projects["projects"]) == 8


def _qualification_route_ids(rubric: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for track in rubric["tracks"].values():
        ids.update(route["id"] for route in track["qualification_routes"])
    return ids


def _bands_cover_zero_to_one_hundred(bands: list[dict[str, Any]]) -> bool:
    covered: set[int] = set()
    for band in bands:
        low = band["min"]
        high = band["max"]
        if high < low:
            return False
        for score in range(low, high + 1):
            if score in covered:
                return False
            covered.add(score)
    return covered == set(range(101))

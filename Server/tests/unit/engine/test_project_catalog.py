"""Configuration-validation tests for the Package B project catalogue."""

import hashlib
import json
from collections.abc import Mapping
from typing import Any

import pytest

from app.engine.configuration import (
    load_project_catalog_v1,
    load_rubric_v2,
)

APPROVED_TRACKS = ("software_engineering", "data_analytics")
LOCKED_PROJECT_IDS = (
    "se.project.01_operations_workflow",
    "se.project.02_application_tracker_interface",
    "se.project.03_service_request_api",
    "se.project.04_support_ticket_classifier",
    "da.project.01_kpi_dashboard",
    "da.project.02_sla_analysis",
    "da.project.03_customer_performance_investigation",
    "da.project.04_repeatable_data_quality_workflow",
)
GLOBAL_EXCLUSIONS = (
    "track_mismatch",
    "blocking_review_unresolved",
    "no_positive_core_gap_coverage",
)
CLASSIFIER_EXCLUSIONS = (
    "python_not_explicit",
    "api_foundation_missing_unverifiable",
    "safe_labelled_data_unavailable",
)
FORBIDDEN_PROJECT_TEXT = (
    "guaranteed employment",
    "promise employment",
    "will get you hired",
    "hiring guarantee",
    "score increase",
    "increase your score",
    "guaranteed completion",
    "complete in 7 days",
    "complete in 30 days",
    "complete within",
)
SAFE_DATA_MARKERS = ("public", "anonymis", "synthetic")
APPROVED_PROJECT_CATALOG_SHA256 = "4517a58a88d67d4f5eca8af62f74385902144eb780aede3d90b898ab8cec0e2d"


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


def _criteria_by_track(rubric: Mapping[str, Any]) -> dict[str, dict[str, Mapping[str, Any]]]:
    return {
        track_id: {
            criterion["id"]: criterion for criterion in rubric["tracks"][track_id]["criteria"]
        }
        for track_id in APPROVED_TRACKS
    }


def _project_category_ids(rubric: Mapping[str, Any], track_id: str) -> set[str]:
    return {
        criterion["id"]
        for criterion in rubric["tracks"][track_id]["criteria"]
        if criterion["category_id"].endswith(".projects")
    }


def _is_dataset_based(project: Mapping[str, Any]) -> bool:
    return project["track"] == "data_analytics" or project["project_id"].endswith(
        "support_ticket_classifier"
    )


@pytest.fixture(scope="module")
def rubric() -> dict[str, Any]:
    return load_rubric_v2()


@pytest.fixture(scope="module")
def catalog() -> dict[str, Any]:
    return load_project_catalog_v1()


@pytest.fixture(scope="module")
def projects(catalog: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return list(catalog["projects"])


def test_exactly_eight_projects_four_per_track(projects: list[Mapping[str, Any]]) -> None:
    assert len(projects) == 8
    by_track = {track_id: 0 for track_id in APPROVED_TRACKS}
    for project in projects:
        by_track[project["track"]] += 1
    assert by_track == {"software_engineering": 4, "data_analytics": 4}


def test_project_catalog_metadata_matches_contract(catalog: Mapping[str, Any]) -> None:
    assert catalog["contract_version"] == "1.2.0"
    assert catalog["rubric_version"] == "V2"
    assert catalog["catalog_version"] == "1.0.0"
    assert catalog["status"] == "approved"


def test_project_ids_are_unique_and_locked(projects: list[Mapping[str, Any]]) -> None:
    ids = [project["project_id"] for project in projects]
    assert ids == list(LOCKED_PROJECT_IDS)
    assert len(ids) == len(set(ids))


def test_every_project_references_exactly_one_approved_track(
    projects: list[Mapping[str, Any]],
) -> None:
    for project in projects:
        assert project["track"] in APPROVED_TRACKS
        prefix = "se" if project["track"] == "software_engineering" else "da"
        assert project["project_id"].startswith(f"{prefix}.project.")


def test_core_and_optional_criteria_exist_on_the_same_track(
    rubric: Mapping[str, Any],
    projects: list[Mapping[str, Any]],
) -> None:
    by_track = _criteria_by_track(rubric)
    for project in projects:
        known = by_track[project["track"]]
        for criterion_id in [*project["core_criterion_ids"], *project["optional_criterion_ids"]]:
            assert criterion_id in known


def test_core_and_optional_coverage_do_not_overlap(projects: list[Mapping[str, Any]]) -> None:
    for project in projects:
        core = set(project["core_criterion_ids"])
        optional = set(project["optional_criterion_ids"])
        assert not core.intersection(optional), project["project_id"]
        assert len(core) == len(project["core_criterion_ids"])
        assert len(optional) == len(project["optional_criterion_ids"])


def test_every_project_has_foundations_outputs_checks_exclusions_and_source(
    projects: list[Mapping[str, Any]],
) -> None:
    for project in projects:
        assert project["required_foundations"]
        assert project["required_outputs"]
        assert project["completion_checks"]
        assert project["exclusion_conditions"]
        assert project["source_blueprint"].strip()
        assert all(item.strip() for item in project["required_foundations"])
        assert all(item.strip() for item in project["required_outputs"])
        assert all(item.strip() for item in project["completion_checks"])


def test_every_project_covers_its_track_project_category_in_core(
    rubric: Mapping[str, Any],
    projects: list[Mapping[str, Any]],
) -> None:
    for project in projects:
        required = _project_category_ids(rubric, project["track"])
        assert required.issubset(set(project["core_criterion_ids"]))


def test_global_exclusion_conditions_are_present(
    catalog: Mapping[str, Any],
    projects: list[Mapping[str, Any]],
) -> None:
    assert catalog["global_exclusion_conditions"] == list(GLOBAL_EXCLUSIONS)
    for project in projects:
        for condition in GLOBAL_EXCLUSIONS:
            assert condition in project["exclusion_conditions"]


def test_dataset_based_projects_require_safe_or_declared_data(
    projects: list[Mapping[str, Any]],
) -> None:
    dataset_projects = [project for project in projects if _is_dataset_based(project)]
    assert len(dataset_projects) == 5
    for project in dataset_projects:
        requirement = " ".join(_walk_text(project)).lower()
        assert all(marker in requirement for marker in SAFE_DATA_MARKERS)
        assert "confidential" in requirement


def test_selection_policy_uses_positive_core_gaps_and_stable_ids(
    catalog: Mapping[str, Any],
) -> None:
    policy = catalog["selection_policy"]
    assert policy["coverage_inputs"] == "positive_core_covered_point_gaps"
    assert policy["recommended_count"] == 1
    assert policy["tie_break"] == "stable_project_id"


def test_optional_criteria_do_not_contribute_to_coverage_score(
    catalog: Mapping[str, Any],
) -> None:
    assert catalog["selection_policy"]["optional_criteria_contribute_to_score"] is False


def test_zero_positive_coverage_returns_review_required(catalog: Mapping[str, Any]) -> None:
    assert (
        catalog["selection_policy"]["zero_positive_coverage_outcome"]
        == "PROJECT_RECOMMENDATION_REVIEW_REQUIRED"
    )


def test_classifier_includes_python_api_and_safe_data_exclusions(
    projects: list[Mapping[str, Any]],
) -> None:
    classifier = next(
        project
        for project in projects
        if project["project_id"] == "se.project.04_support_ticket_classifier"
    )
    for condition in CLASSIFIER_EXCLUSIONS:
        assert condition in classifier["exclusion_conditions"]


def test_required_foundations_are_not_automatic_exclusions(
    projects: list[Mapping[str, Any]],
) -> None:
    for project in projects:
        extras = [
            condition
            for condition in project["exclusion_conditions"]
            if condition not in GLOBAL_EXCLUSIONS
        ]
        for foundation in project["required_foundations"]:
            assert foundation not in extras
        if project["project_id"] == "se.project.04_support_ticket_classifier":
            assert extras == list(CLASSIFIER_EXCLUSIONS)


def test_no_project_promises_employment_score_increase_or_completion_time(
    catalog: Mapping[str, Any],
) -> None:
    combined = " ".join(_walk_text(catalog)).lower()
    for phrase in FORBIDDEN_PROJECT_TEXT:
        assert phrase not in combined, phrase


def test_load_project_catalog_v1_rejects_non_object(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.engine.configuration.load_json", lambda path: ["not-an-object"])
    with pytest.raises(TypeError, match="JSON object"):
        load_project_catalog_v1()


def test_approved_project_catalog_canonical_hash_is_locked(catalog: Mapping[str, Any]) -> None:
    assert _canonical_sha256(catalog) == APPROVED_PROJECT_CATALOG_SHA256

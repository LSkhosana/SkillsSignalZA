"""Package C golden candidate fixture validation and invariant tests."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator, Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from app.engine.configuration import (
    load_action_catalog_v1,
    load_json,
    load_project_catalog_v1,
    load_rubric_v2,
)

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "golden_candidates"
SCHEMA_DIR = Path(__file__).resolve().parents[3] / "app" / "schemas"
FIXTURE_SCHEMA_PATH = FIXTURE_DIR / "golden_fixture.schema.json"
MANIFEST_PATH = FIXTURE_DIR / "manifest.json"
LOCKED_MANIFEST_SHA256 = "b953d0ba670d5daf606a084a0fa74bc65655be3a5bf0896ead19ca8870712289"
LOCKED_CONTRACT_VERSION = "1.2.0"
LOCKED_RUBRIC_VERSION = "V2"
SECRET_SENTINEL = "SKILLSIGNALZA_GOLDEN_SECRET_DO_NOT_LEAK_7f9c2e"
REVIEW_SENTINEL = "PROJECT_RECOMMENDATION_REVIEW_REQUIRED"
IDENTITY_FIELDS = {"assessment_id", "run_id", "submitted_at", "assessed_at"}
CREDENTIAL_PATTERNS = (
    re.compile(r":[^/\s]+@"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"Traceback \(most recent call last\)"),
)
LOCKED_FILENAMES = (
    "c01_se_full_score.json",
    "c02_da_full_score.json",
    "c03_se_no_language_cap.json",
    "c04_se_named_language.json",
    "c05_se_framework_only.json",
    "c06_se_cv_only_project.json",
    "c07_da_no_sql_cap.json",
    "c08_da_named_sql.json",
    "c09_da_database_only.json",
    "c10_da_cv_only_project.json",
    "c11_da_google_sheets_ceiling.json",
    "c12_da_context_free_dashboard.json",
    "c13_da_power_bi_alignment.json",
    "c14_inaccessible_link.json",
    "c15_conflicting_sources_review.json",
    "c16_unsupported_team_player.json",
    "c17_qualification_isolation.json",
    "c18_duplicate_claim_normalization.json",
    "c19_band_boundaries.json",
    "c20_determinism.json",
    "c21_technical_failure_isolation.json",
    "c22_secret_exclusion.json",
)
COVERAGE_TAGS = (
    "se_full_score_configuration",
    "da_full_score_configuration",
    "se_no_language_cap",
    "se_named_language_prevents_cap",
    "se_framework_is_not_language",
    "se_cv_only_project_cap",
    "da_no_sql_cap",
    "da_named_sql_prevents_cap",
    "da_database_product_is_not_sql",
    "da_cv_only_project_cap",
    "da_google_sheets_ceiling",
    "da_context_free_dashboard",
    "da_power_bi_alignment",
    "inaccessible_link",
    "conflicting_sources",
    "unsupported_behaviour_label",
    "qualification_isolation",
    "double_counting_prevention",
    "band_boundaries",
    "deterministic_output",
    "technical_failure_isolation",
    "secret_exclusion",
)


def _canonical_sha256(document: object) -> str:
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validator(schema: Mapping[str, Any]) -> Draft202012Validator:
    return Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)


def _walk(node: object) -> Iterator[object]:
    yield node
    if isinstance(node, Mapping):
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def _band_for(score: int) -> str:
    if score <= 39:
        return "limited_application_evidence"
    if score <= 59:
        return "foundation_visible"
    if score <= 79:
        return "developing_application_readiness"
    return "strong_application_evidence"


def _strip_identity(node: object) -> object:
    if isinstance(node, Mapping):
        return {
            key: _strip_identity(value) for key, value in node.items() if key not in IDENTITY_FIELDS
        }
    if isinstance(node, list):
        return [_strip_identity(item) for item in node]
    return node


def _completed_results(fixture: Mapping[str, Any]) -> list[dict[str, Any]]:
    expected = fixture["expected"]
    results: list[dict[str, Any]] = []
    result = expected.get("assessment_result")
    if isinstance(result, dict):
        results.append(result)
    for run in expected.get("runs", []):
        run_result = run.get("assessment_result")
        if isinstance(run_result, dict):
            results.append(run_result)
    return results


def _assessment_inputs(fixture: Mapping[str, Any]) -> list[dict[str, Any]]:
    inputs: list[dict[str, Any]] = []
    top_level = fixture.get("assessment_input")
    if isinstance(top_level, dict):
        inputs.append(top_level)
    for run in fixture["expected"].get("runs", []):
        run_input = run.get("assessment_input")
        if isinstance(run_input, dict):
            inputs.append(run_input)
    return inputs


def _assert_submitted_links_have_exactly_one_matching_source(
    assessment_input: Mapping[str, Any],
    source_records: list[Mapping[str, Any]],
) -> None:
    for link in assessment_input.get("links") or []:
        expected_source_id = f"src-{link['link_id']}"
        matches = [
            source
            for source in source_records
            if source["source_id"] == expected_source_id
            and source["locator"] == link["submitted_url"]
            and source["source_type"] == link["declared_type"]
        ]
        assert len(matches) == 1, (
            assessment_input.get("candidate_ref"),
            link,
            matches,
        )


def _expected_actions(
    action_catalog: Mapping[str, Any],
    criterion_id: str,
    current_anchor: str,
) -> Mapping[str, Any]:
    matches = [
        action
        for action in action_catalog["actions"]
        if action["criterion_id"] == criterion_id and action["current_anchor"] == current_anchor
    ]
    assert len(matches) == 1, (criterion_id, current_anchor)
    return matches[0]


def _ordered_strengths(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    strengths = [
        {
            "criterion_id": item["criterion_id"],
            "awarded_points": item["awarded_points"],
            "max_points": item["max_points"],
        }
        for item in result["criterion_results"]
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
    result: Mapping[str, Any],
    overall_cap_ids: set[str],
    category_cap_ids: set[str],
) -> list[dict[str, Any]]:
    gaps = []
    for item in result["criterion_results"]:
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


def _select_project(
    project_catalog: Mapping[str, Any],
    track: str,
    result: Mapping[str, Any],
    facts: list[Mapping[str, Any]],
) -> object:
    gap_by_id = {
        item["criterion_id"]: item["max_points"] - item["awarded_points"]
        for item in result["criterion_results"]
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
        for item in result["criterion_results"]
    )
    eligible: list[tuple[int, str, Mapping[str, Any]]] = []
    for project in project_catalog["projects"]:
        exclusions = set(project["exclusion_conditions"])
        if project["track"] != track and "track_mismatch" in exclusions:
            continue
        if result["flags"] and "blocking_review_unresolved" in exclusions:
            continue
        if "python_not_explicit" in exclusions and not python_explicit:
            continue
        if "api_foundation_missing_unverifiable" in exclusions and api_missing:
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


@pytest.fixture(scope="module")
def fixture_schema() -> dict[str, Any]:
    return load_json(FIXTURE_SCHEMA_PATH)


@pytest.fixture(scope="module")
def input_schema() -> dict[str, Any]:
    return load_json(SCHEMA_DIR / "assessment_input.schema.json")


@pytest.fixture(scope="module")
def fact_schema() -> dict[str, Any]:
    return load_json(SCHEMA_DIR / "evidence_fact.schema.json")


@pytest.fixture(scope="module")
def result_schema() -> dict[str, Any]:
    return load_json(SCHEMA_DIR / "assessment_result.schema.json")


@pytest.fixture(scope="module")
def rubric() -> dict[str, Any]:
    return load_rubric_v2()


@pytest.fixture(scope="module")
def action_catalog() -> dict[str, Any]:
    return load_action_catalog_v1()


@pytest.fixture(scope="module")
def project_catalog() -> dict[str, Any]:
    return load_project_catalog_v1()


@pytest.fixture(scope="module")
def manifest() -> dict[str, Any]:
    return load_json(MANIFEST_PATH)


@pytest.fixture(scope="module")
def fixtures() -> list[tuple[Path, dict[str, Any]]]:
    loaded: list[tuple[Path, dict[str, Any]]] = []
    for filename in LOCKED_FILENAMES:
        path = FIXTURE_DIR / filename
        loaded.append((path, json.loads(path.read_text(encoding="utf-8"))))
    return loaded


def test_manifest_and_all_22_fixtures_parse_and_validate_against_fixture_schema(
    fixture_schema: dict[str, Any],
    manifest: Mapping[str, Any],
    fixtures: list[tuple[Path, dict[str, Any]]],
) -> None:
    assert manifest["package_version"] == "1.0.0"
    assert manifest["status"] == "approved"
    assert manifest["contract_version"] == LOCKED_CONTRACT_VERSION
    assert manifest["rubric_version"] == LOCKED_RUBRIC_VERSION
    assert len(fixtures) == 22
    validator = _validator(fixture_schema)
    for _path, document in fixtures:
        validator.validate(document)
    extra = deepcopy(fixtures[0][1])
    extra["unknown_top_level"] = True
    with pytest.raises(ValidationError):
        validator.validate(extra)


def test_ids_filenames_requirements_kinds_hashes_and_coverage_tags_are_unique_and_complete(
    manifest: Mapping[str, Any],
    fixtures: list[tuple[Path, dict[str, Any]]],
) -> None:
    entries = list(manifest["fixtures"])
    assert [entry["filename"] for entry in entries] == list(LOCKED_FILENAMES)
    assert [entry["acceptance_requirement"] for entry in entries] == list(range(1, 23))
    assert len({entry["fixture_id"] for entry in entries}) == 22
    assert len({entry["canonical_sha256"] for entry in entries}) == 22
    assert list(manifest["coverage_tags"]) == list(COVERAGE_TAGS)
    assert len(set(manifest["coverage_tags"])) == 22
    for entry, (path, document) in zip(entries, fixtures, strict=True):
        assert path.name == entry["filename"]
        assert document["fixture_id"] == entry["fixture_id"]
        assert document["acceptance_requirement"] == entry["acceptance_requirement"]
        assert document["fixture_kind"] == entry["fixture_kind"]
        assert document["track"] == entry["track"]
        assert _canonical_sha256(document) == entry["canonical_sha256"]
        assert document["contract_version"] == LOCKED_CONTRACT_VERSION
        assert document["rubric_version"] == LOCKED_RUBRIC_VERSION


def test_every_embedded_assessment_input_validates(
    input_schema: dict[str, Any],
    fixtures: list[tuple[Path, dict[str, Any]]],
) -> None:
    validator = _validator(input_schema)
    for _path, document in fixtures:
        assessment_input = document.get("assessment_input")
        if isinstance(assessment_input, dict):
            validator.validate(assessment_input)
        for run in document["expected"].get("runs", []):
            validator.validate(run["assessment_input"])


def test_every_embedded_evidence_fact_validates(
    fact_schema: dict[str, Any],
    fixtures: list[tuple[Path, dict[str, Any]]],
) -> None:
    validator = _validator(fact_schema)
    for _path, document in fixtures:
        for fact in document["evidence_facts"]:
            validator.validate(fact)


def test_every_embedded_completed_result_validates(
    result_schema: dict[str, Any],
    fixtures: list[tuple[Path, dict[str, Any]]],
) -> None:
    validator = _validator(result_schema)
    for _path, document in fixtures:
        for result in _completed_results(document):
            assert result["status"] == "COMPLETED"
            validator.validate(result)


def test_completed_results_have_five_categories_and_26_selected_track_criteria(
    rubric: Mapping[str, Any],
    fixtures: list[tuple[Path, dict[str, Any]]],
) -> None:
    for _path, document in fixtures:
        for result in _completed_results(document):
            track = rubric["tracks"][result["track"]]
            criteria = track["criteria"]
            categories = track["categories"]
            assert len(result["category_results"]) == 5
            assert [item["category_id"] for item in result["category_results"]] == [
                item["id"] for item in categories
            ]
            assert len(result["criterion_results"]) == 26
            assert [item["criterion_id"] for item in result["criterion_results"]] == [
                item["id"] for item in criteria
            ]
            other_prefix = "da." if result["track"] == "software_engineering" else "se."
            assert all(
                not item["criterion_id"].startswith(other_prefix)
                for item in result["criterion_results"]
            )
            by_id = {item["id"]: item for item in criteria}
            for item in result["criterion_results"]:
                configured = by_id[item["criterion_id"]]
                assert item["max_points"] == configured["max_points"]
                assert item["category_id"] == configured["category_id"]
                assert configured["rule_id"] in item["rule_ids"]
                assert item["rule_ids"]


def test_evidence_and_source_references_are_closed_and_nonzero_scores_have_accepted_facts(
    fixtures: list[tuple[Path, dict[str, Any]]],
) -> None:
    for _path, document in fixtures:
        source_ids = [source["source_id"] for source in document["source_records"]]
        assert len(source_ids) == len(set(source_ids))
        fact_ids = [fact["evidence_id"] for fact in document["evidence_facts"]]
        assert len(fact_ids) == len(set(fact_ids))
        facts = {fact["evidence_id"]: fact for fact in document["evidence_facts"]}
        for fact in document["evidence_facts"]:
            assert fact["source_id"] in source_ids
            assert fact["review_status"] == "accepted"
        for assessment_input in _assessment_inputs(document):
            if "cv" in assessment_input:
                assert any(source["source_id"] == "src-cv" for source in document["source_records"])
            _assert_submitted_links_have_exactly_one_matching_source(
                assessment_input,
                document["source_records"],
            )
        for result in _completed_results(document):
            for item in result["criterion_results"]:
                for evidence_id in item["evidence_ids"]:
                    assert evidence_id in facts
                if item["awarded_points"] > 0:
                    assert item["evidence_ids"]
                    assert all(
                        facts[evidence_id]["review_status"] == "accepted"
                        for evidence_id in item["evidence_ids"]
                    )


def test_criterion_category_raw_cap_final_and_band_arithmetic_matches_locked_matrix(
    fixtures: list[tuple[Path, dict[str, Any]]],
) -> None:
    expected = {
        "c01.se.full_score": (100, 100, 100, "strong_application_evidence", (35, 20, 15, 20, 10)),
        "c02.da.full_score": (100, 100, 100, "strong_application_evidence", (40, 25, 10, 15, 10)),
        "c03.se.no_language_cap": (82, 59, 59, "foundation_visible", (19, 18, 15, 20, 10)),
        "c04.se.named_language": (86, 100, 86, "strong_application_evidence", (23, 18, 15, 20, 10)),
        "c05.se.framework_only": (82, 59, 59, "foundation_visible", (19, 18, 15, 20, 10)),
        "c06.se.cv_only_project": (93, 100, 93, "strong_application_evidence", (35, 20, 8, 20, 10)),
        "c07.da.no_sql_cap": (85, 79, 79, "developing_application_readiness", (25, 25, 10, 15, 10)),
        "c08.da.named_sql": (90, 100, 90, "strong_application_evidence", (30, 25, 10, 15, 10)),
        "c09.da.database_only": (
            85,
            79,
            79,
            "developing_application_readiness",
            (25, 25, 10, 15, 10),
        ),
        "c10.da.cv_only_project": (96, 100, 96, "strong_application_evidence", (40, 25, 6, 15, 10)),
        "c11.da.google_sheets_ceiling": (
            97,
            100,
            97,
            "strong_application_evidence",
            (37, 25, 10, 15, 10),
        ),
        "c12.da.context_free_dashboard": (
            98,
            100,
            98,
            "strong_application_evidence",
            (40, 25, 8, 15, 10),
        ),
        "c13.da.power_bi_alignment": (1, 79, 1, "limited_application_evidence", (0, 1, 0, 0, 0)),
        "c14.se.inaccessible_link": (17, 100, 17, "limited_application_evidence", (9, 0, 8, 0, 0)),
        "c16.se.unsupported_team_player": (
            0,
            59,
            0,
            "limited_application_evidence",
            (0, 0, 0, 0, 0),
        ),
        "c17.se.qualification_isolation": (
            10,
            59,
            10,
            "limited_application_evidence",
            (0, 0, 0, 10, 0),
        ),
        "c18.da.duplicate_claim_normalization": (
            2,
            79,
            2,
            "limited_application_evidence",
            (0, 2, 0, 0, 0),
        ),
        "c22.da.secret_exclusion": (2, 79, 2, "limited_application_evidence", (0, 2, 0, 0, 0)),
    }
    by_id = {document["fixture_id"]: document for _path, document in fixtures}
    for fixture_id, (raw, cap, final, band, category_finals) in expected.items():
        result = by_id[fixture_id]["expected"]["assessment_result"]
        recomputed_raw = sum(item["final_score"] for item in result["category_results"])
        assert result["raw_total"] == raw == recomputed_raw
        assert result["applicable_overall_cap"] == cap
        assert result["final_score"] == final == min(raw, cap)
        assert result["band"] == band == _band_for(final)
        assert tuple(item["final_score"] for item in result["category_results"]) == category_finals
        for category in result["category_results"]:
            members = [
                item
                for item in result["criterion_results"]
                if item["category_id"] == category["category_id"]
            ]
            assert category["pre_cap_score"] == sum(item["awarded_points"] for item in members)
            assert category["final_score"] <= category["max_points"]
            assert category["final_score"] <= category["pre_cap_score"]


def test_section_8_scenario_assertions_hold_exactly(
    fixtures: list[tuple[Path, dict[str, Any]]],
) -> None:
    by_id = {document["fixture_id"]: document for _path, document in fixtures}

    c01 = by_id["c01.se.full_score"]["expected"]["assessment_result"]
    assert c01["material_gaps"] == []
    assert c01["priority_actions"] == []
    assert c01["project_recommendation"] == REVIEW_SENTINEL
    assert c01["overall_caps"] == []
    assert c01["category_caps"] == []

    c02 = by_id["c02.da.full_score"]["expected"]["assessment_result"]
    assert c02["material_gaps"] == []
    assert c02["priority_actions"] == []
    assert c02["project_recommendation"] == REVIEW_SENTINEL

    c03 = by_id["c03.se.no_language_cap"]["expected"]["assessment_result"]
    assert c03["overall_caps"] == [{"rule_id": "rubric.v2.se.cap.no_language", "cap": 59}]
    assert c03["material_gaps"][0]["criterion_id"] == "se.core.programming_language"
    language = next(
        item
        for item in c03["criterion_results"]
        if item["criterion_id"] == "se.core.programming_language"
    )
    assert language["anchor"] == "missing_unverifiable"
    assert language["awarded_points"] == 0

    c04 = by_id["c04.se.named_language"]["expected"]["assessment_result"]
    named = next(
        item
        for item in c04["criterion_results"]
        if item["criterion_id"] == "se.core.programming_language"
    )
    assert named["anchor"] == "named_only"
    assert named["awarded_points"] == 4
    assert c04["overall_caps"] == []

    c05 = by_id["c05.se.framework_only"]
    assert all(
        "programming_language" not in fact["rule_id"] and fact["subject"].lower() != "python"
        for fact in c05["evidence_facts"]
    )
    assert any(fact["subject"].lower() == "django" for fact in c05["evidence_facts"])
    assert c05["expected"]["assessment_result"]["final_score"] == 59

    c06 = by_id["c06.se.cv_only_project"]["expected"]["assessment_result"]
    projects = next(
        item for item in c06["category_results"] if item["category_id"] == "se.projects"
    )
    assert projects["pre_cap_score"] == 9
    assert projects["final_score"] == 8
    assert c06["category_caps"] == [
        {"rule_id": "rubric.v2.se.cap.cv_only_projects", "cap": 8, "category_id": "se.projects"}
    ]
    assert c06["overall_caps"] == []

    c07 = by_id["c07.da.no_sql_cap"]["expected"]["assessment_result"]
    assert c07["overall_caps"] == [{"rule_id": "rubric.v2.da.cap.no_sql", "cap": 79}]
    sql = next(item for item in c07["criterion_results"] if item["criterion_id"] == "da.core.sql")
    assert sql["anchor"] == "missing_unverifiable"

    c08 = by_id["c08.da.named_sql"]["expected"]["assessment_result"]
    sql_named = next(
        item for item in c08["criterion_results"] if item["criterion_id"] == "da.core.sql"
    )
    assert sql_named["anchor"] == "named_only"
    assert sql_named["awarded_points"] == 5
    assert c08["overall_caps"] == []

    c09 = by_id["c09.da.database_only"]
    assert all("da.core.sql" not in fact["rule_id"] for fact in c09["evidence_facts"])
    assert any(fact["subject"] == "PostgreSQL" for fact in c09["evidence_facts"])
    assert c09["expected"]["assessment_result"]["final_score"] == 79

    c10 = by_id["c10.da.cv_only_project"]["expected"]["assessment_result"]
    da_projects = next(
        item for item in c10["category_results"] if item["category_id"] == "da.projects"
    )
    assert da_projects["pre_cap_score"] == 9
    assert da_projects["final_score"] == 6
    assert c10["category_caps"] == [
        {"rule_id": "rubric.v2.da.cap.cv_only_projects", "cap": 6, "category_id": "da.projects"}
    ]

    c11 = by_id["c11.da.google_sheets_ceiling"]
    sheets = next(
        item
        for item in c11["expected"]["assessment_result"]["criterion_results"]
        if item["criterion_id"] == "da.core.spreadsheets"
    )
    assert sheets["anchor"] == "demonstrated"
    assert sheets["awarded_points"] == 5
    assert "rubric.v2.da.cap.google_sheets_ceiling" in sheets["rule_ids"]
    assert all(fact["subject"].lower() != "excel" for fact in c11["evidence_facts"])

    c12 = by_id["c12.da.context_free_dashboard"]["expected"]["assessment_result"]
    context = next(
        item for item in c12["criterion_results"] if item["criterion_id"] == "da.projects.context"
    )
    assert context["anchor"] == "missing_unverifiable"
    assert context["awarded_points"] == 0
    assert "rubric.v2.da.rule.context_free_dashboard" in context["rule_ids"]
    projects12 = next(
        item for item in c12["category_results"] if item["category_id"] == "da.projects"
    )
    assert projects12["final_score"] == 8
    assert projects12["final_score"] < projects12["max_points"]

    c13 = by_id["c13.da.power_bi_alignment"]["expected"]["assessment_result"]
    power_bi = next(
        item
        for item in c13["criterion_results"]
        if item["criterion_id"] == "da.tools.power_bi_alignment"
    )
    assert power_bi["anchor"] == "named_only"
    assert power_bi["awarded_points"] == 1
    assert any(cap["rule_id"] == "rubric.v2.da.cap.no_sql" for cap in c13["overall_caps"])
    assert c13["final_score"] == 1

    c14 = by_id["c14.se.inaccessible_link"]
    assert any(source["access_status"] == "inaccessible" for source in c14["source_records"])
    assert all(fact["source_id"] == "src-cv" for fact in c14["evidence_facts"])
    language14 = next(
        item
        for item in c14["expected"]["assessment_result"]["criterion_results"]
        if item["criterion_id"] == "se.core.programming_language"
    )
    assert language14["awarded_points"] == 9
    assert c14["expected"]["assessment_result"]["overall_caps"] == []
    projects14 = next(
        item
        for item in c14["expected"]["assessment_result"]["category_results"]
        if item["category_id"] == "se.projects"
    )
    assert projects14["pre_cap_score"] == projects14["final_score"] == 8

    c15 = by_id["c15.da.conflicting_sources_review"]["expected"]
    assert c15["assessment_result"] is None
    assert c15["state"] == c15["error_code"] == "REVIEW_REQUIRED"
    assert c15["review_flag"] == "MATERIAL_SOURCE_CONTRADICTION"
    assert c15["frozen_sql_evidence_level"] == "missing_unverifiable"
    assert c15["raw_score_present"] is False
    assert c15["final_score_present"] is False

    c16 = by_id["c16.se.unsupported_team_player"]
    collab = next(
        item
        for item in c16["expected"]["assessment_result"]["criterion_results"]
        if item["criterion_id"] == "se.readiness.collaboration"
    )
    assert collab["anchor"] == "named_only"
    assert collab["awarded_points"] == 0
    assert any(fact["explicit_text"] == "team player" for fact in c16["evidence_facts"])
    assert c16["expected"]["assessment_result"]["final_score"] == 0

    c17 = by_id["c17.se.qualification_isolation"]
    technical_types = {
        "skill_name",
        "skill_application",
        "tool_name",
        "tool_application",
        "project_proof",
        "project_context",
        "project_process",
        "project_outcome",
        "professional_behaviour",
    }
    assert all(fact["fact_type"] not in technical_types for fact in c17["evidence_facts"])
    assert any(
        cap["rule_id"] == "rubric.v2.se.cap.no_language"
        for cap in c17["expected"]["assessment_result"]["overall_caps"]
    )
    assert c17["expected"]["assessment_result"]["final_score"] == 10

    c18 = by_id["c18.da.duplicate_claim_normalization"]
    assert c18["provenance"]["occurrence_count"] == 2
    assert c18["provenance"]["canonical_fact_count"] == 1
    assert len(c18["evidence_facts"]) == 1
    programming = next(
        item
        for item in c18["expected"]["assessment_result"]["criterion_results"]
        if item["criterion_id"] == "da.tools.programming"
    )
    assert programming["awarded_points"] == 2
    assert programming["evidence_ids"] == [c18["evidence_facts"][0]["evidence_id"]]

    c19 = by_id["c19.band_boundaries"]["expected"]["band_table"]
    assert [(row["final_score"], row["band"]) for row in c19] == [
        (0, "limited_application_evidence"),
        (39, "limited_application_evidence"),
        (40, "foundation_visible"),
        (59, "foundation_visible"),
        (60, "developing_application_readiness"),
        (79, "developing_application_readiness"),
        (80, "strong_application_evidence"),
        (100, "strong_application_evidence"),
    ]

    c20 = by_id["c20.se.determinism"]["expected"]
    assert c20["identity_excluded_fields"] == [
        "assessment_id",
        "run_id",
        "submitted_at",
        "assessed_at",
    ]
    left = {
        "assessment_input": c20["runs"][0]["assessment_input"],
        "assessment_result": c20["runs"][0]["assessment_result"],
    }
    right = {
        "assessment_input": c20["runs"][1]["assessment_input"],
        "assessment_result": c20["runs"][1]["assessment_result"],
    }
    assert _canonical_sha256(_strip_identity(left)) == _canonical_sha256(_strip_identity(right))

    c21 = by_id["c21.technical_failure_isolation"]["expected"]
    assert c21["assessment_result"] is None
    assert [case["error_code"] for case in c21["cases"]] == [
        "CV_EXTRACTION_FAILED",
        "RULESET_INVALID",
    ]
    for case in c21["cases"]:
        assert case["assessment_result"] is None
        assert case["raw_score_present"] is False
        assert case["final_score_present"] is False
        assert case["band_present"] is False
        assert case["cannot_become_zero_score_completed_assessment"] is True

    c22 = by_id["c22.da.secret_exclusion"]
    assert c22["harness"]["secret_sentinel"] == SECRET_SENTINEL


def test_strength_gap_action_and_project_ordering_matches_contract_without_production_engine(
    action_catalog: Mapping[str, Any],
    project_catalog: Mapping[str, Any],
    fixtures: list[tuple[Path, dict[str, Any]]],
) -> None:
    overall_related = {
        "software_engineering": "se.core.programming_language",
        "data_analytics": "da.core.sql",
    }
    for _path, document in fixtures:
        for result in _completed_results(document):
            assert result["strengths"] == _ordered_strengths(result)
            overall_ids = {
                overall_related[result["track"]]
                for cap in result["overall_caps"]
                if cap["rule_id"].endswith((".no_language", ".no_sql"))
            }
            category_ids = {
                item["criterion_id"]
                for cap in result["category_caps"]
                for item in result["criterion_results"]
                if item["category_id"] == cap.get("category_id")
            }
            assert result["material_gaps"] == _ordered_gaps(result, overall_ids, category_ids)
            assert len(result["priority_actions"]) <= 5
            assert [action["priority_order"] for action in result["priority_actions"]] == list(
                range(1, len(result["priority_actions"]) + 1)
            )
            for action, gap in zip(
                result["priority_actions"],
                result["material_gaps"][:5],
                strict=True,
            ):
                criterion = next(
                    item
                    for item in result["criterion_results"]
                    if item["criterion_id"] == gap["criterion_id"]
                )
                catalog_action = _expected_actions(
                    action_catalog, gap["criterion_id"], criterion["anchor"]
                )
                assert action["action_id"] == catalog_action["action_id"]
                assert action["criterion_id"] == catalog_action["criterion_id"]
                assert action["current_anchor"] == catalog_action["current_anchor"]
                assert action["target_anchor"] == catalog_action["target_anchor"]
                assert action["required_output"] == catalog_action["required_output"]
                assert action["completion_check"] == catalog_action["completion_check"]
            recommendation = _select_project(
                project_catalog,
                result["track"],
                result,
                document["evidence_facts"],
            )
            assert result["project_recommendation"] == recommendation
            if isinstance(recommendation, str):
                assert recommendation == REVIEW_SENTINEL
            else:
                known_ids = {project["project_id"] for project in project_catalog["projects"]}
                assert recommendation["project_id"] in known_ids


def test_canonical_hashes_and_determinism_are_newline_and_platform_independent(
    manifest: Mapping[str, Any],
    fixtures: list[tuple[Path, dict[str, Any]]],
) -> None:
    crlf = json.dumps(manifest, sort_keys=True, indent=2).replace("\n", "\r\n")
    parsed = json.loads(crlf)
    assert _canonical_sha256(parsed) == LOCKED_MANIFEST_SHA256
    assert _canonical_sha256(manifest) == LOCKED_MANIFEST_SHA256
    for entry, (_path, document) in zip(manifest["fixtures"], fixtures, strict=True):
        round_trip = json.loads(
            json.dumps(document, indent=2, sort_keys=True).replace("\n", "\r\n")
        )
        assert _canonical_sha256(round_trip) == entry["canonical_sha256"]


def test_active_configuration_metadata_is_contract_1_2_0(
    rubric: Mapping[str, Any],
    action_catalog: Mapping[str, Any],
    project_catalog: Mapping[str, Any],
) -> None:
    assert rubric["contract_version"] == LOCKED_CONTRACT_VERSION
    assert rubric["rubric_version"] == LOCKED_RUBRIC_VERSION
    assert action_catalog["contract_version"] == LOCKED_CONTRACT_VERSION
    assert action_catalog["catalog_version"] == "1.0.0"
    assert len(action_catalog["actions"]) == 212
    assert project_catalog["contract_version"] == LOCKED_CONTRACT_VERSION
    assert project_catalog["catalog_version"] == "1.0.0"
    assert len(project_catalog["projects"]) == 8


def test_failure_and_review_fixtures_contain_no_completed_result_or_score(
    fixtures: list[tuple[Path, dict[str, Any]]],
) -> None:
    for _path, document in fixtures:
        if document["fixture_kind"] not in {"review_required", "technical_failure", "band_table"}:
            continue
        expected = document["expected"]
        assert expected["assessment_result"] is None
        dumped = json.dumps(expected)
        assert '"raw_total"' not in dumped
        assert '"final_score":' not in dumped or document["fixture_kind"] == "band_table"
        if document["fixture_kind"] == "band_table":
            assert "raw_total" not in expected
            continue
        if document["fixture_kind"] == "review_required":
            assert expected["raw_score_present"] is False
            assert expected["final_score_present"] is False
        for case in expected.get("cases", []):
            assert case["assessment_result"] is None
            assert case["raw_score_present"] is False
            assert case["final_score_present"] is False


def test_secret_sentinel_exists_only_at_harness_secret_sentinel(
    fixtures: list[tuple[Path, dict[str, Any]]],
) -> None:
    c22 = next(
        document for _path, document in fixtures if document["fixture_id"].startswith("c22.")
    )
    assert c22["harness"]["secret_sentinel"] == SECRET_SENTINEL
    assert SECRET_SENTINEL not in c22["assertions"].get("forbidden_patterns", [])

    scanned = deepcopy(c22)
    del scanned["harness"]["secret_sentinel"]
    for node in _walk(scanned):
        if isinstance(node, Mapping):
            for key, value in node.items():
                assert SECRET_SENTINEL not in str(key)
                if isinstance(value, str):
                    assert SECRET_SENTINEL not in value
        elif isinstance(node, str):
            assert SECRET_SENTINEL not in node

    public = {
        "assessment_result": c22["expected"]["assessment_result"],
        "report_data": c22["expected"]["report_data"],
    }
    for node in _walk(public):
        if isinstance(node, str):
            for pattern in CREDENTIAL_PATTERNS:
                assert pattern.search(node) is None
            assert SECRET_SENTINEL not in node


def test_fixture_package_does_not_add_production_engine_modules() -> None:
    engine_root = Path(__file__).resolve().parents[3] / "app" / "engine"
    for directory in ("scoring", "extraction", "qa", "reporting"):
        files = [
            path for path in (engine_root / directory).glob("*.py") if path.name != "__init__.py"
        ]
        assert files == []

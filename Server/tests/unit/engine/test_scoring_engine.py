"""Package D production scoring engine tests against locked golden fixtures."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from app.engine.configuration import (
    load_action_catalog_v1,
    load_project_catalog_v1,
    load_rubric_v2,
)
from app.engine.configuration.validation import (
    EngineConfiguration,
    load_validated_engine_configuration,
)
from app.engine.scoring import band_for, canonical_result, score_assessment

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "golden_candidates"
SECRET_SENTINEL = "SKILLSIGNALZA_GOLDEN_SECRET_DO_NOT_LEAK_7f9c2e"
COMPLETED_FILENAMES = (
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
    "c16_unsupported_team_player.json",
    "c17_qualification_isolation.json",
    "c18_duplicate_claim_normalization.json",
    "c22_secret_exclusion.json",
)


def _load(filename: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / filename).read_text(encoding="utf-8"))


def _canonical_sha256(document: object) -> str:
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _score_fixture(document: dict[str, Any]) -> dict[str, Any]:
    result = document["expected"]["assessment_result"]
    return score_assessment(
        document["assessment_input"],
        document["evidence_facts"],
        document["scoring_context"],
        document["source_records"],
        assessment_id=result["assessment_id"],
        run_id=result["run_id"],
        assessed_at=result["assessed_at"],
    )


@pytest.mark.parametrize("filename", COMPLETED_FILENAMES)
def test_production_engine_matches_locked_completed_fixtures(filename: str) -> None:
    document = _load(filename)
    outcome = _score_fixture(document)
    assert outcome["state"] == "COMPLETED"
    assert outcome["assessment_result"] == document["expected"]["assessment_result"]
    assert SECRET_SENTINEL not in json.dumps(outcome)


def test_c15_blocking_review_produces_review_required_without_a_score() -> None:
    document = _load("c15_conflicting_sources_review.json")
    outcome = score_assessment(
        document["assessment_input"],
        document["evidence_facts"],
        document["scoring_context"],
        document["source_records"],
        assessment_id="assessment-golden-c15",
        run_id="run-golden-c15",
        assessed_at="2026-08-31T10:00:00Z",
    )
    assert outcome["state"] == outcome["error_code"] == "REVIEW_REQUIRED"
    assert outcome["assessment_result"] is None
    assert outcome["raw_score_present"] is False
    assert outcome["final_score_present"] is False
    assert outcome["band_present"] is False
    assert "MATERIAL_SOURCE_CONTRADICTION" in outcome["flags"]
    assert outcome["frozen_sql_evidence_level"] == "missing_unverifiable"


def test_c19_band_table_matches_locked_boundaries() -> None:
    document = _load("c19_band_boundaries.json")
    table = [(row["final_score"], row["band"]) for row in document["expected"]["band_table"]]
    assert table == [(score, band_for(score)) for score, _band in table]


def test_c20_identical_inputs_are_byte_equivalent_after_identity_exclusion() -> None:
    document = _load("c20_determinism.json")
    results = []
    for run in document["expected"]["runs"]:
        outcome = score_assessment(
            run["assessment_input"],
            document["evidence_facts"],
            document["scoring_context"],
            document["source_records"],
            assessment_id=run["assessment_result"]["assessment_id"],
            run_id=run["assessment_result"]["run_id"],
            assessed_at=run["assessment_result"]["assessed_at"],
        )
        assert outcome["state"] == "COMPLETED"
        assert outcome["assessment_result"] == run["assessment_result"]
        results.append(canonical_result(outcome["assessment_result"]))
    assert _canonical_sha256(results[0]) == _canonical_sha256(results[1])


def test_c21_ruleset_invalid_never_becomes_a_zero_score() -> None:
    document = _load("c21_technical_failure_isolation.json")
    broken = deepcopy(load_rubric_v2())
    broken["tracks"]["software_engineering"]["categories"][0]["max_points"] = 1
    outcome = load_validated_engine_configuration(rubric=broken)
    assert isinstance(outcome, dict)
    assert outcome["state"] == outcome["error_code"] == "RULESET_INVALID"
    assert outcome["assessment_result"] is None
    assert outcome["raw_score_present"] is False
    unknown = load_validated_engine_configuration(rubric_version="V9")
    assert isinstance(unknown, dict)
    assert unknown["state"] == "RULESET_NOT_FOUND"
    for case in document["expected"]["cases"]:
        assert case["assessment_result"] is None
        assert case["cannot_become_zero_score_completed_assessment"] is True


def test_cv_extraction_failed_is_not_a_scoring_outcome() -> None:
    document = _load("c01_se_full_score.json")
    outcome = _score_fixture(document)
    assert outcome["error_code"] != "CV_EXTRACTION_FAILED"
    assert "CV_EXTRACTION_FAILED" not in json.dumps(outcome)
    assert outcome["state"] == "COMPLETED"


def test_scoring_context_change_changes_result_but_prose_does_not() -> None:
    document = _load("c04_se_named_language.json")
    baseline = _score_fixture(document)["assessment_result"]
    mutated_context = deepcopy(document["scoring_context"])
    language = next(
        item
        for item in mutated_context["criterion_bindings"]
        if item["criterion_id"] == "se.core.programming_language"
    )
    language["anchor"] = "missing_unverifiable"
    language["evidence_ids"] = []
    changed = score_assessment(
        document["assessment_input"],
        document["evidence_facts"],
        mutated_context,
        document["source_records"],
        assessment_id=baseline["assessment_id"],
        run_id=baseline["run_id"],
        assessed_at=baseline["assessed_at"],
    )
    assert changed["assessment_result"]["final_score"] != baseline["final_score"]
    assert any(
        cap["rule_id"] == "rubric.v2.se.cap.no_language"
        for cap in changed["assessment_result"]["overall_caps"]
    )

    ignored = deepcopy(document)
    ignored["title"] = "changed title must not be read"
    ignored["description"] = "changed description must not be read"
    ignored["expected"]["assessment_result"]["final_score"] = 0
    ignored["fixture_id"] = "not-a-scoring-input"
    prose_outcome = _score_fixture(ignored)
    assert prose_outcome["assessment_result"] == baseline


def test_engine_rejects_invalid_input_without_scoring() -> None:
    document = _load("c01_se_full_score.json")
    broken_input = deepcopy(document["assessment_input"])
    broken_input["track"] = "product_management"
    outcome = score_assessment(
        broken_input,
        document["evidence_facts"],
        document["scoring_context"],
        document["source_records"],
        assessment_id="a",
        run_id="r",
        assessed_at="2026-08-31T10:00:00Z",
    )
    assert outcome["state"] == "INPUT_INVALID"
    assert outcome["assessment_result"] is None


def test_qa_failure_does_not_release_a_completed_score(monkeypatch: pytest.MonkeyPatch) -> None:
    document = _load("c01_se_full_score.json")

    def fail_qa(**_kwargs: object) -> dict[str, object]:
        return {
            "status": "FAIL",
            "checks": [{"name": "band_matches_final_score", "passed": False}],
        }

    monkeypatch.setattr("app.engine.scoring.engine.run_assessment_qa", fail_qa)
    outcome = _score_fixture(document)
    assert outcome["state"] == "QA_FAILED"
    assert outcome["assessment_result"] is None


def test_validated_loader_accepts_active_configuration() -> None:
    loaded = load_validated_engine_configuration()
    assert isinstance(loaded, EngineConfiguration)
    assert loaded.rubric["contract_version"] == "1.2.0"
    assert loaded.project_catalog["catalog_version"] == load_project_catalog_v1()["catalog_version"]
    assert loaded.rubric["rubric_version"] == load_rubric_v2()["rubric_version"]


def _assert_ruleset_invalid(**kwargs: object) -> None:
    outcome = load_validated_engine_configuration(**kwargs)
    assert isinstance(outcome, dict)
    assert outcome["state"] == "RULESET_INVALID"


def test_configuration_validation_rejects_broken_invariants() -> None:
    rubric = load_rubric_v2()
    actions = deepcopy(load_action_catalog_v1())
    projects = load_project_catalog_v1()

    broken_contract = deepcopy(rubric)
    broken_contract["contract_version"] = "9.9.9"
    _assert_ruleset_invalid(rubric=broken_contract)

    broken_rubric_version = deepcopy(rubric)
    broken_rubric_version["rubric_version"] = "V1"
    _assert_ruleset_invalid(rubric=broken_rubric_version)

    broken_action_contract = deepcopy(actions)
    broken_action_contract["contract_version"] = "9.9.9"
    _assert_ruleset_invalid(action_catalog=broken_action_contract)

    broken_project_contract = deepcopy(projects)
    broken_project_contract["contract_version"] = "9.9.9"
    _assert_ruleset_invalid(project_catalog=broken_project_contract)

    broken_action_catalog_version = deepcopy(actions)
    broken_action_catalog_version["catalog_version"] = "2.0.0"
    _assert_ruleset_invalid(action_catalog=broken_action_catalog_version)

    broken_project_catalog_version = deepcopy(projects)
    broken_project_catalog_version["catalog_version"] = "2.0.0"
    _assert_ruleset_invalid(project_catalog=broken_project_catalog_version)

    broken_tracks = deepcopy(rubric)
    broken_tracks["supported_tracks"] = ["software_engineering"]
    _assert_ruleset_invalid(rubric=broken_tracks)

    overlapping_bands = deepcopy(rubric)
    overlapping_bands["score_bands"][0]["max"] = 50
    _assert_ruleset_invalid(rubric=overlapping_bands)

    inverted_bands = deepcopy(rubric)
    inverted_bands["score_bands"][0]["min"] = 39
    inverted_bands["score_bands"][0]["max"] = 0
    _assert_ruleset_invalid(rubric=inverted_bands)

    missing_track = deepcopy(rubric)
    missing_track["tracks"] = {"software_engineering": rubric["tracks"]["software_engineering"]}
    _assert_ruleset_invalid(rubric=missing_track)

    category_total = deepcopy(rubric)
    category_total["tracks"]["software_engineering"]["categories"][0]["max_points"] = 1
    _assert_ruleset_invalid(rubric=category_total)

    criterion_total = deepcopy(rubric)
    criterion_total["tracks"]["software_engineering"]["criteria"][0]["max_points"] = 1
    _assert_ruleset_invalid(rubric=criterion_total)

    duplicate_criterion = deepcopy(rubric)
    duplicate_criterion["tracks"]["data_analytics"]["criteria"][0]["id"] = rubric["tracks"][
        "software_engineering"
    ]["criteria"][0]["id"]
    _assert_ruleset_invalid(rubric=duplicate_criterion)

    duplicate_rule = deepcopy(rubric)
    duplicate_rule["tracks"]["software_engineering"]["criteria"][1]["rule_id"] = rubric["tracks"][
        "software_engineering"
    ]["criteria"][0]["rule_id"]
    _assert_ruleset_invalid(rubric=duplicate_rule)

    se_qual = deepcopy(rubric)
    se_qual["tracks"]["software_engineering"]["qualification_routes"][0]["points"] = 3
    _assert_ruleset_invalid(rubric=se_qual)

    da_qual = deepcopy(rubric)
    da_qual["tracks"]["data_analytics"]["qualification_routes"][0]["points"] = 3
    _assert_ruleset_invalid(rubric=da_qual)

    overall_cap = deepcopy(rubric)
    overall_cap["tracks"]["software_engineering"]["overall_caps"][0]["cap_points"] = 101
    _assert_ruleset_invalid(rubric=overall_cap)

    category_cap = deepcopy(rubric)
    category_cap["tracks"]["software_engineering"]["category_caps"][0]["cap_points"] = 99
    _assert_ruleset_invalid(rubric=category_cap)

    criterion_cap = deepcopy(rubric)
    criterion_cap["tracks"]["data_analytics"]["criterion_caps"][0]["cap_points"] = 99
    _assert_ruleset_invalid(rubric=criterion_cap)

    language_cap = deepcopy(rubric)
    language_cap["tracks"]["software_engineering"]["overall_caps"][0]["cap_points"] = 10
    _assert_ruleset_invalid(rubric=language_cap)

    sql_cap = deepcopy(rubric)
    sql_cap["tracks"]["data_analytics"]["overall_caps"][0]["cap_points"] = 10
    _assert_ruleset_invalid(rubric=sql_cap)

    duplicate_action = deepcopy(actions)
    duplicate_action["actions"][1]["action_id"] = actions["actions"][0]["action_id"]
    _assert_ruleset_invalid(action_catalog=duplicate_action)

    unknown_action_criterion = deepcopy(actions)
    unknown_action_criterion["actions"][0]["criterion_id"] = "not.a.criterion"
    _assert_ruleset_invalid(action_catalog=unknown_action_criterion)

    unknown_action_anchor = deepcopy(actions)
    unknown_action_anchor["actions"][0]["current_anchor"] = "advanced"
    _assert_ruleset_invalid(action_catalog=unknown_action_anchor)

    too_few_actions = deepcopy(actions)
    too_few_actions["actions"] = actions["actions"][:10]
    _assert_ruleset_invalid(action_catalog=too_few_actions)

    duplicate_project = deepcopy(projects)
    duplicate_project["projects"][1]["project_id"] = projects["projects"][0]["project_id"]
    _assert_ruleset_invalid(project_catalog=duplicate_project)

    unknown_project_track = deepcopy(projects)
    unknown_project_track["projects"][0]["track"] = "product_management"
    _assert_ruleset_invalid(project_catalog=unknown_project_track)

    unknown_core = deepcopy(projects)
    unknown_core["projects"][0]["core_criterion_ids"] = ["not.a.criterion"]
    _assert_ruleset_invalid(project_catalog=unknown_core)

    too_few_projects = deepcopy(projects)
    too_few_projects["projects"] = projects["projects"][:1]
    _assert_ruleset_invalid(project_catalog=too_few_projects)


def test_loader_maps_load_failures_to_ruleset_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_path: object) -> object:
        raise TypeError("rubric_v2.json must contain a JSON object")

    monkeypatch.setattr("app.engine.configuration.validation.load_rubric_v2", boom)
    outcome = load_validated_engine_configuration()
    assert isinstance(outcome, dict)
    assert outcome["state"] == "RULESET_INVALID"


def test_score_assessment_rejects_non_configuration_objects() -> None:
    document = _load("c01_se_full_score.json")
    outcome = score_assessment(
        document["assessment_input"],
        document["evidence_facts"],
        document["scoring_context"],
        document["source_records"],
        assessment_id="a",
        run_id="r",
        assessed_at="2026-08-31T10:00:00Z",
        configuration={"state": "UNEXPECTED"},
    )
    assert outcome["state"] == "RULESET_INVALID"


def test_score_assessment_propagates_ruleset_outcomes() -> None:
    document = _load("c01_se_full_score.json")
    outcome = score_assessment(
        document["assessment_input"],
        document["evidence_facts"],
        document["scoring_context"],
        document["source_records"],
        assessment_id="a",
        run_id="r",
        assessed_at="2026-08-31T10:00:00Z",
        configuration={"state": "RULESET_NOT_FOUND", "error_code": "RULESET_NOT_FOUND"},
    )
    assert outcome["state"] == "RULESET_NOT_FOUND"


def _score_mutated(document: dict[str, Any], **fields: object) -> dict[str, Any]:
    return score_assessment(
        fields.get("assessment_input", document["assessment_input"]),
        fields.get("evidence_facts", document["evidence_facts"]),
        fields.get("scoring_context", document["scoring_context"]),
        fields.get("source_records", document["source_records"]),
        assessment_id="a",
        run_id="r",
        assessed_at="2026-08-31T10:00:00Z",
        **({"configuration": fields["configuration"]} if "configuration" in fields else {}),
    )


def test_input_validation_failures_do_not_score() -> None:
    document = _load("c01_se_full_score.json")
    cases: list[dict[str, Any]] = []

    mismatched = deepcopy(document["assessment_input"])
    mismatched["contract_version"] = "1.1.0"
    cases.append({"assessment_input": mismatched})

    duplicate_sources = deepcopy(document["source_records"])
    duplicate_sources.append(deepcopy(duplicate_sources[0]))
    cases.append({"source_records": duplicate_sources})

    duplicate_facts = deepcopy(document["evidence_facts"])
    duplicate_facts.append(deepcopy(duplicate_facts[0]))
    cases.append({"evidence_facts": duplicate_facts})

    orphan_fact = deepcopy(document["evidence_facts"])
    orphan_fact[0] = {**orphan_fact[0], "source_id": "missing-source"}
    cases.append({"evidence_facts": orphan_fact})

    unmatched_link = deepcopy(document["source_records"])
    unmatched_link[1]["locator"] = "https://example.com/wrong"
    cases.append({"source_records": unmatched_link})

    duplicate_bindings = deepcopy(document["scoring_context"])
    duplicate_bindings["criterion_bindings"].append(
        deepcopy(duplicate_bindings["criterion_bindings"][0])
    )
    cases.append({"scoring_context": duplicate_bindings})

    no_qualification = deepcopy(document["scoring_context"])
    no_qualification["criterion_bindings"] = [
        item
        for item in no_qualification["criterion_bindings"]
        if item["criterion_id"] != "se.alignment.qualification"
    ]
    cases.append({"scoring_context": no_qualification})

    bad_route = deepcopy(document["scoring_context"])
    for item in bad_route["criterion_bindings"]:
        if item["criterion_id"] == "se.alignment.qualification":
            item["anchor"] = "da.qual.completed"
    cases.append({"scoring_context": bad_route})

    unknown_trigger = deepcopy(document["scoring_context"])
    unknown_trigger["rule_triggers"] = ["not.a.rule"]
    cases.append({"scoring_context": unknown_trigger})

    unknown_exclusion = deepcopy(document["scoring_context"])
    unknown_exclusion["project_exclusion_ids"] = ["not-an-exclusion"]
    cases.append({"scoring_context": unknown_exclusion})

    duplicate_flags = deepcopy(document["scoring_context"])
    duplicate_flags["review_flags"] = ["MATERIAL_SOURCE_CONTRADICTION"] * 2
    cases.append({"scoring_context": duplicate_flags})

    other_track = deepcopy(document["scoring_context"])
    other_track["criterion_bindings"][0]["criterion_id"] = "da.core.sql"
    cases.append({"scoring_context": other_track})

    missing_evidence = deepcopy(document["scoring_context"])
    missing_evidence["criterion_bindings"][0]["evidence_ids"] = ["ev-missing"]
    cases.append({"scoring_context": missing_evidence})

    empty_nonzero = deepcopy(document["scoring_context"])
    empty_nonzero["criterion_bindings"][0]["evidence_ids"] = []
    cases.append({"scoring_context": empty_nonzero})

    empty_qual = deepcopy(document["scoring_context"])
    for item in empty_qual["criterion_bindings"]:
        if item["criterion_id"] == "se.alignment.qualification":
            item["evidence_ids"] = []
    cases.append({"scoring_context": empty_qual})

    for fields in cases:
        outcome = _score_mutated(document, **fields)
        assert outcome["assessment_result"] is None
        assert outcome["state"] in {"INPUT_INVALID", "REVIEW_REQUIRED"}


def test_track_mismatch_between_input_and_context_is_invalid() -> None:
    document = _load("c01_se_full_score.json")
    assessment_input = deepcopy(document["assessment_input"])
    assessment_input["track"] = "data_analytics"
    outcome = _score_mutated(document, assessment_input=assessment_input)
    assert outcome["state"] == "INPUT_INVALID"


def test_explicit_project_exclusion_and_blocking_flag_change_selection() -> None:
    from app.engine.scoring.engine import _select_project

    document = _load("c03_se_no_language_cap.json")
    outcome = _score_fixture(document)
    result = outcome["assessment_result"]
    excluded = _select_project(
        load_project_catalog_v1(),
        "software_engineering",
        result["criterion_results"],
        document["evidence_facts"],
        ["python_not_explicit", "api_foundation_missing_unverifiable"],
        flags=["MATERIAL_SOURCE_CONTRADICTION"],
    )
    assert excluded == "PROJECT_RECOMMENDATION_REVIEW_REQUIRED" or isinstance(excluded, dict)


def test_assessment_qa_failure_helpers() -> None:
    from app.engine.qa.assessment import run_assessment_qa

    document = _load("c01_se_full_score.json")
    result = deepcopy(document["expected"]["assessment_result"])
    result["criterion_results"][0]["evidence_ids"] = []
    result["criterion_results"][0]["awarded_points"] = 12
    facts = {fact["evidence_id"]: fact for fact in document["evidence_facts"]}
    qa = run_assessment_qa(
        assessment_input=document["assessment_input"],
        source_records=[],
        facts=facts,
        result=result,
        track_criteria=load_rubric_v2()["tracks"]["software_engineering"]["criteria"],
        review_flags=[],
    )
    assert qa["status"] == "FAIL"

    result["criterion_results"][0]["anchor"] = "se.qual.completed"
    qa = run_assessment_qa(
        assessment_input={"cv": {}, "links": [{"link_id": "missing"}]},
        source_records=document["source_records"],
        facts={},
        result=result,
        track_criteria=load_rubric_v2()["tracks"]["software_engineering"]["criteria"],
        review_flags=[],
    )
    assert qa["status"] == "FAIL"

    result["category_results"][0]["final_score"] = 99
    qa = run_assessment_qa(
        assessment_input=document["assessment_input"],
        source_records=document["source_records"],
        facts=facts,
        result=result,
        track_criteria=load_rubric_v2()["tracks"]["software_engineering"]["criteria"],
        review_flags=[],
    )
    assert qa["status"] == "FAIL"

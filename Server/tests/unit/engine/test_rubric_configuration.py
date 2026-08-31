"""Configuration-validation tests for Rubric V2 JSON."""

import hashlib
import json
from collections.abc import Iterator, Mapping
from typing import Any

import pytest

from app.engine.configuration import (
    RUBRIC_V2_PATH,
    load_json,
    load_rubric_v2,
)

APPROVED_RUBRIC_V2_SHA256 = "90dd930ce9f0dfc7f25302bf29291d30654a452028cf919faf50d4c6eb24b844"

SCHEMA_DIR = RUBRIC_V2_PATH.parents[2] / "schemas"
JSON_DOCUMENTS = (
    RUBRIC_V2_PATH,
    SCHEMA_DIR / "assessment_input.schema.json",
    SCHEMA_DIR / "evidence_fact.schema.json",
    SCHEMA_DIR / "assessment_result.schema.json",
)
APPROVED_TRACKS = ("software_engineering", "data_analytics")
EVIDENCE_ORDER = ("named_only", "documented", "demonstrated")
POINT_KEYS = {
    "awarded_points",
    "cap_points",
    "category_maximum",
    "criterion_maximum",
    "max",
    "max_points",
    "min",
    "points",
}


def _walk(node: object) -> Iterator[object]:
    yield node
    if isinstance(node, Mapping):
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def _track(rubric: Mapping[str, Any], track_id: str) -> Mapping[str, Any]:
    return rubric["tracks"][track_id]


def _criteria(rubric: Mapping[str, Any], track_id: str) -> list[Mapping[str, Any]]:
    return list(_track(rubric, track_id)["criteria"])


def _categories(rubric: Mapping[str, Any], track_id: str) -> list[Mapping[str, Any]]:
    return list(_track(rubric, track_id)["categories"])


def _is_whole_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


@pytest.fixture(scope="module")
def rubric() -> dict[str, Any]:
    return load_rubric_v2()


def test_all_package_a_json_files_parse() -> None:
    for path in JSON_DOCUMENTS:
        document = load_json(path)
        assert isinstance(document, dict), path.name


def test_approved_tracks_exist(rubric: Mapping[str, Any]) -> None:
    assert list(rubric["supported_tracks"]) == list(APPROVED_TRACKS)
    assert set(rubric["tracks"]) == set(APPROVED_TRACKS)


def test_software_engineering_has_exactly_26_criteria(rubric: Mapping[str, Any]) -> None:
    assert len(_criteria(rubric, "software_engineering")) == 26


def test_data_analytics_has_exactly_26_criteria(rubric: Mapping[str, Any]) -> None:
    assert len(_criteria(rubric, "data_analytics")) == 26


def test_software_engineering_category_maxima_total_100(rubric: Mapping[str, Any]) -> None:
    total = sum(category["max_points"] for category in _categories(rubric, "software_engineering"))
    assert total == 100


def test_data_analytics_category_maxima_total_100(rubric: Mapping[str, Any]) -> None:
    total = sum(category["max_points"] for category in _categories(rubric, "data_analytics"))
    assert total == 100


def test_software_engineering_criterion_maxima_total_100(rubric: Mapping[str, Any]) -> None:
    total = sum(criterion["max_points"] for criterion in _criteria(rubric, "software_engineering"))
    assert total == 100


def test_data_analytics_criterion_maxima_total_100(rubric: Mapping[str, Any]) -> None:
    total = sum(criterion["max_points"] for criterion in _criteria(rubric, "data_analytics"))
    assert total == 100


@pytest.mark.parametrize("track_id", APPROVED_TRACKS)
def test_category_criterion_maxima_match_category_maximum(
    rubric: Mapping[str, Any],
    track_id: str,
) -> None:
    criteria_by_category: dict[str, int] = {}
    for criterion in _criteria(rubric, track_id):
        category_id = criterion["category_id"]
        criteria_by_category[category_id] = (
            criteria_by_category.get(category_id, 0) + criterion["max_points"]
        )
    for category in _categories(rubric, track_id):
        assert criteria_by_category[category["id"]] == category["max_points"]


def test_all_point_values_are_whole_integers(rubric: Mapping[str, Any]) -> None:
    for node in _walk(rubric):
        if not isinstance(node, Mapping):
            continue
        for key in POINT_KEYS:
            if key in node:
                assert _is_whole_int(node[key]), key
        anchors = node.get("evidence_anchors")
        if isinstance(anchors, Mapping):
            for label, points in anchors.items():
                assert _is_whole_int(points), label


def test_no_criterion_anchor_exceeds_criterion_maximum(rubric: Mapping[str, Any]) -> None:
    for track_id in APPROVED_TRACKS:
        for criterion in _criteria(rubric, track_id):
            anchors = criterion.get("evidence_anchors", {})
            for points in anchors.values():
                assert points <= criterion["max_points"]
            if criterion["scoring"] == "qualification_routes":
                routes = _track(rubric, track_id)["qualification_routes"]
                for route in routes:
                    assert route["points"] <= criterion["max_points"]


def test_evidence_anchors_are_non_decreasing(rubric: Mapping[str, Any]) -> None:
    for track_id in APPROVED_TRACKS:
        for criterion in _criteria(rubric, track_id):
            if criterion["scoring"] != "evidence_anchors":
                continue
            anchors = criterion["evidence_anchors"]
            previous = anchors[EVIDENCE_ORDER[0]]
            for level in EVIDENCE_ORDER[1:]:
                current = anchors[level]
                assert current >= previous
                previous = current


def test_highest_software_engineering_qualification_route_is_10(
    rubric: Mapping[str, Any],
) -> None:
    routes = _track(rubric, "software_engineering")["qualification_routes"]
    assert max(route["points"] for route in routes) == 10


def test_highest_data_analytics_qualification_route_is_7(rubric: Mapping[str, Any]) -> None:
    routes = _track(rubric, "data_analytics")["qualification_routes"]
    assert max(route["points"] for route in routes) == 7


def test_software_engineering_no_language_overall_cap_is_59(rubric: Mapping[str, Any]) -> None:
    caps = _track(rubric, "software_engineering")["overall_caps"]
    cap = next(item for item in caps if item["rule_id"] == "rubric.v2.se.cap.no_language")
    assert cap["cap_points"] == 59


def test_software_engineering_cv_only_project_cap_is_8_of_15(rubric: Mapping[str, Any]) -> None:
    caps = _track(rubric, "software_engineering")["category_caps"]
    cap = next(item for item in caps if item["rule_id"] == "rubric.v2.se.cap.cv_only_projects")
    assert cap["category_id"] == "se.projects"
    assert cap["cap_points"] == 8
    assert cap["category_maximum"] == 15


def test_data_analytics_no_sql_overall_cap_is_79(rubric: Mapping[str, Any]) -> None:
    caps = _track(rubric, "data_analytics")["overall_caps"]
    cap = next(item for item in caps if item["rule_id"] == "rubric.v2.da.cap.no_sql")
    assert cap["cap_points"] == 79


def test_data_analytics_cv_only_project_cap_is_6_of_10(rubric: Mapping[str, Any]) -> None:
    caps = _track(rubric, "data_analytics")["category_caps"]
    cap = next(item for item in caps if item["rule_id"] == "rubric.v2.da.cap.cv_only_projects")
    assert cap["category_id"] == "da.projects"
    assert cap["cap_points"] == 6
    assert cap["category_maximum"] == 10


def test_data_analytics_google_sheets_ceiling_is_5_of_8(rubric: Mapping[str, Any]) -> None:
    caps = _track(rubric, "data_analytics")["criterion_caps"]
    cap = next(item for item in caps if item["rule_id"] == "rubric.v2.da.cap.google_sheets_ceiling")
    assert cap["criterion_id"] == "da.core.spreadsheets"
    assert cap["cap_points"] == 5
    assert cap["criterion_maximum"] == 8


def test_power_bi_alignment_awards_one_point_for_non_missing_levels(
    rubric: Mapping[str, Any],
) -> None:
    criterion = next(
        item
        for item in _criteria(rubric, "data_analytics")
        if item["id"] == "da.tools.power_bi_alignment"
    )
    anchors = criterion["evidence_anchors"]
    assert criterion["max_points"] == 1
    assert anchors["demonstrated"] == 1
    assert anchors["documented"] == 1
    assert anchors["named_only"] == 1
    assert anchors["missing_unverifiable"] == 0


def test_score_bands_cover_every_integer_from_0_through_100_once(
    rubric: Mapping[str, Any],
) -> None:
    covered = [False] * 101
    for band in rubric["score_bands"]:
        for score in range(band["min"], band["max"] + 1):
            assert covered[score] is False
            covered[score] = True
    assert all(covered)


def test_score_band_boundaries_match_contract(rubric: Mapping[str, Any]) -> None:
    by_id = {band["id"]: band for band in rubric["score_bands"]}
    assert by_id["limited_application_evidence"]["min"] == 0
    assert by_id["limited_application_evidence"]["max"] == 39
    assert by_id["foundation_visible"]["min"] == 40
    assert by_id["foundation_visible"]["max"] == 59
    assert by_id["developing_application_readiness"]["min"] == 60
    assert by_id["developing_application_readiness"]["max"] == 79
    assert by_id["strong_application_evidence"]["min"] == 80
    assert by_id["strong_application_evidence"]["max"] == 100


def test_category_ids_are_unique(rubric: Mapping[str, Any]) -> None:
    ids = [
        category["id"] for track_id in APPROVED_TRACKS for category in _categories(rubric, track_id)
    ]
    assert len(ids) == len(set(ids))


def test_criterion_ids_are_unique(rubric: Mapping[str, Any]) -> None:
    ids = [
        criterion["id"] for track_id in APPROVED_TRACKS for criterion in _criteria(rubric, track_id)
    ]
    assert len(ids) == len(set(ids))


def test_rule_ids_are_unique(rubric: Mapping[str, Any]) -> None:
    ids = [
        node["rule_id"]
        for node in _walk(rubric)
        if isinstance(node, Mapping) and isinstance(node.get("rule_id"), str)
    ]
    assert ids
    assert len(ids) == len(set(ids))


def test_qualification_route_ids_are_unique(rubric: Mapping[str, Any]) -> None:
    ids = [
        route["id"]
        for track_id in APPROVED_TRACKS
        for route in _track(rubric, track_id)["qualification_routes"]
    ]
    assert len(ids) == len(set(ids))


def test_every_criterion_references_an_existing_category(rubric: Mapping[str, Any]) -> None:
    for track_id in APPROVED_TRACKS:
        category_ids = {category["id"] for category in _categories(rubric, track_id)}
        for criterion in _criteria(rubric, track_id):
            assert criterion["category_id"] in category_ids


def test_every_cap_references_existing_track_category_or_criterion(
    rubric: Mapping[str, Any],
) -> None:
    for track_id in APPROVED_TRACKS:
        track = _track(rubric, track_id)
        category_ids = {category["id"] for category in track["categories"]}
        criterion_ids = {criterion["id"] for criterion in track["criteria"]}
        for cap in track["category_caps"]:
            assert cap["track"] == track_id
            assert cap["category_id"] in category_ids
        for cap in track["overall_caps"]:
            assert cap["track"] == track_id
            assert cap["related_criterion_id"] in criterion_ids
        for cap in track["criterion_caps"]:
            assert cap["track"] == track_id
            assert cap["criterion_id"] in criterion_ids
        for rule in track["special_rules"]:
            assert rule["track"] == track_id
            if "criterion_id" in rule:
                assert rule["criterion_id"] in criterion_ids


def test_load_rubric_v2_rejects_non_object(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.engine.configuration.load_json", lambda path: ["not-an-object"])
    with pytest.raises(TypeError, match="JSON object"):
        load_rubric_v2()


def _canonical_sha256(document: Mapping[str, Any]) -> str:
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_approved_rubric_v2_canonical_hash_is_locked(rubric: Mapping[str, Any]) -> None:
    assert _canonical_sha256(rubric) == APPROVED_RUBRIC_V2_SHA256

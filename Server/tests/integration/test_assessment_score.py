"""HTTP tests for POST /api/v1/assessments/score."""

from __future__ import annotations

import json
from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from app.core.config import get_settings
from app.engine.configuration import load_json
from app.engine.outcomes import engine_outcome
from app.engine.scoring import score_assessment
from app.main import create_app

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "golden_candidates"
RESULT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "app" / "schemas" / "assessment_result.schema.json"
)
SCORE_PATH = "/api/v1/assessments/score"


@pytest.fixture
def client() -> Iterator[TestClient]:
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def _load(filename: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / filename).read_text(encoding="utf-8"))


def _completed_request(document: dict[str, Any]) -> dict[str, Any]:
    result = document["expected"]["assessment_result"]
    return {
        "assessment_id": result["assessment_id"],
        "run_id": result["run_id"],
        "assessed_at": result["assessed_at"],
        "assessment_input": document["assessment_input"],
        "evidence_facts": document["evidence_facts"],
        "scoring_context": document["scoring_context"],
        "source_records": document["source_records"],
    }


def test_completed_golden_fixture_returns_http_200_and_exact_engine_outcome(
    client: TestClient,
) -> None:
    document = _load("c01_se_full_score.json")
    payload = _completed_request(document)
    expected = score_assessment(
        payload["assessment_input"],
        payload["evidence_facts"],
        payload["scoring_context"],
        payload["source_records"],
        assessment_id=payload["assessment_id"],
        run_id=payload["run_id"],
        assessed_at=payload["assessed_at"],
    )
    response = client.post(SCORE_PATH, json=payload)
    assert response.status_code == 200
    assert response.json() == expected
    assert response.json()["state"] == "COMPLETED"
    Draft202012Validator(
        load_json(RESULT_SCHEMA_PATH),
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    ).validate(response.json()["assessment_result"])


def test_c15_returns_http_200_review_required_without_a_score(client: TestClient) -> None:
    document = _load("c15_conflicting_sources_review.json")
    payload = {
        "assessment_id": "assessment-golden-c15",
        "run_id": "run-golden-c15",
        "assessed_at": "2026-08-31T10:00:00Z",
        "assessment_input": document["assessment_input"],
        "evidence_facts": document["evidence_facts"],
        "scoring_context": document["scoring_context"],
        "source_records": document["source_records"],
    }
    response = client.post(SCORE_PATH, json=payload)
    body = response.json()
    assert response.status_code == 200
    assert body["state"] == "REVIEW_REQUIRED"
    assert body["assessment_result"] is None
    assert body["raw_score_present"] is False
    assert body["final_score_present"] is False
    assert "detail" not in body


def test_invalid_top_level_request_returns_fastapi_422_without_service(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = {"count": 0}

    def fail_if_called(_payload: object) -> object:
        called["count"] += 1
        raise AssertionError("service must not be invoked")

    monkeypatch.setattr("app.api.v1.assessments.score_frozen_assessment", fail_if_called)
    extra = {
        "assessment_id": "assessment-id",
        "run_id": "run-id",
        "assessed_at": "2026-08-31T10:00:00Z",
        "assessment_input": {},
        "evidence_facts": [],
        "scoring_context": {},
        "source_records": [],
        "rubric": {"unexpected": True},
    }
    response = client.post(SCORE_PATH, json=extra)
    assert response.status_code == 422
    assert "detail" in response.json()
    assert called["count"] == 0

    invalid_time = {
        "assessment_id": "assessment-id",
        "run_id": "run-id",
        "assessed_at": "not-an-rfc3339-datetime",
        "assessment_input": {},
        "evidence_facts": [],
        "scoring_context": {},
        "source_records": [],
    }
    response = client.post(SCORE_PATH, json=invalid_time)
    assert response.status_code == 422
    assert "detail" in response.json()
    assert called["count"] == 0


@pytest.mark.parametrize(
    ("state", "status"),
    [
        ("INPUT_INVALID", 422),
        ("TRACK_INVALID", 422),
        ("RULESET_NOT_FOUND", 503),
        ("RULESET_INVALID", 503),
        ("QA_FAILED", 500),
        ("FAILED", 500),
    ],
)
def test_engine_states_map_to_http_status_with_canonical_body(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    state: str,
    status: int,
) -> None:
    outcome = engine_outcome(state, error_code=state)
    monkeypatch.setattr(
        "app.api.v1.assessments.score_frozen_assessment",
        lambda _payload: outcome,
    )
    response = client.post(
        SCORE_PATH,
        json={
            "assessment_id": "assessment-id",
            "run_id": "run-id",
            "assessed_at": "2026-08-31T10:00:00Z",
            "assessment_input": {},
            "evidence_facts": [],
            "scoring_context": {},
            "source_records": [],
        },
    )
    assert response.status_code == status
    assert response.json() == outcome
    assert "detail" not in response.json()
    assert "traceback" not in response.text.lower()


def test_input_invalid_from_engine_uses_canonical_body(client: TestClient) -> None:
    document = _load("c01_se_full_score.json")
    payload = _completed_request(document)
    payload["assessment_input"] = deepcopy(payload["assessment_input"])
    payload["assessment_input"]["track"] = "product_management"
    response = client.post(SCORE_PATH, json=payload)
    body = response.json()
    assert response.status_code == 422
    assert body["state"] == "INPUT_INVALID"
    assert body["assessment_result"] is None
    assert "detail" not in body


def test_repeated_identical_requests_are_deterministic(client: TestClient) -> None:
    payload = _completed_request(_load("c01_se_full_score.json"))
    first = client.post(SCORE_PATH, json=payload)
    second = client.post(SCORE_PATH, json=payload)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()


def test_unexpected_service_failure_returns_failed_without_leaking(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(_payload: object) -> object:
        raise RuntimeError("C:\\secret\\path traceback must not leak")

    monkeypatch.setattr("app.api.v1.assessments.score_frozen_assessment", boom)
    response = client.post(
        SCORE_PATH,
        json={
            "assessment_id": "assessment-id",
            "run_id": "run-id",
            "assessed_at": "2026-08-31T10:00:00Z",
            "assessment_input": {},
            "evidence_facts": [],
            "scoring_context": {},
            "source_records": [],
        },
    )
    body = response.json()
    assert response.status_code == 500
    assert body == engine_outcome("FAILED", error_code="FAILED")
    assert "C:\\secret\\path" not in response.text
    assert "RuntimeError" not in response.text


def test_non_string_engine_state_maps_to_http_500(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.v1.assessments.score_frozen_assessment",
        lambda _payload: {"state": None},
    )
    response = client.post(
        SCORE_PATH,
        json={
            "assessment_id": "assessment-id",
            "run_id": "run-id",
            "assessed_at": "2026-08-31T10:00:00Z",
            "assessment_input": {},
            "evidence_facts": [],
            "scoring_context": {},
            "source_records": [],
        },
    )
    assert response.status_code == 500
    assert "traceback" not in response.text.lower()


def test_openapi_documents_the_score_endpoint(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    path = spec["paths"][SCORE_PATH]["post"]
    assert path["summary"] == "Score a frozen assessment run"
    assert "200" in path["responses"]
    assert "422" in path["responses"]
    assert "500" in path["responses"]
    assert "503" in path["responses"]
    schema = path["requestBody"]["content"]["application/json"]["schema"]
    if "$ref" in schema:
        schema = spec["components"]["schemas"][schema["$ref"].rsplit("/", 1)[-1]]
    properties = schema.get("properties", {})
    assert set(properties) == {
        "assessment_id",
        "run_id",
        "assessed_at",
        "assessment_input",
        "evidence_facts",
        "scoring_context",
        "source_records",
    }
    assert schema.get("additionalProperties") is False

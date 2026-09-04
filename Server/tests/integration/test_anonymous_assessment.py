"""HTTP tests for POST /api/v1/assessments. Fakes only; no Supabase or Postgres."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.engine.schema_registry import draft_validator
from app.main import create_app
from app.repositories.supabase import MAX_FILE_SIZE_BYTES
from app.services.anonymous_assessment import (
    ERROR_ASSESSMENT_SERVICE_UNAVAILABLE,
    ERROR_FILE_TOO_LARGE,
    ERROR_INVALID_SUBMISSION,
    ERROR_TOO_MANY_LINKS,
    ERROR_UNSUPPORTED_MEDIA_TYPE,
)
from tests.integration.test_assessment_score import SCORE_PATH, _completed_request, _load
from tests.unit.services.test_anonymous_assessment import (
    IDENTITY,
    RAW_CLAIM,
    FakeStorage,
    RecordingRepository,
    _paid_keys,
    da_docx,
    se_pdf,
)
from tests.unit.services.test_assessment_pipeline import ASSESSED_AT, _blocked_retrieve

ANON_PATH = "/api/v1/assessments"
MEDIA_PDF = "application/pdf"
MEDIA_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.fixture
def app_client() -> Iterator[tuple[TestClient, Any]]:
    get_settings.cache_clear()
    application = create_app()
    with TestClient(application) as client:
        application.state.auto_bind_resources = False
        yield client, application
    get_settings.cache_clear()


def _bind(
    application: Any,
    *,
    repository: RecordingRepository | None = None,
    storage: FakeStorage | None = None,
    **overrides: Any,
) -> tuple[RecordingRepository, FakeStorage]:
    repo = repository if repository is not None else RecordingRepository()
    store = storage if storage is not None else FakeStorage()
    application.state.repository = repo
    application.state.storage = store
    application.state.identity_factory = lambda: IDENTITY
    application.state.claim_token_factory = lambda: RAW_CLAIM
    application.state.assessed_at = ASSESSED_AT
    application.state.retrieve_link = _blocked_retrieve
    for name, value in overrides.items():
        setattr(application.state, name, value)
    return repo, store


def _post(
    client: TestClient,
    *,
    track: str = "software_engineering",
    filename: str = "cv.pdf",
    file_bytes: bytes | None = None,
    media_type: str = MEDIA_PDF,
    links: object | None = None,
    extra_data: dict[str, str] | None = None,
) -> Any:
    data: dict[str, str] = {"track": track}
    if links is not None:
        data["links"] = links if isinstance(links, str) else json.dumps(links)
    if extra_data:
        data.update(extra_data)
    payload = se_pdf() if file_bytes is None else file_bytes
    return client.post(
        ANON_PATH,
        data=data,
        files={"cv": (filename, payload, media_type)},
    )


def test_completed_se_pdf_returns_http_201_and_preview(
    app_client: tuple[TestClient, Any],
) -> None:
    client, application = app_client
    _bind(application)
    response = _post(client)
    assert response.status_code == 201
    payload = response.json()
    draft_validator("anonymous_assessment_response.schema.json").validate(payload)
    draft_validator("readiness_preview.schema.json").validate(payload["preview"])
    assert payload["state"] == "COMPLETED"
    assert payload["claim_token"] == RAW_CLAIM
    assert payload["preview"]["schema_version"] == "readiness.preview.v1"
    assert _paid_keys(payload) == set()


def test_completed_da_docx_returns_http_201(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _bind(application)
    response = _post(
        client,
        track="data_analytics",
        filename="cv.docx",
        file_bytes=da_docx(),
        media_type=MEDIA_DOCX,
    )
    assert response.status_code == 201
    assert response.json()["preview"]["track"] == "data_analytics"


def test_client_injected_ids_and_score_fields_are_ignored(
    app_client: tuple[TestClient, Any],
) -> None:
    client, application = app_client
    repo, _storage = _bind(application)
    response = _post(
        client,
        extra_data={
            "assessment_id": "client-assessment",
            "run_id": "client-run",
            "document_id": "client-doc",
            "candidate_ref": "client-candidate",
            "contract_version": "9.9.9",
            "rubric_version": "V1",
            "score": "99",
            "evidence_facts": "[]",
            "scoring_context": "{}",
            "source_records": "[]",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["assessment_id"] == IDENTITY.assessment_id
    assert payload["run_id"] == IDENTITY.run_id
    assert repo.bundles[0].assessment_input["candidate_ref"] == IDENTITY.candidate_ref
    assert repo.bundles[0].assessment_input["contract_version"] == "1.2.0"


def test_malformed_links_json_returns_422(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    repo, storage = _bind(application)
    response = _post(client, links="{not-json")
    assert response.status_code == 422
    payload = response.json()
    assert payload["error_code"] == ERROR_INVALID_SUBMISSION
    assert payload["schema_version"] == "anonymous.assessment.v1"
    assert "detail" not in payload
    assert repo.bundles == []
    assert storage.puts == []


def test_too_many_links_returns_422_before_storage(
    app_client: tuple[TestClient, Any],
) -> None:
    client, application = app_client
    repo, storage = _bind(application)
    links = [
        {"submitted_url": f"https://example.com/{index}", "declared_type": "project"}
        for index in range(6)
    ]
    response = _post(client, links=links)
    assert response.status_code == 422
    assert response.json()["error_code"] == ERROR_TOO_MANY_LINKS
    assert storage.puts == []
    assert repo.bundles == []


def test_unsupported_media_type_returns_422(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _bind(application)
    response = _post(client, filename="cv.txt", media_type="text/plain", file_bytes=b"hello")
    assert response.status_code == 422
    assert response.json()["error_code"] == ERROR_UNSUPPORTED_MEDIA_TYPE


def test_file_too_large_returns_422(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    repo, storage = _bind(application)
    response = _post(client, file_bytes=b"a" * (MAX_FILE_SIZE_BYTES + 1))
    assert response.status_code == 422
    assert response.json()["error_code"] == ERROR_FILE_TOO_LARGE
    assert storage.puts == []
    assert repo.bundles == []


def test_review_required_returns_202_without_preview(
    app_client: tuple[TestClient, Any],
) -> None:
    from tests.unit.services.test_assessment_pipeline import _accessible_retrieve

    client, application = app_client
    _bind(application, retrieve_link=_accessible_retrieve)
    response = _post(
        client,
        links=[{"submitted_url": "https://example.com/project", "declared_type": "project"}],
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["state"] == "REVIEW_REQUIRED"
    assert payload["preview"] is None
    assert payload["claim_token"] == RAW_CLAIM


def test_not_scorable_returns_422_without_preview(
    app_client: tuple[TestClient, Any],
) -> None:
    client, application = app_client
    _bind(application)
    response = _post(client, file_bytes=b"%PDF-1.4 broken")
    assert response.status_code == 422
    payload = response.json()
    assert payload["state"] == "NOT_SCORABLE"
    assert payload["preview"] is None
    assert payload["error_code"] == "CV_UNREADABLE"


def test_unconfigured_endpoint_returns_503(app_client: tuple[TestClient, Any]) -> None:
    client, _application = app_client
    response = _post(client)
    assert response.status_code == 503
    payload = response.json()
    assert payload["error_code"] == ERROR_ASSESSMENT_SERVICE_UNAVAILABLE
    assert payload["claim_token"] is None
    assert payload["preview"] is None
    draft_validator("anonymous_assessment_response.schema.json").validate(payload)


def test_missing_cv_returns_schema_422(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _bind(application)
    response = client.post(ANON_PATH, data={"track": "software_engineering"})
    assert response.status_code == 422
    payload = response.json()
    assert payload["error_code"] == ERROR_INVALID_SUBMISSION
    assert "detail" not in payload


def test_score_route_remains_unchanged(app_client: tuple[TestClient, Any]) -> None:
    client, _application = app_client
    document = _load("c01_se_full_score.json")
    response = client.post(SCORE_PATH, json=_completed_request(document))
    assert response.status_code == 200
    assert response.json()["state"] == "COMPLETED"
    assert "assessment_result" in response.json()


def test_non_list_links_json_returns_422(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    repo, storage = _bind(application)
    response = _post(client, links="{}")
    assert response.status_code == 422
    assert response.json()["error_code"] == ERROR_INVALID_SUBMISSION
    assert storage.puts == []
    assert repo.bundles == []


def test_orchestration_exception_returns_503(app_client: tuple[TestClient, Any]) -> None:
    client, application = app_client
    _bind(application)

    async def boom(**_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("orchestration exploded")

    import app.api.v1.assessments as assessments_api

    original = assessments_api.submit_anonymous_assessment
    assessments_api.submit_anonymous_assessment = boom  # type: ignore[assignment]
    try:
        response = _post(client)
    finally:
        assessments_api.submit_anonymous_assessment = original
    assert response.status_code == 503
    assert response.json()["error_code"] == ERROR_ASSESSMENT_SERVICE_UNAVAILABLE


def test_reports_id_is_not_exposed(app_client: tuple[TestClient, Any]) -> None:
    client, _application = app_client
    response = client.get("/api/v1/reports/assessment-1")
    assert response.status_code == 404

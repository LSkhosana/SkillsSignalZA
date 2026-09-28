"""Package FL-4 owned-summary orchestration tests. No database or live Auth."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from app.engine.schema_registry import draft_validator
from app.repositories.records import (
    AssessmentRecord,
    AssessmentRunRecord,
    PaymentRecord,
)
from app.services.assessment_summaries import (
    ERROR_AUTH_INVALID,
    ERROR_SUMMARIES_SERVICE_UNAVAILABLE,
    SCHEMA_VERSION,
    list_owned_assessment_summaries,
    summaries_failed_outcome,
    summaries_http_status,
    summaries_service_unavailable,
)
from tests.unit.services.test_anonymous_assessment import IDENTITY, RecordingRepository

OLDER = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
NEWER = datetime(2026, 9, 5, 10, 0, tzinfo=UTC)
PAID_AT = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)
USER_A = "user-verified-a"
USER_B = "user-verified-b"
FORBIDDEN = {
    "owner_user_id",
    "claim_token",
    "claim_token_hash",
    "category_breakdown",
    "strengths",
    "material_gaps",
    "priority_actions",
    "project_recommendation",
    "criterion_breakdown",
    "cap_detail",
    "explicit_text",
    "evidence_facts",
    "source_records",
    "scoring_context",
    "storage_path",
    "assessment_result",
    "email",
    "access_token",
    "preview",
    "authorization_url",
    "provider_reference",
    "paid_payload",
}


def _run(
    assessment_id: str,
    run_id: str,
    *,
    assessed_at: datetime,
    state: str = "COMPLETED",
    result: dict | None = None,
) -> AssessmentRunRecord:
    return AssessmentRunRecord(
        run_id=run_id,
        assessment_id=assessment_id,
        state=state,
        error_code=None,
        pipeline_version="assessment.pipeline.v1",
        contract_version="1.2.0",
        rubric_version="V2",
        track="software_engineering",
        assessment_input={"track": "software_engineering"},
        scoring_context=None,
        assessment_result=result,
        review_flags=[],
        stages=["score"],
        assessed_at=assessed_at,
        created_at=assessed_at,
        source_records=[],
        evidence_facts=[],
        document=None,
    )


def _seed_assessment(
    repository: RecordingRepository,
    *,
    assessment_id: str,
    owner_user_id: str | None,
    access_state: str,
    assessed_at: datetime,
    run_id: str | None = None,
    run_state: str = "COMPLETED",
    result: dict | None = None,
    track: str = "software_engineering",
) -> None:
    latest = run_id if run_id is not None else f"run-{assessment_id}"
    repository.assessments[assessment_id] = AssessmentRecord(
        assessment_id=assessment_id,
        candidate_ref=IDENTITY.candidate_ref,
        track=track,
        access_state=access_state,  # type: ignore[arg-type]
        claim_token_hash="hash-must-never-appear",
        claimed_at=assessed_at,
        latest_run_id=latest,
        expires_at=None,
        created_at=assessed_at,
        updated_at=assessed_at,
        owner_user_id=owner_user_id,
    )
    repository.runs[latest] = _run(
        assessment_id,
        latest,
        assessed_at=assessed_at,
        state=run_state,
        result=result,
    )


def _seed_payment(
    repository: RecordingRepository,
    *,
    assessment_id: str,
    owner_user_id: str,
    paid_at: datetime,
    status: str = "SUCCEEDED",
) -> None:
    payment_id = f"pay-{assessment_id}"
    repository.payments[payment_id] = PaymentRecord(
        payment_id=payment_id,
        assessment_id=assessment_id,
        owner_user_id=owner_user_id,
        product_id="readiness_report_v1",
        billing_model="one_time",
        provider="paystack",
        provider_reference=f"psk-{assessment_id}",
        provider_transaction_id="txn-secret",
        amount_minor=15900,
        currency="ZAR",
        status=status,  # type: ignore[arg-type]
        authorization_url="https://paystack.invalid/checkout",
        paid_at=paid_at,
        created_at=paid_at,
        updated_at=paid_at,
    )


def _list(repository: RecordingRepository, owner: str = USER_A, **kwargs: object) -> dict:
    return asyncio.run(
        list_owned_assessment_summaries(
            repository=repository,
            owner_user_id=owner,
            **kwargs,
        )
    )


def test_owner_receives_only_owned_summaries() -> None:
    repository = RecordingRepository()
    _seed_assessment(
        repository,
        assessment_id="owned-preview",
        owner_user_id=USER_A,
        access_state="PREVIEW",
        assessed_at=OLDER,
        result={"final_score": 59, "band": "foundation_visible"},
    )
    _seed_assessment(
        repository,
        assessment_id="owned-unlocked",
        owner_user_id=USER_A,
        access_state="UNLOCKED",
        assessed_at=NEWER,
        result={"final_score": 82, "band": "strong_application_evidence"},
    )
    _seed_payment(repository, assessment_id="owned-unlocked", owner_user_id=USER_A, paid_at=PAID_AT)
    _seed_assessment(
        repository,
        assessment_id="other-user",
        owner_user_id=USER_B,
        access_state="UNLOCKED",
        assessed_at=NEWER,
        result={"final_score": 90, "band": "strong_application_evidence"},
    )
    _seed_assessment(
        repository,
        assessment_id="unowned",
        owner_user_id=None,
        access_state="PREVIEW",
        assessed_at=NEWER,
        result={"final_score": 40, "band": "limited_application_evidence"},
    )
    outcome = _list(repository)
    draft_validator("assessment_summaries.schema.json").validate(outcome)
    assert outcome["schema_version"] == SCHEMA_VERSION
    assert outcome["state"] == "LISTED"
    assert outcome["error_code"] is None
    ids = [item["assessment_id"] for item in outcome["items"]]
    assert ids == ["owned-unlocked", "owned-preview"]
    by_id = {item["assessment_id"]: item for item in outcome["items"]}
    assert by_id["owned-preview"]["access_state"] == "PREVIEW"
    assert by_id["owned-preview"]["unlocked_at"] is None
    assert by_id["owned-preview"]["final_score"] == 59
    assert by_id["owned-unlocked"]["access_state"] == "UNLOCKED"
    assert by_id["owned-unlocked"]["unlocked_at"] == "2026-09-06T12:00:00Z"
    assert "other-user" not in ids
    assert "unowned" not in ids
    for item in outcome["items"]:
        for key in FORBIDDEN:
            assert key not in item
    for key in FORBIDDEN:
        assert key not in outcome


def test_incomplete_run_omits_score_and_band() -> None:
    repository = RecordingRepository()
    _seed_assessment(
        repository,
        assessment_id="review-required",
        owner_user_id=USER_A,
        access_state="PREVIEW",
        assessed_at=NEWER,
        run_state="REVIEW_REQUIRED",
        result={"final_score": 70, "band": "developing_application_readiness"},
    )
    outcome = _list(repository)
    draft_validator("assessment_summaries.schema.json").validate(outcome)
    assert outcome["items"][0]["final_score"] is None
    assert outcome["items"][0]["band"] is None


def test_blank_owner_is_auth_invalid() -> None:
    outcome = _list(RecordingRepository(), owner="  ")
    assert outcome["state"] == "FAILED"
    assert outcome["error_code"] == ERROR_AUTH_INVALID
    assert summaries_http_status(outcome) == 401


def test_repository_failure_is_unavailable() -> None:
    repository = RecordingRepository()
    repository.list_summaries_error = RuntimeError("forced")
    outcome = _list(repository)
    assert outcome["error_code"] == ERROR_SUMMARIES_SERVICE_UNAVAILABLE
    assert summaries_http_status(outcome) == 503
    assert summaries_service_unavailable()["error_code"] == ERROR_SUMMARIES_SERVICE_UNAVAILABLE
    failed = summaries_failed_outcome(ERROR_AUTH_INVALID)
    assert failed["items"] == []
    assert summaries_http_status({"state": "FAILED"}) == 500


def test_offset_pagination_is_explicit_and_has_more() -> None:
    repository = RecordingRepository()
    _seed_assessment(
        repository,
        assessment_id="z-newest",
        owner_user_id=USER_A,
        access_state="PREVIEW",
        assessed_at=NEWER,
        result={"final_score": 10, "band": "limited_application_evidence"},
    )
    _seed_assessment(
        repository,
        assessment_id="m-middle",
        owner_user_id=USER_A,
        access_state="PREVIEW",
        assessed_at=datetime(2026, 9, 3, 10, 0, tzinfo=UTC),
        result={"final_score": 20, "band": "foundation_visible"},
    )
    _seed_assessment(
        repository,
        assessment_id="a-oldest",
        owner_user_id=USER_A,
        access_state="PREVIEW",
        assessed_at=OLDER,
        result={"final_score": 30, "band": "foundation_visible"},
    )
    first = _list(repository, limit=2, offset=0)
    assert first["has_more"] is True
    assert first["limit"] == 2
    assert first["offset"] == 0
    assert [item["assessment_id"] for item in first["items"]] == ["z-newest", "m-middle"]
    second = _list(repository, limit=2, offset=2)
    assert second["has_more"] is False
    assert [item["assessment_id"] for item in second["items"]] == ["a-oldest"]


def test_tie_breaks_on_assessment_id_descending() -> None:
    repository = RecordingRepository()
    _seed_assessment(
        repository,
        assessment_id="assessment-a",
        owner_user_id=USER_A,
        access_state="PREVIEW",
        assessed_at=NEWER,
        result={"final_score": 1, "band": "limited_application_evidence"},
    )
    _seed_assessment(
        repository,
        assessment_id="assessment-b",
        owner_user_id=USER_A,
        access_state="PREVIEW",
        assessed_at=NEWER,
        result={"final_score": 2, "band": "limited_application_evidence"},
    )
    outcome = _list(repository)
    assert [item["assessment_id"] for item in outcome["items"]] == [
        "assessment-b",
        "assessment-a",
    ]


def test_non_integer_limit_clamps_to_default() -> None:
    repository = RecordingRepository()
    _seed_assessment(
        repository,
        assessment_id="owned-preview",
        owner_user_id=USER_A,
        access_state="PREVIEW",
        assessed_at=NEWER,
        result={"final_score": 10, "band": "limited_application_evidence"},
    )
    outcome = _list(repository, limit=True)  # type: ignore[arg-type]
    assert outcome["state"] == "LISTED"
    assert outcome["limit"] == 50


def test_invalid_band_fails_closed() -> None:
    repository = RecordingRepository()
    _seed_assessment(
        repository,
        assessment_id="owned-preview",
        owner_user_id=USER_A,
        access_state="PREVIEW",
        assessed_at=NEWER,
        result={"final_score": 10, "band": "not_a_canonical_band"},
    )
    outcome = _list(repository)
    assert outcome["state"] == "FAILED"
    assert outcome["error_code"] == ERROR_SUMMARIES_SERVICE_UNAVAILABLE
    assert outcome["items"] == []

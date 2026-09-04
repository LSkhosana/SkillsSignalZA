"""Unit tests for anonymous-assessment multipart parsing. No network."""

from __future__ import annotations

import asyncio

from app.api.v1.assessments import _read_bounded_cv
from app.repositories.supabase import MAX_FILE_SIZE_BYTES
from app.services.anonymous_assessment import ERROR_FILE_TOO_LARGE


class _RecordingUpload:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self.requested_sizes: list[int] = []

    async def read(self, size: int = -1) -> bytes:
        self.requested_sizes.append(size)
        if size < 0:
            raise AssertionError("anonymous CV reads must be bounded")
        return self._payload[:size]


def test_bounded_cv_read_requests_at_most_max_plus_one() -> None:
    upload = _RecordingUpload(b"a" * (MAX_FILE_SIZE_BYTES + 50))
    result = asyncio.run(_read_bounded_cv(upload))  # type: ignore[arg-type]
    assert upload.requested_sizes == [MAX_FILE_SIZE_BYTES + 1]
    assert result.status_code == 422
    payload = result.body
    assert ERROR_FILE_TOO_LARGE.encode("utf-8") in payload
    assert b"FILE_TOO_LARGE" in payload


def test_bounded_cv_read_accepts_exact_limit() -> None:
    payload = b"a" * MAX_FILE_SIZE_BYTES
    upload = _RecordingUpload(payload)
    result = asyncio.run(_read_bounded_cv(upload))  # type: ignore[arg-type]
    assert upload.requested_sizes == [MAX_FILE_SIZE_BYTES + 1]
    assert result == payload

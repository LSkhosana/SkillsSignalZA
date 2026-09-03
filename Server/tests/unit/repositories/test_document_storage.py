"""Private document storage adapter tests. No real network."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.repositories.supabase import (
    DocumentStorageError,
    SupabaseDocumentStorage,
    opaque_storage_path,
)

SECRET = "sb_secret_test-storage-key"
PDF = b"%PDF-1.4 test-cv"
DOCX = b"PK\x03\x04 test-docx"
OBJECT_URL_PREFIX = "https://example.supabase.co/storage/v1/object/candidate-evidence/"


class FakeResponse:
    def __init__(self, status_code: int = 200, content: bytes = b"") -> None:
        self.status_code = status_code
        self.content = content


class FakeAsyncClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, bytes | None, dict[str, str] | None]] = []
        self.post_response = FakeResponse()
        self.get_response = FakeResponse(content=PDF)
        self.delete_response = FakeResponse()

    async def post(
        self, url: str, content: bytes | None = None, headers: dict[str, str] | None = None
    ):
        self.calls.append(("POST", url, content, headers))
        return self.post_response

    async def put(
        self, url: str, content: bytes | None = None, headers: dict[str, str] | None = None
    ):
        self.calls.append(("PUT", url, content, headers))
        return FakeResponse()

    async def get(self, url: str, headers: dict[str, str] | None = None):
        self.calls.append(("GET", url, None, headers))
        return self.get_response

    async def delete(self, url: str, headers: dict[str, str] | None = None):
        self.calls.append(("DELETE", url, None, headers))
        return self.delete_response

    async def aclose(self) -> None:
        return None


def _storage(client: FakeAsyncClient) -> SupabaseDocumentStorage:
    return SupabaseDocumentStorage(
        supabase_url="https://example.supabase.co",
        secret_key=SECRET,
        bucket="candidate-evidence",
        client=client,
    )


def _assert_secret_not_leaked(*values: object) -> None:
    for value in values:
        rendered = str(value)
        assert SECRET not in rendered
        assert PDF.decode("latin-1") not in rendered
        assert DOCX.decode("latin-1") not in rendered


def _assert_private_secret_headers(
    headers: dict[str, str] | None, *, media_type: str | None = None
) -> None:
    assert headers is not None
    assert headers["apikey"] == SECRET
    assert "Authorization" not in headers
    assert not any(str(value).startswith("Bearer ") for value in headers.values())
    if media_type is None:
        assert "Content-Type" not in headers
    else:
        assert headers["Content-Type"] == media_type


def test_pdf_and_docx_uploads_use_post_and_opaque_paths() -> None:
    async def body() -> None:
        client = FakeAsyncClient()
        storage = _storage(client)
        pdf_meta = await storage.put_private_document(
            assessment_id="assessment-1",
            document_id="src-cv",
            file_bytes=PDF,
            media_type="application/pdf",
            original_filename="Jane Doe CV.pdf",
        )
        assert pdf_meta["storage_path"] == "assessments/assessment-1/src-cv.pdf"
        assert "Jane" not in pdf_meta["storage_path"]
        assert "Doe" not in pdf_meta["storage_path"]
        assert pdf_meta["byte_size"] == len(PDF)
        docx_meta = await storage.put_private_document(
            assessment_id="assessment-1",
            document_id="src-cv",
            file_bytes=DOCX,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            original_filename="resume.docx",
        )
        assert docx_meta["storage_path"].endswith(".docx")
        methods = [call[0] for call in client.calls]
        assert methods == ["POST", "POST"]
        assert "PUT" not in methods
        first = client.calls[0]
        assert first[1] == f"{OBJECT_URL_PREFIX}assessments/assessment-1/src-cv.pdf"
        assert first[2] == PDF
        _assert_private_secret_headers(first[3], media_type="application/pdf")
        second = client.calls[1]
        assert second[2] == DOCX
        _assert_private_secret_headers(
            second[3],
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        assert "get_public_url" not in dir(storage)
        assert not hasattr(storage, "public_url")

    asyncio.run(body())


def test_local_rejections_do_not_touch_the_network() -> None:
    async def body() -> None:
        client = FakeAsyncClient()
        storage = _storage(client)
        with pytest.raises(DocumentStorageError) as empty:
            await storage.put_private_document(
                assessment_id="assessment-1",
                document_id="src-cv",
                file_bytes=b"",
                media_type="application/pdf",
                original_filename="cv.pdf",
            )
        with pytest.raises(DocumentStorageError) as huge:
            await storage.put_private_document(
                assessment_id="assessment-1",
                document_id="src-cv",
                file_bytes=b"a" * (10 * 1024 * 1024 + 1),
                media_type="application/pdf",
                original_filename="cv.pdf",
            )
        with pytest.raises(DocumentStorageError) as media:
            await storage.put_private_document(
                assessment_id="assessment-1",
                document_id="src-cv",
                file_bytes=PDF,
                media_type="image/png",
                original_filename="cv.png",
            )
        assert empty.value.error_code == "EMPTY_FILE"
        assert huge.value.error_code == "FILE_TOO_LARGE"
        assert media.value.error_code == "UNSUPPORTED_MEDIA_TYPE"
        assert client.calls == []
        for exc in (empty.value, huge.value, media.value):
            _assert_secret_not_leaked(exc, exc.error_code)

    asyncio.run(body())


def test_get_and_delete_remain_private_storage_operations() -> None:
    async def body() -> None:
        client = FakeAsyncClient()
        storage = _storage(client)
        path = opaque_storage_path("assessment-1", "src-cv", "application/pdf")
        assert await storage.get_private_document(path) == PDF
        await storage.delete_private_document(path)
        methods = [call[0] for call in client.calls]
        assert methods == ["GET", "DELETE"]
        urls = [call[1] for call in client.calls]
        assert urls == [
            f"{OBJECT_URL_PREFIX}{path}",
            f"{OBJECT_URL_PREFIX}{path}",
        ]
        assert all(url.startswith(OBJECT_URL_PREFIX) for url in urls)
        assert all(SECRET not in url for url in urls)
        for call in client.calls:
            _assert_private_secret_headers(call[3])
        client.get_response = FakeResponse(status_code=500, content=PDF + SECRET.encode())
        with pytest.raises(DocumentStorageError) as failed:
            await storage.get_private_document(path)
        assert failed.value.error_code == "STORAGE_GET_FAILED"
        _assert_secret_not_leaked(failed.value, failed.value.error_code)

    asyncio.run(body())


def test_storage_http_status_errors_are_safe() -> None:
    async def body() -> None:
        client = FakeAsyncClient()
        client.post_response = FakeResponse(status_code=403, content=SECRET.encode() + PDF)
        client.delete_response = FakeResponse(status_code=500, content=PDF)
        storage = _storage(client)
        with pytest.raises(DocumentStorageError) as put_failed:
            await storage.put_private_document(
                assessment_id="assessment-1",
                document_id="src-cv",
                file_bytes=PDF,
                media_type="application/pdf",
                original_filename="resume.pdf",
            )
        with pytest.raises(DocumentStorageError) as delete_failed:
            await storage.delete_private_document("assessments/assessment-1/src-cv.pdf")
        assert put_failed.value.error_code == "STORAGE_PUT_FAILED"
        assert delete_failed.value.error_code == "STORAGE_DELETE_FAILED"
        assert client.calls[0][0] == "POST"
        _assert_secret_not_leaked(
            put_failed.value, put_failed.value.error_code, delete_failed.value
        )

    asyncio.run(body())


def test_http_errors_are_safe() -> None:
    class BoomClient(FakeAsyncClient):
        async def post(
            self, url: str, content: bytes | None = None, headers: dict[str, str] | None = None
        ):
            raise httpx.ConnectError("boom", request=httpx.Request("POST", url))

        async def delete(self, url: str, headers: dict[str, str] | None = None):
            raise httpx.ConnectError("boom", request=httpx.Request("DELETE", url))

    async def body() -> None:
        storage = _storage(BoomClient())
        with pytest.raises(DocumentStorageError) as put_failed:
            await storage.put_private_document(
                assessment_id="assessment-1",
                document_id="src-cv",
                file_bytes=PDF,
                media_type="application/pdf",
                original_filename="cv.pdf",
            )
        with pytest.raises(DocumentStorageError) as delete_failed:
            await storage.delete_private_document("assessments/assessment-1/src-cv.pdf")
        assert put_failed.value.error_code == "STORAGE_PUT_FAILED"
        assert delete_failed.value.error_code == "STORAGE_DELETE_FAILED"
        _assert_secret_not_leaked(put_failed.value, delete_failed.value)

    asyncio.run(body())


def test_opaque_ids_reject_path_separators() -> None:
    with pytest.raises(DocumentStorageError):
        opaque_storage_path("assessment/1", "src-cv", "application/pdf")

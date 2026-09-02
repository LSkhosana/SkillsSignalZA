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

SECRET = "super-secret-storage-key"
PDF = b"%PDF-1.4 test-cv"
DOCX = b"PK\x03\x04 test-docx"


class FakeResponse:
    def __init__(self, status_code: int = 200, content: bytes = b"") -> None:
        self.status_code = status_code
        self.content = content


class FakeAsyncClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, bytes | None, dict[str, str] | None]] = []
        self.put_response = FakeResponse()
        self.get_response = FakeResponse(content=PDF)
        self.delete_response = FakeResponse()

    async def put(
        self, url: str, content: bytes | None = None, headers: dict[str, str] | None = None
    ):
        self.calls.append(("PUT", url, content, headers))
        return self.put_response

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


def test_pdf_and_docx_uploads_use_opaque_paths() -> None:
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
        put_calls = [call for call in client.calls if call[0] == "PUT"]
        assert put_calls[0][2] == PDF
        headers = put_calls[0][3] or {}
        assert headers["Authorization"] == f"Bearer {SECRET}"
        assert headers["apikey"] == SECRET
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
            assert SECRET not in str(exc)

    asyncio.run(body())


def test_get_and_delete_use_private_object_urls() -> None:
    async def body() -> None:
        client = FakeAsyncClient()
        storage = _storage(client)
        path = opaque_storage_path("assessment-1", "src-cv", "application/pdf")
        assert await storage.get_private_document(path) == PDF
        await storage.delete_private_document(path)
        urls = [call[1] for call in client.calls]
        assert all(
            "example.supabase.co/storage/v1/object/candidate-evidence/" in url for url in urls
        )
        assert all(SECRET not in url for url in urls)
        client.get_response = FakeResponse(status_code=500)
        with pytest.raises(DocumentStorageError) as failed:
            await storage.get_private_document(path)
        assert SECRET not in str(failed.value)

    asyncio.run(body())


def test_storage_http_status_errors_are_safe() -> None:
    async def body() -> None:
        client = FakeAsyncClient()
        client.put_response = FakeResponse(status_code=403)
        client.delete_response = FakeResponse(status_code=500)
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

    asyncio.run(body())


def test_http_errors_are_safe() -> None:
    class BoomClient(FakeAsyncClient):
        async def put(
            self, url: str, content: bytes | None = None, headers: dict[str, str] | None = None
        ):
            raise httpx.ConnectError("boom", request=httpx.Request("PUT", url))

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

    asyncio.run(body())


def test_opaque_ids_reject_path_separators() -> None:
    with pytest.raises(DocumentStorageError):
        opaque_storage_path("assessment/1", "src-cv", "application/pdf")

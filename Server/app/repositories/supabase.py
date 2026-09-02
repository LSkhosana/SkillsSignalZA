"""Supabase Storage adapter for private CV objects.

This module is the V1 DocumentStorage implementation. It does not persist
assessment rows and does not use PostgREST.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import httpx

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
MEDIA_TYPE_PDF = "application/pdf"
MEDIA_TYPE_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
SUPPORTED_MEDIA_TYPES = frozenset({MEDIA_TYPE_PDF, MEDIA_TYPE_DOCX})
OPAQUE_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class DocumentStorageError(Exception):
    """Safe private-storage failure that never includes secrets or CV bytes."""

    def __init__(self, error_code: str) -> None:
        self.error_code = error_code
        super().__init__(error_code)


def opaque_storage_path(assessment_id: str, document_id: str, media_type: str) -> str:
    """Return an opaque object key derived only from IDs and media type."""
    if not OPAQUE_ID_RE.fullmatch(assessment_id) or not OPAQUE_ID_RE.fullmatch(document_id):
        raise DocumentStorageError("INVALID_STORAGE_PATH")
    suffix = ".pdf" if media_type == MEDIA_TYPE_PDF else ".docx"
    return f"assessments/{assessment_id}/{document_id}{suffix}"


class SupabaseDocumentStorage:
    """Private Supabase Storage adapter using the server-side secret only."""

    def __init__(
        self,
        *,
        supabase_url: str,
        secret_key: str,
        bucket: str = "candidate-evidence",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = supabase_url.rstrip("/")
        self._secret_key = secret_key
        self._bucket = bucket
        self._client = client
        self._owns_client = client is None

    def _headers(self, media_type: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._secret_key}",
            "apikey": self._secret_key,
        }
        if media_type is not None:
            headers["Content-Type"] = media_type
        return headers

    def _object_url(self, storage_path: str) -> str:
        return f"{self._base_url}/storage/v1/object/{self._bucket}/{storage_path}"

    async def _client_for_call(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        return httpx.AsyncClient()

    async def put_private_document(
        self,
        *,
        assessment_id: str,
        document_id: str,
        file_bytes: bytes,
        media_type: str,
        original_filename: str,
    ) -> dict[str, Any]:
        if media_type not in SUPPORTED_MEDIA_TYPES:
            raise DocumentStorageError("UNSUPPORTED_MEDIA_TYPE")
        if not file_bytes:
            raise DocumentStorageError("EMPTY_FILE")
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise DocumentStorageError("FILE_TOO_LARGE")
        digest = hashlib.sha256(file_bytes).hexdigest()
        storage_path = opaque_storage_path(assessment_id, document_id, media_type)
        if original_filename and Path(storage_path).name == original_filename:
            raise DocumentStorageError("INVALID_STORAGE_PATH")
        client = await self._client_for_call()
        close = self._owns_client
        try:
            response = await client.put(
                self._object_url(storage_path),
                content=file_bytes,
                headers=self._headers(media_type),
            )
            if response.status_code >= 400:
                raise DocumentStorageError("STORAGE_PUT_FAILED")
        except DocumentStorageError:
            raise
        except httpx.HTTPError:
            raise DocumentStorageError("STORAGE_PUT_FAILED") from None
        finally:
            if close:
                await client.aclose()
        return {
            "document_id": document_id,
            "storage_path": storage_path,
            "original_filename": original_filename,
            "media_type": media_type,
            "sha256": digest,
            "byte_size": len(file_bytes),
        }

    async def get_private_document(self, storage_path: str) -> bytes:
        client = await self._client_for_call()
        close = self._owns_client
        try:
            response = await client.get(self._object_url(storage_path), headers=self._headers())
            if response.status_code >= 400:
                raise DocumentStorageError("STORAGE_GET_FAILED")
            return bytes(response.content)
        except DocumentStorageError:
            raise
        except httpx.HTTPError:
            raise DocumentStorageError("STORAGE_GET_FAILED") from None
        finally:
            if close:
                await client.aclose()

    async def delete_private_document(self, storage_path: str) -> None:
        client = await self._client_for_call()
        close = self._owns_client
        try:
            response = await client.delete(self._object_url(storage_path), headers=self._headers())
            if response.status_code >= 400:
                raise DocumentStorageError("STORAGE_DELETE_FAILED")
        except DocumentStorageError:
            raise
        except httpx.HTTPError:
            raise DocumentStorageError("STORAGE_DELETE_FAILED") from None
        finally:
            if close:
                await client.aclose()

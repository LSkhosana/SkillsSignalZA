"""Public deterministic CV extraction entry point."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from app.engine.extraction.docx import extract_docx_blocks, looks_like_docx
from app.engine.extraction.outcomes import (
    ERROR_EMPTY_FILE,
    ERROR_ENVELOPE_INVALID,
    ERROR_FILE_TOO_LARGE,
    ERROR_MALFORMED_DOCX,
    ERROR_MALFORMED_PDF,
    ERROR_MEDIA_TYPE_MISMATCH,
    ERROR_NO_EXTRACTABLE_TEXT,
    ERROR_PARSER_EXCEPTION,
    ERROR_UNSUPPORTED_MEDIA_TYPE,
    MAX_FILE_SIZE_BYTES,
    MEDIA_TYPE_DOCX,
    MEDIA_TYPE_PDF,
    SUPPORTED_MEDIA_TYPES,
    completed_outcome,
    cv_source_record,
    document_metadata,
    failed_outcome,
)
from app.engine.extraction.pdf import extract_pdf_blocks


def extract_cv(
    file_bytes: bytes,
    *,
    document_id: str,
    original_filename: str,
    declared_media_type: str,
    extracted_at: str,
) -> dict[str, Any]:
    """Extract ordered CV text blocks from caller-supplied PDF or DOCX bytes.

    This entry point performs no HTTP, persistence, scoring, classification,
    network I/O, or filesystem writes. Parser streams stay in memory.
    """
    byte_size, sha256 = _describe_bytes(file_bytes)
    document = document_metadata(
        document_id=document_id if isinstance(document_id, str) else "",
        original_filename=original_filename if isinstance(original_filename, str) else "",
        declared_media_type=declared_media_type if isinstance(declared_media_type, str) else "",
        verified_media_type=None,
        byte_size=byte_size,
        sha256=sha256,
    )
    try:
        envelope_error = _envelope_error(
            file_bytes,
            document_id=document_id,
            original_filename=original_filename,
            declared_media_type=declared_media_type,
            extracted_at=extracted_at,
        )
        if envelope_error is not None:
            return failed_outcome(envelope_error, document=document)
        if byte_size == 0:
            return failed_outcome(ERROR_EMPTY_FILE, document=document)
        if byte_size > MAX_FILE_SIZE_BYTES:
            return failed_outcome(ERROR_FILE_TOO_LARGE, document=document)
        if declared_media_type not in SUPPORTED_MEDIA_TYPES:
            return failed_outcome(ERROR_UNSUPPORTED_MEDIA_TYPE, document=document)

        actual_type = _sniff_media_type(file_bytes)
        if actual_type is not None and actual_type != declared_media_type:
            return failed_outcome(ERROR_MEDIA_TYPE_MISMATCH, document=document)
        if actual_type is None:
            malformed = (
                ERROR_MALFORMED_PDF
                if declared_media_type == MEDIA_TYPE_PDF
                else ERROR_MALFORMED_DOCX
            )
            return failed_outcome(malformed, document=document)

        document["verified_media_type"] = actual_type
        if actual_type == MEDIA_TYPE_PDF:
            parsed = extract_pdf_blocks(file_bytes)
            if isinstance(parsed, str):
                return failed_outcome(parsed, document=document)
            blocks, locator = parsed
        else:
            parsed = extract_docx_blocks(file_bytes)
            if isinstance(parsed, str):
                return failed_outcome(parsed, document=document)
            blocks = parsed
            locator = "document"

        if not blocks:
            return failed_outcome(ERROR_NO_EXTRACTABLE_TEXT, document=document)

        assert sha256 is not None
        return completed_outcome(
            document=document,
            source_record=cv_source_record(
                document_id=document_id,
                retrieved_at=extracted_at,
                content_hash=sha256,
                locator=locator,
            ),
            content_blocks=blocks,
        )
    except Exception:
        return failed_outcome(ERROR_PARSER_EXCEPTION, document=document)


def _describe_bytes(file_bytes: object) -> tuple[int | None, str | None]:
    if not isinstance(file_bytes, (bytes, bytearray)):
        return None, None
    payload = bytes(file_bytes)
    return len(payload), hashlib.sha256(payload).hexdigest()


def _envelope_error(
    file_bytes: object,
    *,
    document_id: object,
    original_filename: object,
    declared_media_type: object,
    extracted_at: object,
) -> str | None:
    if not isinstance(file_bytes, (bytes, bytearray)):
        return ERROR_ENVELOPE_INVALID
    if not _non_empty_string(document_id):
        return ERROR_ENVELOPE_INVALID
    if not _non_empty_string(original_filename):
        return ERROR_ENVELOPE_INVALID
    if not _non_empty_string(declared_media_type):
        return ERROR_ENVELOPE_INVALID
    if not _non_empty_string(extracted_at):
        return ERROR_ENVELOPE_INVALID
    try:
        datetime.fromisoformat(str(extracted_at).replace("Z", "+00:00"))
    except ValueError:
        return ERROR_ENVELOPE_INVALID
    return None


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _sniff_media_type(file_bytes: bytes) -> str | None:
    if file_bytes.startswith(b"%PDF-"):
        return MEDIA_TYPE_PDF
    if file_bytes.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")) and looks_like_docx(
        file_bytes
    ):
        return MEDIA_TYPE_DOCX
    return None

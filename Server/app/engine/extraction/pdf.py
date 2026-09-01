"""In-memory text-readable PDF extraction."""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from app.engine.extraction.outcomes import (
    ERROR_ENCRYPTED_PDF,
    ERROR_MALFORMED_PDF,
    ERROR_PDF_PAGE_LIMIT_EXCEEDED,
    MAX_PDF_PAGES,
)
from app.engine.extraction.text import split_non_empty_blocks


def extract_pdf_blocks(file_bytes: bytes) -> tuple[list[dict[str, str]], str] | str:
    """Return ordered PDF blocks and a document locator, or a stable error code."""
    try:
        reader = PdfReader(BytesIO(file_bytes), strict=False)
    except (PyPdfError, OSError, ValueError):
        return ERROR_MALFORMED_PDF
    if getattr(reader, "is_encrypted", False):
        return ERROR_ENCRYPTED_PDF
    try:
        page_count = len(reader.pages)
    except (PyPdfError, OSError, ValueError):
        return ERROR_MALFORMED_PDF
    if page_count < 1:
        return ERROR_MALFORMED_PDF
    if page_count > MAX_PDF_PAGES:
        return ERROR_PDF_PAGE_LIMIT_EXCEEDED
    blocks: list[dict[str, str]] = []
    try:
        for page_index, page in enumerate(reader.pages, start=1):
            extracted = page.extract_text() or ""
            for block_index, text in enumerate(split_non_empty_blocks(extracted), start=1):
                blocks.append(
                    {
                        "block_id": f"blk-p{page_index:04d}-{block_index:04d}",
                        "locator": f"page {page_index}, block {block_index}",
                        "text": text,
                    }
                )
    except (PyPdfError, OSError, ValueError):
        return ERROR_MALFORMED_PDF
    locator = "page 1" if page_count <= 1 else f"pages 1-{page_count}"
    return blocks, locator

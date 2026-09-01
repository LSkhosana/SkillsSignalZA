"""In-memory DOCX extraction with ZIP structural preflight."""

from __future__ import annotations

from io import BytesIO
from zipfile import BadZipFile, ZipFile

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.engine.extraction.outcomes import (
    ERROR_DOCX_ENTRY_LIMIT_EXCEEDED,
    ERROR_DOCX_UNCOMPRESSED_SIZE_LIMIT_EXCEEDED,
    ERROR_DOCX_UNSAFE_ARCHIVE,
    ERROR_MALFORMED_DOCX,
    MAX_DOCX_UNCOMPRESSED_BYTES,
    MAX_DOCX_ZIP_ENTRIES,
)
from app.engine.extraction.text import normalize_extracted_text

_MACRO_ENTRY_MARKERS = (
    "vbaproject.bin",
    "vbadata.xml",
)
_MACRO_CONTENT_MARKERS = (
    "application/vnd.ms-word.document.macroenabled",
    "application/vnd.ms-word.template.macroenabled",
)
_PARAGRAPH_TAG = qn("w:p")
_TABLE_TAG = qn("w:tbl")


def looks_like_docx(file_bytes: bytes) -> bool:
    """Return True when the ZIP archive contains the required DOCX parts."""
    try:
        with ZipFile(BytesIO(file_bytes)) as archive:
            names = {_normalize_zip_name(info.filename) for info in archive.infolist()}
    except (BadZipFile, OSError, ValueError):
        return False
    return "[content_types].xml" in names and "word/document.xml" in names


def preflight_docx_archive(file_bytes: bytes) -> str | None:
    """Reject unsafe or oversized DOCX ZIP structure before parsing."""
    try:
        archive = ZipFile(BytesIO(file_bytes))
    except (BadZipFile, OSError, ValueError):
        return ERROR_MALFORMED_DOCX
    try:
        infos = archive.infolist()
        if len(infos) > MAX_DOCX_ZIP_ENTRIES:
            return ERROR_DOCX_ENTRY_LIMIT_EXCEEDED
        uncompressed = 0
        for info in infos:
            if info.flag_bits & 0x1:
                return ERROR_DOCX_UNSAFE_ARCHIVE
            name = _normalize_zip_name(info.filename)
            if _is_traversal_name(name) or _is_macro_entry(name):
                return ERROR_DOCX_UNSAFE_ARCHIVE
            uncompressed += max(info.file_size, 0)
            if uncompressed > MAX_DOCX_UNCOMPRESSED_BYTES:
                return ERROR_DOCX_UNCOMPRESSED_SIZE_LIMIT_EXCEEDED
        if _content_types_are_macro_enabled(archive):
            return ERROR_DOCX_UNSAFE_ARCHIVE
    except (BadZipFile, OSError, ValueError, RuntimeError):
        return ERROR_MALFORMED_DOCX
    finally:
        archive.close()
    return None


def extract_docx_blocks(file_bytes: bytes) -> list[dict[str, str]] | str:
    """Return ordered DOCX blocks or a stable error code."""
    unsafe = preflight_docx_archive(file_bytes)
    if unsafe is not None:
        return unsafe
    try:
        document = Document(BytesIO(file_bytes))
    except (BadZipFile, OSError, ValueError, KeyError):
        return ERROR_MALFORMED_DOCX
    blocks: list[dict[str, str]] = []
    paragraph_number = 0
    table_number = 0
    try:
        for item in _iter_body_items(document):
            if isinstance(item, Paragraph):
                paragraph_number += 1
                text = normalize_extracted_text(item.text or "")
                if not text:
                    continue
                blocks.append(
                    {
                        "block_id": f"blk-p{paragraph_number:04d}",
                        "locator": f"paragraph {paragraph_number}",
                        "text": text.replace("\n", " "),
                    }
                )
                continue
            table_number += 1
            _extend_table_blocks(blocks, item, table_number)
    except (OSError, ValueError, KeyError):
        return ERROR_MALFORMED_DOCX
    return blocks


def _extend_table_blocks(blocks: list[dict[str, str]], table: Table, table_number: int) -> None:
    for row_index, row in enumerate(table.rows, start=1):
        for cell_index, cell in enumerate(row.cells, start=1):
            text = normalize_extracted_text(cell.text or "").replace("\n", " ")
            if not text:
                continue
            blocks.append(
                {
                    "block_id": f"blk-t{table_number:04d}-r{row_index:04d}-c{cell_index:04d}",
                    "locator": f"table {table_number}, row {row_index}, cell {cell_index}",
                    "text": text,
                }
            )


def _iter_body_items(document: Document) -> list[Paragraph | Table]:
    items: list[Paragraph | Table] = []
    for child in document.element.body.iterchildren():
        if child.tag == _PARAGRAPH_TAG:
            items.append(Paragraph(child, document))
        elif child.tag == _TABLE_TAG:
            items.append(Table(child, document))
    return items


def _content_types_are_macro_enabled(archive: ZipFile) -> bool:
    try:
        payload = archive.read("[Content_Types].xml").decode("utf-8", errors="ignore").lower()
    except KeyError:
        return False
    except (OSError, UnicodeError, RuntimeError):
        return True
    return any(marker in payload for marker in _MACRO_CONTENT_MARKERS)


def _normalize_zip_name(name: str) -> str:
    return name.replace("\\", "/").lower()


def _is_traversal_name(name: str) -> bool:
    if name.startswith("/") or name.startswith("../"):
        return True
    parts = [part for part in name.split("/") if part not in {"", "."}]
    return ".." in parts or any(":" in part for part in parts)


def _is_macro_entry(name: str) -> bool:
    return name.rsplit("/", 1)[-1] in _MACRO_ENTRY_MARKERS

"""Package F deterministic CV extraction tests."""

from __future__ import annotations

import ast
import hashlib
import json
from importlib.resources import files
from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import ZipFile, ZipInfo

import pytest
from jsonschema import Draft202012Validator

from app.engine.configuration import load_json
from app.engine.extraction import (
    EXTRACTOR_VERSION,
    MAX_DOCX_UNCOMPRESSED_BYTES,
    MAX_DOCX_ZIP_ENTRIES,
    MAX_FILE_SIZE_BYTES,
    MAX_PDF_PAGES,
    extract_cv,
)
from app.engine.extraction.outcomes import (
    ERROR_DOCX_ENTRY_LIMIT_EXCEEDED,
    ERROR_DOCX_UNCOMPRESSED_SIZE_LIMIT_EXCEEDED,
    ERROR_DOCX_UNSAFE_ARCHIVE,
    ERROR_EMPTY_FILE,
    ERROR_ENCRYPTED_PDF,
    ERROR_ENVELOPE_INVALID,
    ERROR_FILE_TOO_LARGE,
    ERROR_MALFORMED_DOCX,
    ERROR_MALFORMED_PDF,
    ERROR_MEDIA_TYPE_MISMATCH,
    ERROR_NO_EXTRACTABLE_TEXT,
    ERROR_PARSER_EXCEPTION,
    ERROR_PDF_PAGE_LIMIT_EXCEEDED,
    ERROR_UNSUPPORTED_MEDIA_TYPE,
    MEDIA_TYPE_DOCX,
    MEDIA_TYPE_PDF,
)
from tests.fixtures.cv_extraction.documents import (
    build_blank_pdf,
    build_ordered_docx,
    build_text_docx,
    build_text_pdf,
    encrypt_pdf,
)

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "app" / "schemas" / "cv_extraction.schema.json"
EXTRACTION_DIR = Path(__file__).resolve().parents[3] / "app" / "engine" / "extraction"
EXTRACTED_AT = "2026-09-01T10:00:00Z"
SECRET = "C:\\secret\\path traceback must not leak"


def _validator() -> Draft202012Validator:
    return Draft202012Validator(
        load_json(SCHEMA_PATH),
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )


def _extract(file_bytes: bytes, **overrides: Any) -> dict[str, Any]:
    payload = {
        "document_id": "doc-cv-001",
        "original_filename": "candidate-cv.pdf",
        "declared_media_type": MEDIA_TYPE_PDF,
        "extracted_at": EXTRACTED_AT,
    }
    payload.update(overrides)
    return extract_cv(file_bytes, **payload)


def _assert_safe_outcome(outcome: dict[str, Any]) -> None:
    _validator().validate(outcome)
    serialized = json.dumps(outcome)
    assert "assessment_result" not in outcome
    assert "traceback" not in serialized.lower()
    assert SECRET not in serialized
    assert "RuntimeError" not in serialized


def test_schema_is_packaged_and_valid() -> None:
    packaged = files("app.schemas").joinpath("cv_extraction.schema.json")
    assert packaged.is_file()
    schema = json.loads(packaged.read_text(encoding="utf-8"))
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    Draft202012Validator.check_schema(schema)


def test_pdf_extraction_preserves_page_block_order_and_text() -> None:
    file_bytes = build_text_pdf([["Python developer", "Built a Flask API"], ["Second page SQL"]])
    outcome = _extract(file_bytes)
    _assert_safe_outcome(outcome)
    assert outcome["state"] == "COMPLETED"
    assert [block["locator"] for block in outcome["content_blocks"]] == [
        "page 1, block 1",
        "page 1, block 2",
        "page 2, block 1",
    ]
    assert [block["text"] for block in outcome["content_blocks"]] == [
        "Python developer",
        "Built a Flask API",
        "Second page SQL",
    ]
    assert outcome["source_record"]["locator"] == "pages 1-2"


def test_docx_paragraphs_and_table_cells_preserve_document_order() -> None:
    outcome = _extract(
        build_ordered_docx(),
        original_filename="candidate-cv.docx",
        declared_media_type=MEDIA_TYPE_DOCX,
    )
    _assert_safe_outcome(outcome)
    assert [block["locator"] for block in outcome["content_blocks"]] == [
        "paragraph 1",
        "table 1, row 1, cell 1",
        "table 1, row 1, cell 2",
        "paragraph 2",
    ]
    assert [block["text"] for block in outcome["content_blocks"]] == [
        "Intro paragraph",
        "cell a",
        "cell b",
        "Closing paragraph",
    ]
    assert outcome["source_record"]["locator"] == "document"


def test_original_byte_sha256_is_exact() -> None:
    file_bytes = build_text_pdf([["Hashable CV text"]])
    outcome = _extract(file_bytes)
    digest = hashlib.sha256(file_bytes).hexdigest()
    assert outcome["document"]["sha256"] == digest
    assert outcome["source_record"]["content_hash"] == digest
    assert outcome["document"]["byte_size"] == len(file_bytes)


def test_successful_source_record_matches_contract_section_7() -> None:
    outcome = _extract(build_text_pdf([["Contract source record"]]))
    record = outcome["source_record"]
    assert record["source_id"] == "doc-cv-001"
    assert record["source_type"] == "cv"
    assert record["submitted_by_candidate"] is True
    assert record["access_status"] == "accessible"
    assert record["ownership_status"] == "attributed"
    assert record["retrieved_at"] == EXTRACTED_AT
    assert record["extractor_version"] == EXTRACTOR_VERSION
    assert record["locator"]
    assert record["notes"]
    assert "Python" not in record["notes"]


def test_repeated_identical_calls_are_byte_equivalent() -> None:
    file_bytes = build_text_pdf([["Repeated extraction", "Same wording"]])
    first = _extract(file_bytes)
    second = _extract(file_bytes)
    assert json.dumps(first, sort_keys=True, separators=(",", ":")) == json.dumps(
        second, sort_keys=True, separators=(",", ":")
    )


@pytest.mark.parametrize(
    ("file_bytes", "overrides", "error_code"),
    [
        (b"", {}, ERROR_EMPTY_FILE),
        (
            build_text_pdf([["text"]]),
            {"declared_media_type": "text/plain"},
            ERROR_UNSUPPORTED_MEDIA_TYPE,
        ),
        (
            build_text_pdf([["text"]]),
            {
                "declared_media_type": MEDIA_TYPE_DOCX,
                "original_filename": "candidate-cv.docx",
            },
            ERROR_MEDIA_TYPE_MISMATCH,
        ),
        (b"%PDF-1.4\nnot-a-real-pdf", {}, ERROR_MALFORMED_PDF),
        (encrypt_pdf(build_text_pdf([["secret text"]])), {}, ERROR_ENCRYPTED_PDF),
        (
            b"PK\x03\x04not-a-docx",
            {
                "declared_media_type": MEDIA_TYPE_DOCX,
                "original_filename": "candidate-cv.docx",
            },
            ERROR_MALFORMED_DOCX,
        ),
        (build_blank_pdf(1), {}, ERROR_NO_EXTRACTABLE_TEXT),
        (build_text_pdf([["text"]]), {"document_id": ""}, ERROR_ENVELOPE_INVALID),
        (
            build_text_pdf([["text"]]),
            {"extracted_at": "not-an-rfc3339-datetime"},
            ERROR_ENVELOPE_INVALID,
        ),
    ],
    ids=[
        "empty_file",
        "unsupported_type",
        "media_type_mismatch",
        "malformed_pdf",
        "encrypted_pdf",
        "malformed_docx",
        "no_extractable_text",
        "empty_document_id",
        "invalid_extracted_at",
    ],
)
def test_expected_failures_are_safe(
    file_bytes: bytes,
    overrides: dict[str, Any],
    error_code: str,
) -> None:
    outcome = _extract(file_bytes, **overrides)
    _assert_safe_outcome(outcome)
    assert outcome["state"] == "CV_EXTRACTION_FAILED"
    assert outcome["error_code"] == error_code
    assert outcome["source_record"] is None
    assert outcome["content_blocks"] == []
    if file_bytes:
        assert outcome["document"]["sha256"] == hashlib.sha256(file_bytes).hexdigest()


def test_file_size_limit_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.engine.extraction.cv.MAX_FILE_SIZE_BYTES", 16)
    file_bytes = b"x" * 17
    outcome = _extract(file_bytes)
    _assert_safe_outcome(outcome)
    assert outcome["error_code"] == ERROR_FILE_TOO_LARGE
    assert outcome["document"]["byte_size"] == 17
    assert outcome["document"]["sha256"] == hashlib.sha256(file_bytes).hexdigest()
    assert outcome["content_blocks"] == []


def test_pdf_page_limit_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.engine.extraction.pdf.MAX_PDF_PAGES", 2)
    outcome = _extract(build_text_pdf([["one"], ["two"], ["three"]]))
    _assert_safe_outcome(outcome)
    assert outcome["error_code"] == ERROR_PDF_PAGE_LIMIT_EXCEEDED


def test_docx_macro_and_traversal_entries_are_rejected() -> None:
    safe = build_text_docx(paragraphs=["Visible paragraph"])
    with_macro = _with_zip_entry(safe, "word/vbaProject.bin", b"macro")
    with_traversal = _with_zip_entry(safe, "../evil.txt", b"nope")
    for payload in (with_macro, with_traversal):
        outcome = _extract(
            payload,
            original_filename="candidate-cv.docx",
            declared_media_type=MEDIA_TYPE_DOCX,
        )
        _assert_safe_outcome(outcome)
        assert outcome["error_code"] == ERROR_DOCX_UNSAFE_ARCHIVE


def test_docx_encrypted_zip_entry_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    class FlaggedZip(ZipFile):
        def infolist(self) -> list[ZipInfo]:
            infos = list(super().infolist())
            if infos:
                infos[0].flag_bits |= 0x1
            return infos

    monkeypatch.setattr("app.engine.extraction.docx.ZipFile", FlaggedZip)
    outcome = _extract(
        build_text_docx(paragraphs=["Visible paragraph"]),
        original_filename="candidate-cv.docx",
        declared_media_type=MEDIA_TYPE_DOCX,
    )
    _assert_safe_outcome(outcome)
    assert outcome["error_code"] == ERROR_DOCX_UNSAFE_ARCHIVE


def test_docx_entry_and_uncompressed_limits_are_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    file_bytes = build_text_docx(paragraphs=["Visible paragraph"])
    monkeypatch.setattr("app.engine.extraction.docx.MAX_DOCX_ZIP_ENTRIES", 1)
    over_entries = _extract(
        file_bytes,
        original_filename="candidate-cv.docx",
        declared_media_type=MEDIA_TYPE_DOCX,
    )
    _assert_safe_outcome(over_entries)
    assert over_entries["error_code"] == ERROR_DOCX_ENTRY_LIMIT_EXCEEDED

    monkeypatch.setattr("app.engine.extraction.docx.MAX_DOCX_ZIP_ENTRIES", MAX_DOCX_ZIP_ENTRIES)
    monkeypatch.setattr("app.engine.extraction.docx.MAX_DOCX_UNCOMPRESSED_BYTES", 10)
    over_size = _extract(
        file_bytes,
        original_filename="candidate-cv.docx",
        declared_media_type=MEDIA_TYPE_DOCX,
    )
    _assert_safe_outcome(over_size)
    assert over_size["error_code"] == ERROR_DOCX_UNCOMPRESSED_SIZE_LIMIT_EXCEEDED


def test_parser_exceptions_do_not_leak_unsafe_details(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_file_bytes: bytes) -> object:
        raise RuntimeError(f"{SECRET} Built a Flask API")

    monkeypatch.setattr("app.engine.extraction.cv.extract_pdf_blocks", boom)
    outcome = _extract(build_text_pdf([["Built a Flask API"]]))
    _assert_safe_outcome(outcome)
    assert outcome["error_code"] == ERROR_PARSER_EXCEPTION
    assert "Built a Flask API" not in json.dumps(outcome)


def test_extraction_does_not_persist_files_or_use_scoring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "app.engine.scoring.score_assessment",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("scoring")),
    )
    outcome = _extract(build_text_pdf([["No persistence"]]))
    _assert_safe_outcome(outcome)
    assert outcome["state"] == "COMPLETED"
    assert list(tmp_path.iterdir()) == []


def test_extraction_modules_have_no_forbidden_dependencies() -> None:
    forbidden = {
        "socket",
        "httpx",
        "requests",
        "urllib",
        "http.client",
        "subprocess",
        "app.engine.scoring",
        "score_assessment",
        "golden_candidates",
    }
    for path in EXTRACTION_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        text = path.read_text(encoding="utf-8")
        assert not forbidden.intersection(imported)
        for token in forbidden:
            assert token not in text


def test_named_safety_limits_match_launch_values() -> None:
    assert MAX_FILE_SIZE_BYTES == 10 * 1024 * 1024
    assert MAX_PDF_PAGES == 100
    assert MAX_DOCX_ZIP_ENTRIES == 256
    assert MAX_DOCX_UNCOMPRESSED_BYTES == 32 * 1024 * 1024
    assert EXTRACTOR_VERSION == "extract.cv.v1"


def test_repeated_docx_text_is_not_deduplicated() -> None:
    outcome = _extract(
        build_text_docx(paragraphs=["Same wording", "Same wording"]),
        original_filename="candidate-cv.docx",
        declared_media_type=MEDIA_TYPE_DOCX,
    )
    _assert_safe_outcome(outcome)
    assert [block["text"] for block in outcome["content_blocks"]] == [
        "Same wording",
        "Same wording",
    ]


def _with_zip_entry(docx_bytes: bytes, name: str, payload: bytes) -> bytes:
    buffer = BytesIO()
    with ZipFile(BytesIO(docx_bytes)) as source, ZipFile(buffer, "w") as target:
        for info in source.infolist():
            target.writestr(info, source.read(info.filename))
        target.writestr(name, payload)
    return buffer.getvalue()

"""Run the zero-cost SkillSignalZA job-post collector locally."""

from __future__ import annotations

import argparse
import json
import mimetypes
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from scraper.extractor import extract_record
from scraper.fetcher import FetchError, fetch_job_page, page_from_manual_text
from scraper.schema import TRACK_HEADERS
from scraper.workbook import WorkbookError, WorkbookStore


ROOT = Path(__file__).resolve().parent
TEMPLATE_PATH = ROOT / "data" / "SkillSignalZA_JobPost_Collection_Template.xlsx"
WORKING_PATH = ROOT / "exports" / "SkillSignalZA_JobPost_Collection_Working.xlsx"
STORE = WorkbookStore(TEMPLATE_PATH, WORKING_PATH)
MAX_REQUEST_BYTES = 2 * 1024 * 1024


class CollectorHandler(BaseHTTPRequestHandler):
    server_version = "SkillSignalZACollector/1.0"

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/":
            self._send_file(ROOT / "templates" / "index.html")
        elif path.startswith("/static/"):
            relative = unquote(path.removeprefix("/static/"))
            self._send_static(relative)
        elif path == "/api/status":
            try:
                status = STORE.status()
                status["headers"] = TRACK_HEADERS
                self._send_json(status)
            except WorkbookError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
        elif path == "/api/export":
            try:
                file_path = STORE.ensure_working_copy()
                self._send_file(file_path, download_name=file_path.name)
            except WorkbookError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
        else:
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            payload = self._read_json()
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if path == "/api/extract":
            self._handle_extract(payload)
        elif path == "/api/records":
            self._handle_record(payload)
        else:
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def _handle_extract(self, payload: dict[str, object]) -> None:
        track = str(payload.get("track", "")).strip()
        url = str(payload.get("url", "")).strip()
        manual_text = str(payload.get("manual_text", "")).strip()
        if track not in TRACK_HEADERS:
            self._send_json({"error": "Select a collection track."}, HTTPStatus.BAD_REQUEST)
            return
        if not url.startswith(("http://", "https://")):
            self._send_json(
                {"error": "Enter a complete job-post URL beginning with http:// or https://."},
                HTTPStatus.BAD_REQUEST,
            )
            return
        try:
            if manual_text:
                page = page_from_manual_text(url, manual_text)
                used_fallback = True
            else:
                page = fetch_job_page(url)
                used_fallback = False
            record, warnings = extract_record(page, track)
            if used_fallback:
                warnings.insert(0, "Manual pasted text was used; page metadata may need to be completed.")
                record["Notes / Anything Unusual"] = " | ".join(warnings)
            self._send_json(
                {
                    "record": record,
                    "warnings": warnings,
                    "used_manual_text": used_fallback,
                    "source_word_count": len(page.text.split()),
                }
            )
        except FetchError as exc:
            self._send_json(
                {"error": str(exc), "needs_manual_text": True},
                HTTPStatus.UNPROCESSABLE_ENTITY,
            )
        except Exception as exc:  # keep the local UI useful while preserving the console traceback
            print(f"Extraction error: {exc!r}")
            self._send_json(
                {"error": "The post could not be extracted. Paste the full job text and try again."},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def _handle_record(self, payload: dict[str, object]) -> None:
        track = str(payload.get("track", "")).strip()
        record = payload.get("record")
        if not isinstance(record, dict):
            self._send_json({"error": "The record data is missing."}, HTTPStatus.BAD_REQUEST)
            return
        try:
            result = STORE.add_record(track, record)
            result["status"] = STORE.status()
            self._send_json(result, HTTPStatus.CREATED)
        except WorkbookError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.CONFLICT)

    def _read_json(self) -> dict[str, object]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid request length.") from exc
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("Request is empty or too large.")
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Request must contain valid JSON.") from exc
        if not isinstance(value, dict):
            raise ValueError("Request must contain a JSON object.")
        return value

    def _send_static(self, relative: str) -> None:
        static_root = (ROOT / "static").resolve()
        file_path = (static_root / relative).resolve()
        if static_root not in file_path.parents or not file_path.is_file():
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        self._send_file(file_path)

    def _send_file(self, path: Path, download_name: str | None = None) -> None:
        if not path.is_file():
            self._send_json({"error": "File not found"}, HTTPStatus.NOT_FOUND)
            return
        content = path.read_bytes()
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store" if download_name else "no-cache")
        if download_name:
            self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SkillSignalZA job-post collector.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    STORE.ensure_working_copy()
    server = ThreadingHTTPServer((args.host, args.port), CollectorHandler)
    url = f"http://{args.host}:{args.port}"
    print(f"SkillSignalZA collector is running at {url}")
    print("Press Ctrl+C to stop it.")
    if not args.no_browser:
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping collector.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()


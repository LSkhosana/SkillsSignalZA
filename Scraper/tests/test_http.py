import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

import app
from scraper.workbook import WorkbookStore


ROOT = Path(__file__).resolve().parents[1]


class HTTPFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        app.STORE = WorkbookStore(
            ROOT / "data" / "SkillSignalZA_JobPost_Collection_Template.xlsx",
            Path(cls.temp.name) / "working.xlsx",
        )
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.CollectorHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.temp.cleanup()

    def post_json(self, path, payload):
        request = Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())

    def test_manual_extract_create_and_export(self):
        with urlopen(self.base_url + "/api/status", timeout=5) as response:
            status = json.loads(response.read())
        self.assertEqual(status["counts"]["SE Track"], 0)

        _, extracted = self.post_json(
            "/api/extract",
            {
                "track": "SE Track",
                "url": "https://example.co.za/jobs/http-test",
                "manual_text": (
                    "Junior Python Developer\n\nJohannesburg, South Africa. Hybrid role.\n\n"
                    "Requirements: 0-2 years experience, Python, Flask, Git and PostgreSQL. "
                    "Degree preferred. Attention to detail and willingness to learn."
                ),
            },
        )
        record = extracted["record"]
        self.assertEqual(record["Programming Languages Mentioned"], "Python")
        self.assertEqual(record["Frameworks/Libraries Mentioned"], "Flask")
        record["Job Title (as written)"] = "Junior Python Developer"
        record["Company Name"] = "Example Labs"
        record["Location"] = "Johannesburg, South Africa"
        record["Date Posted"] = "2026-08-04"

        status_code, created = self.post_json(
            "/api/records", {"track": "SE Track", "record": record}
        )
        self.assertEqual(status_code, 201)
        self.assertEqual(created["post_id"], "SE-001")
        self.assertEqual(created["status"]["counts"]["SE Track"], 1)

        with urlopen(self.base_url + "/api/export", timeout=5) as response:
            exported = response.read()
            self.assertIn("application/vnd.openxmlformats", response.headers["Content-Type"])
        self.assertGreater(len(exported), 10_000)
        self.assertEqual(exported[:2], b"PK")


if __name__ == "__main__":
    unittest.main()


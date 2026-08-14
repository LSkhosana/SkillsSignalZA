import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from scraper.schema import TRACK_HEADERS
from scraper.workbook import WorkbookError, WorkbookStore


ROOT = Path(__file__).resolve().parents[1]


def sample_record(url: str) -> dict[str, str]:
    record = {header: "" for header in TRACK_HEADERS["SE Track"]}
    record.update(
        {
            "Post ID": "Generated when saved",
            "Job Title (as written)": "Junior Developer",
            "Company Name": "Example Company",
            "Location": "Johannesburg, Gauteng, ZA",
            "Work Type": "Hybrid",
            "Source / Job Board": "Example careers",
            "Job Post URL": url,
            "Date Posted": "2026-08-01",
            "Date Collected": "2026-08-05",
            "Experience Required (years)": "0-2",
            "Qualification Required": "Degree preferred",
            "Programming Languages Mentioned": "Python",
            "Frameworks/Libraries Mentioned": "Flask",
            "Git/GitHub Explicitly Named (Y/N)": "Y",
            "Tools & Platforms Mentioned": "Git/GitHub",
            "Portfolio/GitHub Requested (Y/N)": "N",
            "Requirement Level (Required/Preferred/Not Mentioned)": "Not Mentioned",
            "Soft Skills Mentioned (verbatim)": "attention to detail",
            "Specific Readiness Signals (verbatim, beyond generic buzzwords)": "willingness to learn",
            "Key Requirements Paragraph (paste)": "Requirements include Python, Flask and Git.",
            "Notes / Anything Unusual": "",
        }
    )
    return record


class WorkbookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.template = ROOT / "data" / "SkillSignalZA_JobPost_Collection_Template.xlsx"
        self.working = Path(self.temp.name) / "working.xlsx"
        self.store = WorkbookStore(self.template, self.working)

    def tearDown(self):
        self.temp.cleanup()

    def test_first_record_replaces_example_and_preserves_template(self):
        template_before = self.template.read_bytes()
        result = self.store.add_record("SE Track", sample_record("https://example.co.za/jobs/1"))
        self.assertEqual(result["post_id"], "SE-001")
        workbook = load_workbook(self.working, data_only=True)
        try:
            sheet = workbook["SE Track"]
            self.assertEqual(sheet["A2"].value, "SE-001")
            self.assertEqual(sheet["B2"].value, "Junior Developer")
            self.assertEqual(sheet.freeze_panes, "A2")
        finally:
            workbook.close()
        self.assertEqual(self.template.read_bytes(), template_before)
        self.assertEqual(self.store.status()["counts"]["SE Track"], 1)

    def test_duplicate_url_is_blocked(self):
        record = sample_record("https://example.co.za/jobs/duplicate")
        self.store.add_record("SE Track", record)
        record["Job Title (as written)"] = "Another title"
        with self.assertRaisesRegex(WorkbookError, "exact job-post URL"):
            self.store.add_record("SE Track", record)

    def test_second_record_gets_next_id(self):
        self.store.add_record("SE Track", sample_record("https://example.co.za/jobs/1"))
        second = sample_record("https://example.co.za/jobs/2")
        second["Job Title (as written)"] = "Graduate Developer"
        result = self.store.add_record("SE Track", second)
        self.assertEqual(result["post_id"], "SE-002")


if __name__ == "__main__":
    unittest.main()


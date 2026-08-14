import unittest

from scraper.extractor import extract_record
from scraper.fetcher import parse_html


class ExtractorTests(unittest.TestCase):
    def test_software_engineering_json_ld_and_explicit_skills(self):
        html = """
        <html><head>
          <script type="application/ld+json">
          {
            "@context": "https://schema.org",
            "@type": "JobPosting",
            "title": "Junior Software Developer",
            "datePosted": "2026-08-01",
            "hiringOrganization": {"@type": "Organization", "name": "Acme SA"},
            "jobLocation": {"address": {
              "addressLocality": "Johannesburg",
              "addressRegion": "Gauteng",
              "addressCountry": "ZA"
            }},
            "description": "<p>Requirements: 0-2 years of experience. JavaScript, React and Git are required. A degree is preferred.</p><p>Submit your GitHub profile. Excellent written and verbal communication skills and willingness to learn are important.</p>"
          }
          </script>
        </head><body><h1>Junior Software Developer</h1></body></html>
        """
        page = parse_html("https://jobs.example.co.za/123", html)
        record, warnings = extract_record(page, "SE Track")
        self.assertEqual(record["Job Title (as written)"], "Junior Software Developer")
        self.assertEqual(record["Company Name"], "Acme SA")
        self.assertEqual(record["Programming Languages Mentioned"], "JavaScript")
        self.assertEqual(record["Frameworks/Libraries Mentioned"], "React")
        self.assertEqual(record["Git/GitHub Explicitly Named (Y/N)"], "Y")
        self.assertEqual(record["Portfolio/GitHub Requested (Y/N)"], "Y")
        self.assertEqual(record["Requirement Level (Required/Preferred/Not Mentioned)"], "Required")
        self.assertEqual(record["Experience Required (years)"], "0-2")
        self.assertEqual(record["Qualification Required"], "Degree preferred")
        self.assertFalse(any("outside South Africa" in warning for warning in warnings))

    def test_framework_does_not_imply_language(self):
        page = parse_html(
            "https://example.co.za/job/2",
            "<html><body><h1>Junior Developer</h1><p>Requirements include React and Git.</p></body></html>",
        )
        record, warnings = extract_record(page, "SE Track")
        self.assertEqual(record["Programming Languages Mentioned"], "")
        self.assertEqual(record["Frameworks/Libraries Mentioned"], "React")
        self.assertTrue(any("no programming language" in warning for warning in warnings))

    def test_data_analyst_fields(self):
        page = parse_html(
            "https://careers.example.co.za/data-analyst",
            """
            <html><body><h1>Graduate Data Analyst</h1>
            <p>Based in Cape Town, South Africa. This is a hybrid role.</p>
            <p>Requirements: SQL, advanced Excel with pivot tables, Power BI and Python.
            You will clean raw data, present findings to non-technical stakeholders and prepare written reports.
            No prior experience is required. A bachelor's degree is required.</p>
            </body></html>
            """,
        )
        record, _ = extract_record(page, "DA Track")
        self.assertIn("SQL", record["Core Analytical Skills Mentioned"])
        self.assertIn("Excel (advanced)", record["Core Analytical Skills Mentioned"])
        self.assertIn("Power BI", record["Reporting/Visualization Tools Mentioned"])
        self.assertEqual(record["SQL Explicitly Named (Y/N)"], "Y")
        self.assertEqual(record["Work Type"], "Hybrid")
        self.assertEqual(record["Experience Required (years)"], "0")
        self.assertEqual(record["Qualification Required"], "Degree required")
        self.assertIn("present findings to non-technical stakeholders", record["Specific Readiness Signals (verbatim, beyond generic buzzwords)"])


if __name__ == "__main__":
    unittest.main()


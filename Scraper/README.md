# SkillSignalZA Job Post Collector

A small, zero-API-cost collection tool for Step 3 of SkillSignalZA research. It takes one public job-post URL, extracts as many of the workbook's 21 fields as deterministic Python rules can support, lets the researcher edit every value, and writes the approved record to the supplied Excel template.

The program does **not** use OpenAI, Claude, or another paid extraction API. It also does not need authentication or a database.

## What V1 does

- Selects either `SE Track` or `DA Track`.
- Attempts to retrieve one public job-post URL.
- Reads structured `JobPosting` JSON-LD when the page supplies it.
- Falls back to cleaned visible page text.
- Provides a paste-text fallback when a board blocks automatic retrieval.
- Extracts and normalizes explicit technologies against the workbook vocabulary.
- Detects experience, qualifications, work type, portfolio requests, soft skills, and readiness phrases using local rules.
- Flags missing metadata, possible senior roles, 5+ year requirements, unconfirmed South African locations, and weak source text.
- Shows all 21 fields in an editable review form.
- Blocks exact duplicate URLs and duplicate title/company/location combinations.
- Generates `SE-001` / `DA-001` IDs when records are saved.
- Preserves the supplied template and writes to a separate working workbook.
- Removes both example rows from the working copy while leaving their formatting ready for real records.
- Keeps the immediately previous workbook as `*_LastBackup.xlsx`.
- Exports the current collection as `.xlsx`.

## Windows quick start

Double-click:

```text
run_collector.bat
```

The first run creates a private `.venv` folder and installs `openpyxl`. The app then opens at:

```text
http://127.0.0.1:8765
```

This route does not require PowerShell script activation, so it avoids Windows execution-policy friction.

### Manual command option

From Command Prompt or the Cursor terminal in this `Scraper` folder:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Press `Ctrl+C` in the terminal to stop the program.

## Collection workflow

1. Choose Software Engineering or Data Analyst.
2. Paste the original job-post URL.
3. Select **Extract post**.
4. If the page is blocked or login-rendered, expand the manual fallback and paste the full page text.
5. Review all 21 proposed values. Amber fields are missing or need attention.
6. Correct anything the rules did not understand.
7. Select **Create record**.
8. Use **Export current .xlsx** whenever you want the latest workbook.

## Files and data safety

The supplied source files remain in `data/`:

```text
data/SkillSignalZA_Rubric_V1.docx
data/SkillSignalZA_JobPost_Collection_Template.xlsx
```

The program creates this working file on first launch:

```text
exports/SkillSignalZA_JobPost_Collection_Working.xlsx
```

Each successful write first preserves the prior version as:

```text
exports/SkillSignalZA_JobPost_Collection_Working_LastBackup.xlsx
```

Do not keep the working workbook open in Excel while selecting **Create record**. Windows may lock it and prevent a safe atomic save. You can open an exported copy whenever needed.

Generated workbooks are ignored by Git so collected job data is not accidentally committed.

## Extraction rules that protect data quality

- A framework never implies its parent language. `React` does not produce `JavaScript` unless JavaScript is named.
- A Python library never implies Python. `pandas` does not produce `Python` unless Python is named.
- Git/GitHub and SQL flags are based only on explicit words in the post.
- Soft-skill and readiness outputs are exact matched phrases from the source, not paraphrases.
- `Portfolio/GitHub Requested` requires language asking for a portfolio, profile, link, or code sample. A normal Git tool requirement does not count.
- Anything uncertain remains blank or is flagged for manual review.

## Known V1 limits

- LinkedIn and some other job boards may block a direct request, require login, or render the post only in JavaScript. Use the built-in paste fallback.
- Rules can miss unusual wording and cannot interpret context as deeply as an LLM.
- Metadata can be absent from copied text. Fill title, company, location, and date manually when necessary.
- The tool handles one post at a time by design; it does not crawl search results, bypass access controls, or solve CAPTCHAs.
- Extraction is designed to remove most typing, not replace the final human quality check.

## Run the tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Project structure

```text
Scraper/
├── app.py
├── run_collector.bat
├── requirements.txt
├── data/
├── exports/
├── scraper/
│   ├── extractor.py
│   ├── fetcher.py
│   ├── schema.py
│   └── workbook.py
├── static/
│   ├── app.js
│   └── styles.css
├── templates/
│   └── index.html
└── tests/
```

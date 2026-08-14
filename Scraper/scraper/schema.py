"""Workbook schema and normalized extraction vocabulary."""

from __future__ import annotations


COMMON_HEADERS = [
    "Post ID",
    "Job Title (as written)",
    "Company Name",
    "Location",
    "Work Type",
    "Source / Job Board",
    "Job Post URL",
    "Date Posted",
    "Date Collected",
    "Experience Required (years)",
    "Qualification Required",
]

TRACK_HEADERS = {
    "SE Track": COMMON_HEADERS
    + [
        "Programming Languages Mentioned",
        "Frameworks/Libraries Mentioned",
        "Git/GitHub Explicitly Named (Y/N)",
        "Tools & Platforms Mentioned",
        "Portfolio/GitHub Requested (Y/N)",
        "Requirement Level (Required/Preferred/Not Mentioned)",
        "Soft Skills Mentioned (verbatim)",
        "Specific Readiness Signals (verbatim, beyond generic buzzwords)",
        "Key Requirements Paragraph (paste)",
        "Notes / Anything Unusual",
    ],
    "DA Track": COMMON_HEADERS
    + [
        "Core Analytical Skills Mentioned",
        "Reporting/Visualization Tools Mentioned",
        "SQL Explicitly Named (Y/N)",
        "Tools & Platforms Mentioned",
        "Portfolio/GitHub Requested (Y/N)",
        "Requirement Level (Required/Preferred/Not Mentioned)",
        "Soft Skills Mentioned (verbatim)",
        "Specific Readiness Signals (verbatim, beyond generic buzzwords)",
        "Key Requirements Paragraph (paste)",
        "Notes / Anything Unusual",
    ],
}

TRACK_CODES = {"SE Track": "SE", "DA Track": "DA"}

# Values are kept in the same order as the workbook's Skills Reference sheet.
SE_LANGUAGES = {
    "JavaScript": [r"\bjavascript\b", r"\bjava[ -]?script\b", r"\bjs\b"],
    "TypeScript": [r"\btypescript\b", r"\btype[ -]?script\b", r"\bts\b"],
    "Python": [r"\bpython\b"],
    "Java": [r"\bjava\b"],
    "C#": [r"(?<!\w)c#(?!\w)", r"\bc[ -]?sharp\b"],
    "PHP": [r"\bphp\b"],
    "HTML/CSS": [r"\bhtml5?\b", r"\bcss3?\b", r"\bhtml\s*/\s*css\b"],
    "SQL": [r"\bsql\b"],
}

SE_FRAMEWORKS = {
    "React": [r"\breact(?:\.js|js)?\b"],
    "Angular": [r"\bangular(?:\.js|js)?\b"],
    "Vue": [r"\bvue(?:\.js|js)?\b"],
    "Node.js": [r"\bnode(?:\.js|js)?\b"],
    "Express": [r"\bexpress(?:\.js|js)?\b"],
    ".NET": [r"(?<!\w)\.net\b", r"\bdotnet\b", r"\basp\.net\b"],
    "Django": [r"\bdjango\b"],
    "Flask": [r"\bflask\b"],
}

SE_TOOLS = {
    "Git/GitHub": [r"\bgit\b", r"\bgithub\b"],
    "VS Code": [r"\bvs\s*code\b", r"\bvisual studio code\b"],
    "Docker": [r"\bdocker\b"],
    "AWS": [r"\baws\b", r"\bamazon web services\b"],
    "Azure": [r"\bazure\b"],
    "GCP": [r"\bgcp\b", r"\bgoogle cloud(?: platform)?\b"],
    "Postman": [r"\bpostman\b"],
    "Jira": [r"\bjira\b"],
    "Linux": [r"\blinux\b"],
    "MySQL": [r"\bmysql\b"],
    "PostgreSQL": [r"\bpostgres(?:ql)?\b"],
    "SQL Server": [r"\b(?:microsoft\s+)?sql server\b", r"\bmssql\b"],
    "SQLite": [r"\bsqlite\b"],
    "MongoDB": [r"\bmongodb\b", r"\bmongo\s+db\b"],
    "Firebase": [r"\bfirebase\b"],
    "Supabase": [r"\bsupabase\b"],
    "Kubernetes": [r"\bkubernetes\b", r"\bk8s\b"],
}

DA_CORE = {
    "SQL": [r"\bsql\b"],
    "Excel (advanced)": [
        r"\badvanced excel\b",
        r"\bexcel[^.\n]{0,70}\b(?:pivot tables?|power query|vlookup|xlookup|macros?|power pivot)\b",
        r"\b(?:pivot tables?|power query|vlookup|xlookup|macros?|power pivot)\b[^.\n]{0,70}\bexcel\b",
    ],
    "Python": [r"\bpython\b"],
    "R": [r"(?<!\w)R(?!\w)"],
    "Statistics": [r"\bstatistics?\b", r"\bstatistical analysis\b"],
    "Data Cleaning": [r"\bdata clean(?:ing|sing)\b", r"\bclean(?:ing|se) (?:raw )?data\b"],
    "Data Modelling": [r"\bdata model(?:l?ing)?\b", r"\bdimensional model(?:l?ing)?\b"],
}

DA_REPORTING = {
    "Power BI": [r"\bpower\s*bi\b"],
    "Tableau": [r"\btableau\b"],
    "Google Data Studio / Looker Studio": [
        r"\bgoogle data studio\b",
        r"\blooker studio\b",
    ],
    "Excel (dashboards/pivot tables)": [
        r"\bexcel[^.\n]{0,70}\b(?:dashboards?|pivot tables?)\b",
        r"\b(?:dashboards?|pivot tables?)\b[^.\n]{0,70}\bexcel\b",
    ],
}

DA_TOOLS = {
    "Excel": [r"\b(?:microsoft\s+|ms\s+)?excel\b"],
    "SQL Server / MySQL / PostgreSQL": [
        r"\b(?:microsoft\s+)?sql server\b",
        r"\bmssql\b",
        r"\bmysql\b",
        r"\bpostgres(?:ql)?\b",
    ],
    "Google Sheets": [r"\bgoogle sheets\b"],
    "Jira": [r"\bjira\b"],
    "Power Query": [r"\bpower query\b"],
    "BigQuery": [r"\bbigquery\b", r"\bbig query\b"],
    "Microsoft Fabric": [r"\bmicrosoft fabric\b"],
    "pandas": [r"\bpandas\b"],
    "NumPy": [r"\bnumpy\b"],
    "matplotlib": [r"\bmatplotlib\b"],
    "seaborn": [r"\bseaborn\b"],
}

LONG_TEXT_FIELDS = {
    "Soft Skills Mentioned (verbatim)",
    "Specific Readiness Signals (verbatim, beyond generic buzzwords)",
    "Key Requirements Paragraph (paste)",
    "Notes / Anything Unusual",
}


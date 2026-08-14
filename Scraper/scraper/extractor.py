"""Rules-based extraction for the two SkillSignalZA collection tracks."""

from __future__ import annotations

import html
import re
from datetime import date
from typing import Any, Iterable
from urllib.parse import urlparse

from .fetcher import PageContent, parse_html
from .schema import (
    DA_CORE,
    DA_REPORTING,
    DA_TOOLS,
    SE_FRAMEWORKS,
    SE_LANGUAGES,
    SE_TOOLS,
    TRACK_HEADERS,
)


SOURCE_NAMES = {
    "linkedin.com": "LinkedIn",
    "indeed.com": "Indeed",
    "indeed.co.za": "Indeed",
    "pnet.co.za": "PNet",
    "careers24.com": "Careers24",
    "offerzen.com": "OfferZen",
    "glassdoor.com": "Glassdoor",
    "careerjunction.co.za": "CareerJunction",
    "simplify.hr": "Simplify",
}

SOFT_SKILL_PATTERNS = [
    r"\battention to detail\b",
    r"\bexcellent written and verbal communication(?: skills)?\b",
    r"\bwritten and verbal communication(?: skills)?\b",
    r"\bcommunication skills\b",
    r"\bproblem[- ]solving(?: skills)?\b",
    r"\banalytical thinking\b",
    r"\bcritical thinking\b",
    r"\btime management\b",
    r"\binterpersonal skills\b",
    r"\bteam(?:work| player)\b",
    r"\bcollaborat(?:e|ion|ive)(?: skills)?\b",
    r"\borganisational skills\b",
    r"\borganizational skills\b",
    r"\badaptab(?:le|ility)\b",
    r"\bself[- ]motivated\b",
]

READINESS_PATTERNS = [
    r"\bwilling(?:ness)? to learn\b",
    r"\beager to learn\b",
    r"\bcontinuous learning\b",
    r"\bwork(?:ing)? independently\b",
    r"\btake ownership\b",
    r"\bmanage competing priorities\b",
    r"\bcommunicat(?:e|ing) with (?:non-technical )?stakeholders\b",
    r"\bpresent(?:ing)? (?:data |technical )?(?:findings|insights|results) to (?:non-technical )?stakeholders\b",
    r"\bpresent(?:ing)? (?:data |technical )?(?:findings|insights|results)\b",
    r"\bprepare (?:written )?reports\b",
    r"\bwrite (?:clear )?(?:technical )?documentation\b",
    r"\bclient[- ]facing\b",
    r"\bcross[- ]functional (?:team|environment|collaboration)\b",
    r"\bmentorship (?:is )?provided\b",
    r"\bon[- ]the[- ]job training\b",
    r"\bgraduate programme\b",
    r"\bgraduate program\b",
    r"\binternship experience\b",
]


def _iter_nodes(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _iter_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_nodes(child)


def _job_posting(page: PageContent) -> dict[str, Any]:
    for root in page.json_ld:
        for node in _iter_nodes(root):
            node_type = node.get("@type", "")
            types = node_type if isinstance(node_type, list) else [node_type]
            if any(str(item).lower() == "jobposting" for item in types):
                return node
    return {}


def _plain_text(value: Any) -> str:
    if value is None:
        return ""
    raw = html.unescape(str(value))
    if "<" in raw and ">" in raw:
        parsed = parse_html("https://example.invalid", raw)
        return "\n".join(parsed.paragraphs)
    return re.sub(r"\s+", " ", raw).strip()


def _description_paragraphs(job: dict[str, Any], page: PageContent) -> list[str]:
    description = job.get("description") or job.get("responsibilities") or ""
    paragraphs: list[str] = []
    if description:
        raw = html.unescape(str(description))
        if "<" in raw and ">" in raw:
            paragraphs = parse_html("https://example.invalid", raw).paragraphs
        else:
            paragraphs = [
                re.sub(r"\s+", " ", part).strip()
                for part in re.split(
                    r"\n\s*\n|^\s*[•●▪*-]\s+", raw, flags=re.MULTILINE
                )
                if part.strip()
            ]
    combined = paragraphs + page.paragraphs
    result: list[str] = []
    seen: set[str] = set()
    for paragraph in combined:
        clean = re.sub(r"\s+", " ", paragraph).strip()
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)
    return result


def _source_name(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    for domain, name in SOURCE_NAMES.items():
        if host == domain or host.endswith("." + domain):
            return name
    if not host:
        return ""
    label = host.split(".")[0].replace("-", " ")
    return label.title() + " careers"


def _matches(text: str, pattern: str) -> bool:
    flags = 0 if ")R(" in pattern else re.IGNORECASE
    return re.search(pattern, text, flags) is not None


def _extract_vocab(text: str, vocabulary: dict[str, list[str]]) -> list[str]:
    found: list[tuple[int, int, str]] = []
    for order, (label, patterns) in enumerate(vocabulary.items()):
        positions: list[int] = []
        for pattern in patterns:
            flags = 0 if ")R(" in pattern else re.IGNORECASE
            match = re.search(pattern, text, flags)
            if match:
                positions.append(match.start())
        if positions:
            found.append((min(positions), order, label))
    return [label for _, _, label in sorted(found)]


def _name_from_value(value: Any) -> str:
    if isinstance(value, dict):
        return _plain_text(value.get("name") or value.get("legalName"))
    return _plain_text(value)


def _extract_location(job: dict[str, Any]) -> tuple[str, str]:
    locations = job.get("jobLocation")
    if locations and not isinstance(locations, list):
        locations = [locations]
    values: list[str] = []
    countries: list[str] = []
    for location in locations or []:
        if not isinstance(location, dict):
            continue
        address = location.get("address", location)
        if not isinstance(address, dict):
            continue
        country = address.get("addressCountry", "")
        if isinstance(country, dict):
            country = country.get("name", "")
        parts = [
            _plain_text(address.get("addressLocality")),
            _plain_text(address.get("addressRegion")),
            _plain_text(country),
        ]
        values.append(", ".join(part for part in parts if part))
        if country:
            countries.append(str(country))
    return "; ".join(value for value in values if value), ", ".join(countries)


def _labeled_value(paragraphs: list[str], label: str) -> str:
    pattern = re.compile(rf"^\s*{re.escape(label)}\s*[:\-]\s*(.+)$", re.I)
    for paragraph in paragraphs[:12]:
        match = pattern.match(paragraph)
        if match:
            return match.group(1).strip()
    return ""


def _fallback_title(paragraphs: list[str]) -> str:
    labeled = _labeled_value(paragraphs, "job title") or _labeled_value(paragraphs, "position")
    if labeled:
        return labeled
    role_words = re.compile(
        r"\b(?:developer|engineer|analyst|technician|programmer|tester|data scientist|"
        r"software support|graduate|intern)\b",
        re.I,
    )
    for paragraph in paragraphs[:8]:
        if len(paragraph) <= 120 and role_words.search(paragraph) and not paragraph.endswith("."):
            return paragraph
    return ""


def _fallback_location(paragraphs: list[str], text: str) -> str:
    labeled = _labeled_value(paragraphs, "location")
    if labeled:
        return labeled
    place_names = [
        "Johannesburg", "Pretoria", "Cape Town", "Durban", "Centurion", "Midrand",
        "Sandton", "Stellenbosch", "Gauteng", "Western Cape", "KwaZulu-Natal",
        "South Africa",
    ]
    found: list[tuple[int, str]] = []
    for name in place_names:
        match = re.search(rf"\b{re.escape(name)}\b", text, re.I)
        if match:
            found.append((match.start(), match.group(0)))
    values: list[str] = []
    for _, value in sorted(found):
        if value.casefold() not in {item.casefold() for item in values}:
            values.append(value)
    return ", ".join(values[:3])


def _extract_work_type(job: dict[str, Any], text: str) -> str:
    location_type = str(job.get("jobLocationType", "")).lower()
    if "telecommute" in location_type or re.search(r"\bfully remote\b|\bremote role\b", text, re.I):
        return "Remote"
    if re.search(r"\bhybrid\b", text, re.I):
        return "Hybrid"
    if re.search(r"\bon[- ]site\b|\bonsite\b|\boffice[- ]based\b", text, re.I):
        return "On-site"
    return ""


def _extract_experience(text: str) -> tuple[str, int | None]:
    patterns = [
        r"\b(\d{1,2})\s*(?:-|–|—|to)\s*(\d{1,2})\s*\+?\s*(?:years?|yrs?)\b",
        r"\b(?:minimum|min\.?|at least)\s*(?:of\s*)?(\d{1,2})\s*\+?\s*(?:years?|yrs?)\b",
        r"\b(\d{1,2})\s*\+\s*(?:years?|yrs?)\b",
        r"\b(?:up to|maximum of|max\.?)\s*(\d{1,2})\s*(?:years?|yrs?)\b",
        r"\b(\d{1,2})\s*(?:years?|yrs?)\s+(?:of\s+)?(?:relevant\s+)?experience\b",
    ]
    candidates: list[tuple[int, str, int]] = []
    for index, pattern in enumerate(patterns):
        for match in re.finditer(pattern, text, re.I):
            numbers = [int(item) for item in match.groups() if item is not None]
            if not numbers:
                continue
            maximum = max(numbers)
            if len(numbers) == 2:
                display = f"{numbers[0]}-{numbers[1]}"
            elif "+" in match.group(0) or re.search(r"minimum|at least", match.group(0), re.I):
                display = f"{numbers[0]}+"
            elif re.search(r"up to|maximum|max\.?", match.group(0), re.I):
                display = f"0-{numbers[0]}"
            else:
                display = str(numbers[0])
            candidates.append((match.start() + index, display, maximum))
    if not candidates:
        if re.search(r"\bno (?:prior |previous )?experience (?:is )?required\b", text, re.I):
            return "0", 0
        return "Not specified", None
    _, display, maximum = min(candidates, key=lambda item: item[0])
    return display, maximum


def _extract_qualification(text: str) -> str:
    degree = r"\b(?:bachelor'?s?|degree|bsc|bcom|national diploma|diploma|tertiary qualification)\b"
    required = r"\b(?:required|must|minimum|essential|mandatory)\b"
    preferred = r"\b(?:preferred|advantageous|nice to have|beneficial|desirable)\b"
    for match in re.finditer(degree, text, re.I):
        context = text[max(0, match.start() - 100): min(len(text), match.end() + 100)]
        if re.search(preferred, context, re.I):
            return "Degree preferred"
        if re.search(required, context, re.I):
            return "Degree required"
    if re.search(degree, text, re.I):
        return "Degree required"
    if re.search(r"\b(?:certificate|certification|bootcamp)\b", text, re.I):
        return "Certificate/bootcamp mentioned"
    return "No qualification specified"


def _extract_verbatim(text: str, patterns: list[str], limit: int = 8) -> list[str]:
    found: list[tuple[int, str]] = []
    seen: set[str] = set()
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            value = re.sub(r"\s+", " ", match.group(0)).strip(" ,.;:")
            key = value.casefold()
            if value and key not in seen:
                seen.add(key)
                found.append((match.start(), value))
                break
    return [value for _, value in sorted(found)[:limit]]


def _portfolio_request(text: str) -> tuple[str, str]:
    request_patterns = [
        r"\b(?:submit|share|provide|include|send)(?: a| your)? (?:link to (?:your )?)?(?:portfolio|github(?: profile| account)?|code samples?)\b",
        r"\b(?:portfolio|github profile|github account|code samples?) (?:is |are )?(?:required|requested|preferred|essential|mandatory)\b",
        r"\bapply with (?:a |your )?(?:portfolio|github)\b",
    ]
    matches = [re.search(pattern, text, re.I) for pattern in request_patterns]
    match = next((item for item in matches if item), None)
    if not match:
        return "N", "Not Mentioned"
    left = max(text.rfind(".", 0, match.start()), text.rfind("\n", 0, match.start()))
    right_candidates = [position for position in (text.find(".", match.end()), text.find("\n", match.end())) if position >= 0]
    right = min(right_candidates, default=min(len(text), match.end() + 100))
    context = text[left + 1:right]
    if re.search(r"\bpreferred|nice to have|advantageous|optional|bonus\b", context, re.I):
        return "Y", "Preferred"
    return "Y", "Required"


def _key_requirements(paragraphs: list[str], skill_labels: list[str]) -> str:
    best_score = -1
    best = ""
    requirement_words = re.compile(
        r"\brequirements?\b|\bqualifications?\b|\bskills?\b|\bexperience\b|"
        r"\bmust\b|\bpreferred\b|\bknowledge of\b|\bproficien(?:t|cy)\b",
        re.I,
    )
    for paragraph in paragraphs:
        if len(paragraph) < 40:
            continue
        low = paragraph.lower()
        score = len(requirement_words.findall(paragraph)) * 4
        score += sum(2 for label in skill_labels if label.lower().split(" (")[0] in low)
        score += min(len(paragraph) // 120, 4)
        if re.search(r"about us|equal opportunity|privacy|cookie|benefits", paragraph, re.I):
            score -= 5
        if score > best_score:
            best_score = score
            best = paragraph
    return best[:1600]


def _location_warning(location: str, country: str, text: str) -> str | None:
    combined = f"{location} {country}".lower()
    if re.search(r"\b(?:south africa|za|zaf)\b", combined):
        return None
    sa_places = (
        "johannesburg", "pretoria", "cape town", "durban", "gauteng", "western cape",
        "kwazulu-natal", "centurion", "midrand", "sandton", "stellenbosch", "south africa",
    )
    if any(place in combined or place in text.lower() for place in sa_places):
        return None
    if country:
        return f"Location appears to be outside South Africa ({country})."
    return "South African location could not be confirmed."


def extract_record(page: PageContent, track: str) -> tuple[dict[str, str], list[str]]:
    if track not in TRACK_HEADERS:
        raise ValueError("Unknown track selected.")

    job = _job_posting(page)
    paragraphs = _description_paragraphs(job, page)
    body_text = "\n".join(paragraphs) or page.text
    combined_text = "\n".join(
        value for value in [_plain_text(job.get("title")), body_text] if value
    )

    title = _plain_text(job.get("title"))
    if not title:
        title = page.metadata.get("h1") or page.metadata.get("og:title") or _fallback_title(paragraphs)
    company = _name_from_value(job.get("hiringOrganization"))
    if not company:
        company = page.metadata.get("og:site_name", "") or _labeled_value(paragraphs, "company")
    location, country = _extract_location(job)
    if not location:
        location = _fallback_location(paragraphs, body_text)
    date_posted = _plain_text(job.get("datePosted"))[:10]
    work_type = _extract_work_type(job, combined_text)
    experience, max_experience = _extract_experience(combined_text)
    qualification = _extract_qualification(combined_text)
    portfolio, requirement_level = _portfolio_request(combined_text)
    soft_skills = _extract_verbatim(combined_text, SOFT_SKILL_PATTERNS)
    readiness = _extract_verbatim(combined_text, READINESS_PATTERNS)

    record = {header: "" for header in TRACK_HEADERS[track]}
    record.update(
        {
            "Post ID": "Generated when saved",
            "Job Title (as written)": title,
            "Company Name": company,
            "Location": location,
            "Work Type": work_type,
            "Source / Job Board": _source_name(page.final_url or page.url),
            "Job Post URL": page.final_url or page.url,
            "Date Posted": date_posted,
            "Date Collected": date.today().isoformat(),
            "Experience Required (years)": experience,
            "Qualification Required": qualification,
            "Portfolio/GitHub Requested (Y/N)": portfolio,
            "Requirement Level (Required/Preferred/Not Mentioned)": requirement_level,
            "Soft Skills Mentioned (verbatim)": ", ".join(soft_skills),
            "Specific Readiness Signals (verbatim, beyond generic buzzwords)": ", ".join(readiness),
        }
    )

    warnings: list[str] = []
    if track == "SE Track":
        languages = _extract_vocab(combined_text, SE_LANGUAGES)
        frameworks = _extract_vocab(combined_text, SE_FRAMEWORKS)
        tools = _extract_vocab(combined_text, SE_TOOLS)
        record["Programming Languages Mentioned"] = ", ".join(languages)
        record["Frameworks/Libraries Mentioned"] = ", ".join(frameworks)
        record["Git/GitHub Explicitly Named (Y/N)"] = (
            "Y" if re.search(r"\bgit(?:hub)?\b", combined_text, re.I) else "N"
        )
        record["Tools & Platforms Mentioned"] = ", ".join(tools)
        skills = languages + frameworks + tools
        if frameworks and not languages:
            warnings.append("Frameworks were found but no programming language was explicitly named.")
    else:
        core = _extract_vocab(combined_text, DA_CORE)
        reporting = _extract_vocab(combined_text, DA_REPORTING)
        tools = _extract_vocab(combined_text, DA_TOOLS)
        record["Core Analytical Skills Mentioned"] = ", ".join(core)
        record["Reporting/Visualization Tools Mentioned"] = ", ".join(reporting)
        record["SQL Explicitly Named (Y/N)"] = "Y" if re.search(r"\bsql\b", combined_text, re.I) else "N"
        record["Tools & Platforms Mentioned"] = ", ".join(tools)
        skills = core + reporting + tools
        libraries = {"pandas", "NumPy", "matplotlib", "seaborn"}.intersection(tools)
        if libraries and "Python" not in core:
            warnings.append("Python libraries were found but Python was not explicitly named.")

    record["Key Requirements Paragraph (paste)"] = _key_requirements(paragraphs, skills)

    location_warning = _location_warning(location, country, combined_text)
    if location_warning:
        warnings.append(location_warning)
    if max_experience is not None and max_experience >= 5:
        warnings.append(f"Experience requirement appears to be {experience}; the collection excludes 5+ year roles.")
    if re.search(r"\b(?:senior|lead|principal|staff)\b", title, re.I):
        warnings.append("The title appears senior and may fall outside the collection rules.")
    if len(combined_text.split()) < 100:
        warnings.append("Very little requirement text was extracted; check the page or use the paste fallback.")
    for label, value in (
        ("job title", title),
        ("company", company),
        ("location", location),
        ("work type", work_type),
        ("date posted", date_posted),
        ("key requirements paragraph", record["Key Requirements Paragraph (paste)"]),
    ):
        if not value:
            warnings.append(f"Could not determine {label}; fill it in manually.")

    record["Notes / Anything Unusual"] = " | ".join(warnings)
    return record, warnings

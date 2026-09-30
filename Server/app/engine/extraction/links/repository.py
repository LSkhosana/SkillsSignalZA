"""Public GitHub and GitLab repository evidence for candidate-submitted links.

Only official API and raw-content hosts are requested. Ownership becomes
`attributed` when the candidate-declared handle matches the API owner login.
A mismatch or a missing handle stays `unclear`.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlsplit

from app.engine.extraction.links.html import extract_plain_blocks
from app.engine.extraction.links.http import (
    RetrievalError,
    content_type_of,
    decode_body,
    retrieve_validated_resource,
)
from app.engine.extraction.links.outcomes import (
    completed_link_outcome,
    link_metadata,
    link_source_record,
)

_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}$")
_ALLOWED_HOSTS = frozenset({"api.github.com", "raw.githubusercontent.com", "gitlab.com"})
_README_TYPES = frozenset(
    {
        "text/plain",
        "text/markdown",
        "text/html",
        "application/octet-stream",
        "application/json",
    }
)
_JSON_ACCEPT = "application/json"
_TEXT_ACCEPT = "text/plain"


@dataclass(frozen=True)
class PublicRepository:
    """One public GitHub or GitLab repository named by a submitted URL."""

    host: str
    owner: str
    name: str


def parse_public_repository(normalized_url: str) -> PublicRepository | None:
    """Return owner/name when the URL is a public GitHub or GitLab repository."""
    parts = urlsplit(normalized_url)
    hostname = (parts.hostname or "").removeprefix("www.")
    segments = [segment for segment in parts.path.split("/") if segment]
    if len(segments) < 2:
        return None
    owner = segments[0]
    name = segments[1].removesuffix(".git")
    if not _SEGMENT_RE.fullmatch(owner) or not _SEGMENT_RE.fullmatch(name):
        return None
    if hostname == "github.com":
        return PublicRepository("github", owner, name)
    if hostname == "gitlab.com":
        return PublicRepository("gitlab", owner, name)
    return None


def retrieve_public_repository(
    repo: PublicRepository,
    *,
    link_id: str,
    declared_type: str,
    submitted_url: str,
    normalized_url: str,
    retrieved_at: str,
    profile_handle: str,
) -> dict[str, Any] | None:
    """Retrieve README and repository facts, or None when the host API is unavailable."""
    metadata = _metadata(repo)
    if metadata is None:
        return None
    login = _owner_login(repo, metadata)
    if login is None:
        return None
    branch = _default_branch(metadata)
    languages = _languages(repo)
    commit_count = _commit_count(repo)
    readme = _readme(repo, branch)
    summary = _summary(login, languages, commit_count)
    blocks = extract_plain_blocks(readme or "")
    if summary:
        blocks.append(
            {
                "block_id": f"blk-text-{len(blocks) + 1:04d}",
                "locator": "repository:summary",
                "text": summary,
            }
        )
    if not blocks:
        return None
    assessed = (readme or "").encode("utf-8") + b"\n" + summary.encode("utf-8")
    digest = hashlib.sha256(assessed).hexdigest()
    ownership = "attributed" if _handles_match(profile_handle, login) else "unclear"
    link = link_metadata(
        link_id=link_id,
        submitted_url=submitted_url,
        declared_type=declared_type,
        normalized_url=normalized_url,
        final_url=_readme_url(repo, branch) if readme else _metadata_url(repo),
        verified_content_type="text/markdown" if readme else "application/json",
        http_status=200,
        byte_size=len(assessed),
        sha256=digest,
    )
    record = link_source_record(
        link_id=link_id,
        declared_type=declared_type,
        submitted_url=submitted_url,
        retrieved_at=retrieved_at,
        access_status="accessible",
        content_hash=digest,
        ownership_status=ownership,
        notes="Public repository metadata and README retrieved for the submitted repository URL.",
    )
    return completed_link_outcome(link=link, source_record=record, content_blocks=blocks)


def _handles_match(profile_handle: str, login: str) -> bool:
    handle = profile_handle.strip()
    return bool(handle) and handle.casefold() == login.strip().casefold()


def _metadata(repo: PublicRepository) -> dict[str, Any] | None:
    payload = _get_json(_metadata_url(repo))
    if not isinstance(payload, dict):
        return None
    return payload


def _text_field(record: object, key: str) -> str | None:
    if not isinstance(record, dict):
        return None
    value = record.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _owner_login(repo: PublicRepository, metadata: dict[str, Any]) -> str | None:
    if repo.host == "github":
        return _text_field(metadata.get("owner"), "login")
    return _text_field(metadata.get("owner"), "username") or _text_field(
        metadata.get("namespace"), "path"
    )


def _default_branch(metadata: dict[str, Any]) -> str:
    branch = metadata.get("default_branch")
    if isinstance(branch, str) and _SEGMENT_RE.fullmatch(branch):
        return branch
    return "main"


def _languages(repo: PublicRepository) -> list[str]:
    payload = _get_json(_languages_url(repo))
    if not isinstance(payload, dict):
        return []
    names = [str(name) for name in payload if isinstance(name, str) and name.strip()]
    return sorted(names)


def _commit_count(repo: PublicRepository) -> int | None:
    payload = _get_json(_commits_url(repo))
    if not isinstance(payload, list):
        return None
    return len(payload)


def _readme(repo: PublicRepository, branch: str) -> str | None:
    for name in ("README.md", "README"):
        text = _get_text(_readme_url(repo, branch, name))
        if text and text.strip():
            return text
    return None


def _summary(login: str, languages: list[str], commit_count: int | None) -> str:
    parts = [f"Repository owner {login}."]
    if languages:
        parts.append("Languages detected: " + ", ".join(languages) + ".")
    if commit_count is not None:
        parts.append(f"Recent commit sample: {commit_count}.")
    return " ".join(parts)


def _metadata_url(repo: PublicRepository) -> str:
    if repo.host == "github":
        return f"https://api.github.com/repos/{quote(repo.owner)}/{quote(repo.name)}"
    project = quote(f"{repo.owner}/{repo.name}", safe="")
    return f"https://gitlab.com/api/v4/projects/{project}"


def _languages_url(repo: PublicRepository) -> str:
    if repo.host == "github":
        return f"{_metadata_url(repo)}/languages"
    return f"{_metadata_url(repo)}/languages"


def _commits_url(repo: PublicRepository) -> str:
    if repo.host == "github":
        return f"{_metadata_url(repo)}/commits?per_page=5"
    return f"{_metadata_url(repo)}/repository/commits?per_page=5"


def _readme_url(repo: PublicRepository, branch: str, name: str = "README.md") -> str:
    if repo.host == "github":
        return (
            f"https://raw.githubusercontent.com/{quote(repo.owner)}/{quote(repo.name)}/"
            f"{quote(branch)}/{quote(name)}"
        )
    return (
        f"https://gitlab.com/{quote(repo.owner)}/{quote(repo.name)}/-/raw/"
        f"{quote(branch)}/{quote(name)}"
    )


def _get_json(url: str) -> Any | None:
    response = _fetch(url, accept=_JSON_ACCEPT)
    if response is None:
        return None
    try:
        return json.loads(decode_body(response.content, response.headers))
    except json.JSONDecodeError:
        return None


def _get_text(url: str) -> str | None:
    response = _fetch(url, accept=_TEXT_ACCEPT)
    if response is None:
        return None
    media = content_type_of(response.headers)
    if media is not None and media not in _README_TYPES and not media.startswith("text/"):
        return None
    return decode_body(response.content, response.headers)


def _fetch(url: str, *, accept: str) -> Any | None:
    hostname = urlsplit(url).hostname
    if hostname not in _ALLOWED_HOSTS:
        return None
    try:
        response = retrieve_validated_resource(url, accept=accept)
    except RetrievalError:
        return None
    if response.status_code != 200 or not response.content:
        return None
    return response

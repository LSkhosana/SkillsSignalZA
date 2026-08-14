"""Retrieve and clean a single public job-post page without paid services."""

from __future__ import annotations

import html
import ipaddress
import json
import re
import socket
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


MAX_DOWNLOAD_BYTES = 5 * 1024 * 1024


class FetchError(RuntimeError):
    """Raised when a page cannot safely be retrieved or read."""


@dataclass
class PageContent:
    url: str
    final_url: str
    text: str
    paragraphs: list[str]
    json_ld: list[Any] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)


def _validate_public_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise FetchError("Enter a complete http:// or https:// job-post URL.")
    if parsed.username or parsed.password:
        raise FetchError("URLs containing usernames or passwords are not supported.")
    try:
        default_port = 443 if parsed.scheme == "https" else 80
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or default_port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise FetchError("The job-post domain could not be found.") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise FetchError("Local and private-network URLs are not allowed.")
    return parsed.geturl()


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _JobHTMLParser(HTMLParser):
    BLOCK_TAGS = {
        "p", "div", "li", "br", "section", "article", "h1", "h2", "h3", "h4", "tr"
    }
    SKIP_TAGS = {"script", "style", "svg", "nav", "header", "footer", "form", "noscript"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._in_json_ld = False
        self._json_buffer: list[str] = []
        self._paragraph_buffer: list[str] = []
        self.paragraphs: list[str] = []
        self.json_ld: list[Any] = []
        self.metadata: dict[str, str] = {}
        self.h1 = ""
        self._in_h1 = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attr = {k.lower(): (v or "") for k, v in attrs}
        if tag == "script" and "ld+json" in attr.get("type", "").lower():
            self._in_json_ld = True
            self._json_buffer = []
            return
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag == "meta":
            key = (attr.get("property") or attr.get("name") or "").lower()
            value = attr.get("content", "").strip()
            if key and value:
                self.metadata[key] = value
        if tag == "h1":
            self._in_h1 = True
        if tag in self.BLOCK_TAGS:
            self._flush_paragraph()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._in_json_ld and tag == "script":
            raw = "".join(self._json_buffer).strip()
            if raw:
                try:
                    self.json_ld.append(json.loads(raw))
                except json.JSONDecodeError:
                    pass
            self._in_json_ld = False
            self._json_buffer = []
            return
        if tag in self.SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag == "h1":
            self._in_h1 = False
        if tag in self.BLOCK_TAGS:
            self._flush_paragraph()

    def handle_data(self, data: str) -> None:
        if self._in_json_ld:
            self._json_buffer.append(data)
            return
        if self._skip_depth:
            return
        clean = re.sub(r"\s+", " ", html.unescape(data)).strip()
        if not clean:
            return
        self._paragraph_buffer.append(clean)
        if self._in_h1 and not self.h1:
            self.h1 = clean

    def close(self) -> None:
        super().close()
        self._flush_paragraph()
        if self.h1:
            self.metadata.setdefault("h1", self.h1)

    def _flush_paragraph(self) -> None:
        if not self._paragraph_buffer:
            return
        value = re.sub(r"\s+", " ", " ".join(self._paragraph_buffer)).strip()
        self._paragraph_buffer = []
        if len(value) >= 2 and (not self.paragraphs or value != self.paragraphs[-1]):
            self.paragraphs.append(value)


def parse_html(url: str, raw_html: str, final_url: str | None = None) -> PageContent:
    parser = _JobHTMLParser()
    parser.feed(raw_html)
    parser.close()
    paragraphs = [p for p in parser.paragraphs if not _looks_like_page_chrome(p)]
    return PageContent(
        url=url,
        final_url=final_url or url,
        text="\n".join(paragraphs),
        paragraphs=paragraphs,
        json_ld=parser.json_ld,
        metadata=parser.metadata,
    )


def _looks_like_page_chrome(value: str) -> bool:
    low = value.lower().strip()
    chrome = {
        "sign in", "log in", "register", "accept cookies", "privacy policy",
        "terms of use", "skip to main content", "share", "save job", "apply now",
    }
    return low in chrome or (len(low) < 40 and low.startswith("cookie settings"))


def fetch_job_page(url: str, timeout: int = 15) -> PageContent:
    safe_url = _validate_public_url(url)
    request = Request(
        safe_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/126.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-ZA,en;q=0.9",
        },
    )
    try:
        opener = build_opener(_SafeRedirectHandler())
        with opener.open(request, timeout=timeout) as response:
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                raise FetchError(f"The URL returned {content_type}, not a web page.")
            body = response.read(MAX_DOWNLOAD_BYTES + 1)
            if len(body) > MAX_DOWNLOAD_BYTES:
                raise FetchError("The page is too large to process safely.")
            charset = response.headers.get_content_charset() or "utf-8"
            raw_html = body.decode(charset, errors="replace")
            final_url = response.geturl()
    except HTTPError as exc:
        if exc.code in {401, 403, 429}:
            raise FetchError(
                "This job board blocked automatic retrieval. Paste the job text below instead."
            ) from exc
        raise FetchError(f"The job page returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise FetchError("The job page could not be retrieved. Paste the job text below instead.") from exc

    page = parse_html(safe_url, raw_html, final_url)
    if len(page.text.split()) < 60 and not page.json_ld:
        raise FetchError(
            "Too little job content was visible on this page. Paste the full job text below instead."
        )
    return page


def page_from_manual_text(url: str, manual_text: str) -> PageContent:
    paragraphs = [
        re.sub(r"\s+", " ", part).strip()
        for part in re.split(
            r"\n\s*\n|^\s*[•●▪*-]\s+", manual_text, flags=re.MULTILINE
        )
    ]
    paragraphs = [p for p in paragraphs if p]
    if not paragraphs:
        paragraphs = [re.sub(r"\s+", " ", manual_text).strip()]
    return PageContent(
        url=url,
        final_url=url,
        text="\n".join(paragraphs),
        paragraphs=paragraphs,
    )

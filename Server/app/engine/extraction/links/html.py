"""Deterministic visible-text extraction for retrieved link bodies."""

from __future__ import annotations

from html.parser import HTMLParser

from app.engine.extraction.text import normalize_extracted_text

_SKIP_TAGS = frozenset(
    {"script", "style", "noscript", "template", "iframe", "object", "embed", "head"}
)
_BLOCK_TAGS = frozenset(
    {
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "p",
        "li",
        "pre",
        "blockquote",
        "td",
        "th",
        "dt",
        "dd",
        "figcaption",
    }
)


def extract_visible_blocks(content_type: str, body: str) -> list[dict[str, str]]:
    """Return ordered non-empty visible-text blocks for a supported body."""
    if content_type in {"text/html", "application/xhtml+xml"}:
        return extract_html_blocks(body)
    return extract_plain_blocks(body)


def extract_html_blocks(markup: str) -> list[dict[str, str]]:
    """Extract visible HTML blocks in document order with stable locators."""
    parser = _VisibleHTMLParser()
    parser.feed(markup)
    parser.close()
    return parser.blocks


def extract_plain_blocks(body: str) -> list[dict[str, str]]:
    """Extract plain-text or Markdown paragraphs with stable locators."""
    text = body.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    paragraphs = [
        normalize_extracted_text(part).replace("\n", " ") for part in _split_paragraphs(text)
    ]
    blocks: list[dict[str, str]] = []
    ordinal = 0
    for paragraph in paragraphs:
        if not paragraph:
            continue
        ordinal += 1
        blocks.append(
            {
                "block_id": f"blk-text-{ordinal:04d}",
                "locator": f"text:p:{ordinal}",
                "text": paragraph,
            }
        )
    return blocks


def _split_paragraphs(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    for line in text.split("\n"):
        if line.strip():
            current.append(line)
            continue
        if current:
            parts.append("\n".join(current))
            current = []
    if current:
        parts.append("\n".join(current))
    return parts


class _VisibleHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[dict[str, str]] = []
        self._skip_depth = 0
        self._stack: list[tuple[str, list[str]]] = []
        self._counts: dict[str, int] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        if name in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if name == "br" and self._stack:
            self._stack[-1][1].append("\n")
            return
        if name in _BLOCK_TAGS:
            self._stack.append((name, []))

    def handle_endtag(self, tag: str) -> None:
        name = tag.lower()
        if name in _SKIP_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth or name not in _BLOCK_TAGS:
            return
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index][0] != name:
                continue
            _, parts = self._stack.pop(index)
            text = normalize_extracted_text(" ".join(parts))
            if text:
                ordinal = self._counts.get(name, 0) + 1
                self._counts[name] = ordinal
                self.blocks.append(
                    {
                        "block_id": f"blk-html-{name}-{ordinal:04d}",
                        "locator": f"html:{name}:{ordinal}",
                        "text": text.replace("\n", " "),
                    }
                )
            break

    def handle_data(self, data: str) -> None:
        if self._skip_depth or not self._stack:
            return
        self._stack[-1][1].append(data)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "br" and self._stack and not self._skip_depth:
            self._stack[-1][1].append("\n")

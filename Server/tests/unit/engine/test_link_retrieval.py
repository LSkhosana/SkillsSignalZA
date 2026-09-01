"""Package G safe candidate-submitted link retrieval tests."""

from __future__ import annotations

import ast
import hashlib
import json
from importlib.resources import files
from ipaddress import ip_address
from pathlib import Path
from typing import Any

import httpx
import pytest
from jsonschema import Draft202012Validator

from app.engine.configuration import load_json
from app.engine.extraction import normalize_submitted_url, retrieve_candidate_link
from app.engine.extraction.links.html import extract_html_blocks, extract_plain_blocks
from app.engine.extraction.links.http import (
    HopResponse,
    PinnedHop,
    RetrievalError,
    _read_capped_body,
    build_httpx_client,
    content_type_of,
    decode_body,
    is_unsafe_ip,
    resolve_hostname,
    validate_hop,
)
from app.engine.extraction.links.http import (
    send_pinned_get as original_send_pinned_get,
)
from app.engine.extraction.links.outcomes import (
    CONNECT_TIMEOUT_SECONDS,
    ERROR_CONNECT_FAILURE,
    ERROR_DNS_RESOLUTION_FAILED,
    ERROR_ENVELOPE_INVALID,
    ERROR_HTTP_CLIENT_ERROR,
    ERROR_HTTP_SERVER_ERROR,
    ERROR_MALFORMED_URL,
    ERROR_NO_EXTRACTABLE_TEXT,
    ERROR_PARSER_EXCEPTION,
    ERROR_REDIRECT_LIMIT_EXCEEDED,
    ERROR_RESPONSE_TOO_LARGE,
    ERROR_TIMEOUT,
    ERROR_TLS_FAILURE,
    ERROR_UNSAFE_HOST,
    ERROR_UNSAFE_REDIRECT,
    ERROR_UNSUPPORTED_CONTENT_TYPE,
    ERROR_UNSUPPORTED_SCHEME,
    ERROR_URL_CREDENTIALS,
    LINK_EXTRACTOR_VERSION,
    MAX_CONTENT_BLOCKS,
    MAX_REDIRECTS,
    MAX_RESPONSE_BODY_BYTES,
    MAX_URL_LENGTH,
    READ_TIMEOUT_SECONDS,
)

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "app" / "schemas" / "link_retrieval.schema.json"
LINKS_DIR = Path(__file__).resolve().parents[3] / "app" / "engine" / "extraction" / "links"
SAFE_IP = "8.8.8.8"
RETRIEVED_AT = "2026-09-01T11:00:00Z"
SECRET = "C:\\secret\\path traceback must not leak"
HTML_BODY = (
    b"<html><head><title>Ignored</title><style>body{color:red}</style>"
    b"<script>const secret='nope';</script></head><body>"
    b"<h1>Project Title</h1><p>Built a Flask API</p>"
    b"<ul><li>Python</li></ul><pre>print(1)</pre>"
    b"</body></html>"
)


def _validator() -> Draft202012Validator:
    return Draft202012Validator(
        load_json(SCHEMA_PATH),
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )


def _assert_safe(outcome: dict[str, Any]) -> None:
    _validator().validate(outcome)
    serialized = json.dumps(outcome)
    assert "assessment_result" not in outcome
    assert "evidence_facts" not in outcome
    assert "traceback" not in serialized.lower()
    assert SECRET not in serialized
    assert "RuntimeError" not in serialized
    assert "8.8.8.8" not in serialized


def _retrieve(**overrides: Any) -> dict[str, Any]:
    payload = {
        "submitted_url": "https://Example.COM/project",
        "link_id": "link-01",
        "declared_type": "project",
        "retrieved_at": RETRIEVED_AT,
    }
    payload.update(overrides)
    return retrieve_candidate_link(payload.pop("submitted_url"), **payload)


def _ok_html(url: str = "https://example.com/project", body: bytes = HTML_BODY) -> HopResponse:
    return HopResponse(
        status_code=200,
        headers={"content-type": "text/html; charset=utf-8"},
        content=body,
        url=url,
    )


@pytest.fixture(autouse=True)
def block_real_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def dns_blocked(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("real DNS is not allowed")

    def send_blocked(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("real HTTP is not allowed")

    monkeypatch.setattr("app.engine.extraction.links.http.socket.getaddrinfo", dns_blocked)
    monkeypatch.setattr("app.engine.extraction.links.http.send_pinned_get", send_blocked)


@pytest.fixture
def allow_safe_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.engine.extraction.links.http.resolve_hostname",
        lambda hostname, port: [SAFE_IP],
    )


def test_schema_is_packaged_and_valid() -> None:
    packaged = files("app.schemas").joinpath("link_retrieval.schema.json")
    assert packaged.is_file()
    schema = json.loads(packaged.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)


def test_url_normalization_is_deterministic_and_preserves_query_order() -> None:
    raw = "  HTTPS://Bücher.Example.COM:443/Path/Name?b=2&a=1#frag  "
    normalized = normalize_submitted_url(raw)
    assert normalized == "https://xn--bcher-kva.example.com/Path/Name?b=2&a=1"
    assert normalize_submitted_url(raw) == normalized
    assert normalize_submitted_url("http://Example.COM:80/a") == "http://example.com/a"


def test_successful_html_retrieval_matches_contract_source_record(
    monkeypatch: pytest.MonkeyPatch,
    allow_safe_dns: None,
) -> None:
    submitted = "https://Example.COM/project"
    monkeypatch.setattr(
        "app.engine.extraction.links.http.send_pinned_get",
        lambda hop: _ok_html(hop.url),
    )
    outcome = _retrieve(submitted_url=submitted)
    _assert_safe(outcome)
    record = outcome["source_record"]
    assert outcome["state"] == "COMPLETED"
    assert record["source_id"] == "src-link-01"
    assert record["locator"] == submitted
    assert record["source_type"] == "project"
    assert record["submitted_by_candidate"] is True
    assert record["access_status"] == "accessible"
    assert record["ownership_status"] == "unclear"
    assert record["extractor_version"] == LINK_EXTRACTOR_VERSION
    assert outcome["link"]["submitted_url"] == submitted
    assert outcome["link"]["normalized_url"] == "https://example.com/project"


def test_response_body_sha256_is_exact(
    monkeypatch: pytest.MonkeyPatch, allow_safe_dns: None
) -> None:
    monkeypatch.setattr(
        "app.engine.extraction.links.http.send_pinned_get",
        lambda hop: _ok_html(hop.url),
    )
    outcome = _retrieve()
    assert outcome["link"]["sha256"] == hashlib.sha256(HTML_BODY).hexdigest()
    assert outcome["source_record"]["content_hash"] == outcome["link"]["sha256"]


def test_html_visible_blocks_preserve_order_and_exclude_non_visible_content() -> None:
    blocks = extract_html_blocks(HTML_BODY.decode("utf-8"))
    assert [block["locator"] for block in blocks] == [
        "html:h1:1",
        "html:p:1",
        "html:li:1",
        "html:pre:1",
    ]
    assert [block["text"] for block in blocks] == [
        "Project Title",
        "Built a Flask API",
        "Python",
        "print(1)",
    ]
    serialized = json.dumps(blocks)
    assert "nope" not in serialized
    assert "color:red" not in serialized
    assert "Ignored" not in serialized


def test_plain_text_and_markdown_preserve_paragraph_order() -> None:
    body = "First paragraph.\nStill first.\n\nSecond paragraph."
    blocks = extract_plain_blocks(body)
    assert [block["locator"] for block in blocks] == ["text:p:1", "text:p:2"]
    assert blocks[0]["text"] == "First paragraph. Still first."
    assert blocks[1]["text"] == "Second paragraph."


def test_repeated_mocked_retrievals_are_byte_equivalent(
    monkeypatch: pytest.MonkeyPatch,
    allow_safe_dns: None,
) -> None:
    monkeypatch.setattr(
        "app.engine.extraction.links.http.send_pinned_get",
        lambda hop: _ok_html(hop.url),
    )
    first = _retrieve()
    second = _retrieve()
    assert json.dumps(first, sort_keys=True, separators=(",", ":")) == json.dumps(
        second, sort_keys=True, separators=(",", ":")
    )


@pytest.mark.parametrize(
    ("url", "error_code"),
    [
        ("ftp://example.com/path", ERROR_UNSUPPORTED_SCHEME),
        ("https://user:pass@example.com/path", ERROR_URL_CREDENTIALS),
        ("https://127.0.0.1/path", ERROR_UNSAFE_HOST),
        ("https://[::1]/path", ERROR_UNSAFE_HOST),
        ("https://example.com:8080/path", ERROR_UNSAFE_HOST),
        ("not a url", ERROR_MALFORMED_URL),
    ],
)
def test_unsafe_urls_fail_before_http(
    url: str,
    error_code: str,
    monkeypatch: pytest.MonkeyPatch,
    allow_safe_dns: None,
) -> None:
    outcome = _retrieve(submitted_url=url)
    _assert_safe(outcome)
    assert outcome["state"] == "LINK_RETRIEVAL_FAILED"
    assert outcome["error_code"] == error_code
    assert outcome["content_blocks"] == []


def test_private_and_link_local_resolutions_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for address in ("127.0.0.1", "10.0.0.1", "192.168.1.1", "169.254.1.1", "::1", "fc00::1"):
        monkeypatch.setattr(
            "app.engine.extraction.links.http.resolve_hostname",
            lambda hostname, port, ip=address: [ip],
        )
        outcome = _retrieve()
        _assert_safe(outcome)
        assert outcome["error_code"] == ERROR_UNSAFE_HOST
        assert is_unsafe_ip(address) is True


def test_any_blocked_address_fails_the_hop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.engine.extraction.links.http.resolve_hostname",
        lambda hostname, port: [SAFE_IP, "10.0.0.5"],
    )
    outcome = _retrieve()
    assert outcome["error_code"] == ERROR_UNSAFE_HOST


def test_redirects_are_revalidated_and_https_downgrade_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    allow_safe_dns: None,
) -> None:
    responses = [
        HopResponse(
            status_code=302,
            headers={"location": "http://example.com/downgrade"},
            content=b"",
            url="https://example.com/project",
        )
    ]

    def fake_send(hop: PinnedHop) -> HopResponse:
        assert hop.pinned_ip == SAFE_IP
        return responses.pop(0)

    monkeypatch.setattr("app.engine.extraction.links.http.send_pinned_get", fake_send)
    outcome = _retrieve()
    _assert_safe(outcome)
    assert outcome["error_code"] == ERROR_UNSAFE_REDIRECT


def test_unsafe_redirect_target_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    allow_safe_dns: None,
) -> None:
    monkeypatch.setattr(
        "app.engine.extraction.links.http.send_pinned_get",
        lambda hop: HopResponse(
            status_code=302,
            headers={"location": "https://127.0.0.1/internal"},
            content=b"",
            url=hop.url,
        ),
    )
    outcome = _retrieve()
    assert outcome["error_code"] == ERROR_UNSAFE_HOST


def test_redirect_count_is_capped(
    monkeypatch: pytest.MonkeyPatch,
    allow_safe_dns: None,
) -> None:
    def fake_send(hop: PinnedHop) -> HopResponse:
        return HopResponse(
            status_code=302,
            headers={"location": "https://example.com/next"},
            content=b"",
            url=hop.url,
        )

    monkeypatch.setattr("app.engine.extraction.links.http.send_pinned_get", fake_send)
    outcome = _retrieve()
    _assert_safe(outcome)
    assert outcome["error_code"] == ERROR_REDIRECT_LIMIT_EXCEEDED
    assert MAX_REDIRECTS == 5


def test_successful_redirect_chain(
    monkeypatch: pytest.MonkeyPatch,
    allow_safe_dns: None,
) -> None:
    hops: list[str] = []

    def fake_send(hop: PinnedHop) -> HopResponse:
        hops.append(hop.url)
        if hop.url.endswith("/project"):
            return HopResponse(
                status_code=302,
                headers={"location": "https://example.com/final"},
                content=b"",
                url=hop.url,
            )
        return _ok_html(hop.url)

    monkeypatch.setattr("app.engine.extraction.links.http.send_pinned_get", fake_send)
    outcome = _retrieve()
    _assert_safe(outcome)
    assert outcome["state"] == "COMPLETED"
    assert hops == ["https://example.com/project", "https://example.com/final"]
    assert outcome["link"]["final_url"] == "https://example.com/final"


def test_dns_timeout_tls_and_http_errors(
    monkeypatch: pytest.MonkeyPatch,
    allow_safe_dns: None,
) -> None:
    monkeypatch.setattr(
        "app.engine.extraction.links.http.resolve_hostname",
        lambda hostname, port: (_ for _ in ()).throw(RetrievalError(ERROR_DNS_RESOLUTION_FAILED)),
    )
    dns_outcome = _retrieve()
    assert dns_outcome["error_code"] == ERROR_DNS_RESOLUTION_FAILED
    assert dns_outcome["source_record"]["access_status"] == "inaccessible"

    monkeypatch.setattr(
        "app.engine.extraction.links.http.resolve_hostname",
        lambda hostname, port: [SAFE_IP],
    )
    cases = [
        (ERROR_TIMEOUT, ERROR_TIMEOUT),
        (ERROR_TLS_FAILURE, ERROR_TLS_FAILURE),
        (ERROR_CONNECT_FAILURE, ERROR_CONNECT_FAILURE),
    ]
    for raised, expected in cases:
        monkeypatch.setattr(
            "app.engine.extraction.links.http.send_pinned_get",
            lambda hop, code=raised: (_ for _ in ()).throw(RetrievalError(code)),
        )
        outcome = _retrieve()
        _assert_safe(outcome)
        assert outcome["error_code"] == expected

    monkeypatch.setattr(
        "app.engine.extraction.links.http.send_pinned_get",
        lambda hop: HopResponse(404, {"content-type": "text/plain"}, b"", hop.url),
    )
    assert _retrieve()["error_code"] == ERROR_HTTP_CLIENT_ERROR
    monkeypatch.setattr(
        "app.engine.extraction.links.http.send_pinned_get",
        lambda hop: HopResponse(502, {"content-type": "text/plain"}, b"", hop.url),
    )
    assert _retrieve()["error_code"] == ERROR_HTTP_SERVER_ERROR


def test_unsupported_content_type_and_missing_content_length_cap(
    monkeypatch: pytest.MonkeyPatch,
    allow_safe_dns: None,
) -> None:
    monkeypatch.setattr(
        "app.engine.extraction.links.http.send_pinned_get",
        lambda hop: HopResponse(200, {"content-type": "application/pdf"}, b"%PDF", hop.url),
    )
    outcome = _retrieve()
    _assert_safe(outcome)
    assert outcome["error_code"] == ERROR_UNSUPPORTED_CONTENT_TYPE
    assert outcome["source_record"]["access_status"] == "unsupported"

    class _Stream:
        headers: dict[str, str] = {}

        def iter_bytes(self) -> Any:
            yield b"x" * 20

    monkeypatch.setattr("app.engine.extraction.links.http.MAX_RESPONSE_BODY_BYTES", 8)
    with pytest.raises(RetrievalError) as exc:
        _read_capped_body(_Stream())  # type: ignore[arg-type]
    assert exc.value.error_code == ERROR_RESPONSE_TOO_LARGE


def test_content_length_header_is_not_trusted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Stream:
        headers = {"content-length": "4"}

        def iter_bytes(self) -> Any:
            yield b"x" * 50

    monkeypatch.setattr("app.engine.extraction.links.http.MAX_RESPONSE_BODY_BYTES", 8)
    with pytest.raises(RetrievalError) as exc:
        _read_capped_body(_Stream())  # type: ignore[arg-type]
    assert exc.value.error_code == ERROR_RESPONSE_TOO_LARGE


def test_parser_exceptions_do_not_leak(
    monkeypatch: pytest.MonkeyPatch, allow_safe_dns: None
) -> None:
    def boom(_hop: PinnedHop) -> HopResponse:
        raise RuntimeError(f"{SECRET} Built a Flask API nslookup 10.0.0.1")

    monkeypatch.setattr("app.engine.extraction.links.http.send_pinned_get", boom)
    outcome = _retrieve()
    _assert_safe(outcome)
    assert outcome["error_code"] == ERROR_PARSER_EXCEPTION
    assert "Built a Flask API" not in json.dumps(outcome)
    assert "nslookup" not in json.dumps(outcome)


def test_production_client_disables_proxy_inheritance() -> None:
    client = build_httpx_client(transport=httpx.MockTransport(lambda request: httpx.Response(200)))
    assert client.trust_env is False
    client.close()


def test_named_limits() -> None:
    assert MAX_URL_LENGTH == 2048
    assert MAX_REDIRECTS == 5
    assert CONNECT_TIMEOUT_SECONDS == 3.0
    assert READ_TIMEOUT_SECONDS == 10.0
    assert MAX_RESPONSE_BODY_BYTES == 2 * 1024 * 1024
    assert MAX_CONTENT_BLOCKS == 5000
    assert LINK_EXTRACTOR_VERSION == "extract.link.v1"


def test_javascript_only_html_fails_without_text(
    monkeypatch: pytest.MonkeyPatch,
    allow_safe_dns: None,
) -> None:
    body = (
        b"<html><body><script>window.location='https://x';</script>"
        b"<div id='app'></div></body></html>"
    )
    monkeypatch.setattr(
        "app.engine.extraction.links.http.send_pinned_get",
        lambda hop: HopResponse(200, {"content-type": "text/html"}, body, hop.url),
    )
    outcome = _retrieve()
    _assert_safe(outcome)
    assert outcome["error_code"] == ERROR_NO_EXTRACTABLE_TEXT
    assert outcome["source_record"]["access_status"] == "accessible"
    assert outcome["source_record"]["content_hash"] == hashlib.sha256(body).hexdigest()


def test_envelope_invalid_without_source_record() -> None:
    outcome = _retrieve(link_id="", declared_type="cv")
    _assert_safe(outcome)
    assert outcome["error_code"] == ERROR_ENVELOPE_INVALID
    assert outcome["source_record"] is None


def test_modules_do_not_import_scoring_or_golden_answers() -> None:
    forbidden = {"app.engine.scoring", "score_assessment", "golden_candidates"}
    for path in LINKS_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert not forbidden.intersection(imported)
        for token in forbidden:
            assert token not in text


def test_is_unsafe_ip_covers_reserved_ranges() -> None:
    assert is_unsafe_ip("0.0.0.0") is True
    assert is_unsafe_ip("255.255.255.255") is True
    assert is_unsafe_ip("169.254.0.1") is True
    assert is_unsafe_ip("::") is True
    assert is_unsafe_ip(SAFE_IP) is False
    assert ip_address(SAFE_IP).is_global is True


def test_validate_hop_pins_a_global_address(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.engine.extraction.links.http.resolve_hostname",
        lambda hostname, port: ["1.1.1.1", "8.8.8.8"],
    )
    hop = validate_hop("https://example.com/x")
    assert hop.pinned_ip == "1.1.1.1"
    assert hop.hostname == "example.com"


def test_resolve_hostname_maps_dns_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import socket

    def fail(*_args: object, **_kwargs: object) -> object:
        raise socket.gaierror("blocked")

    monkeypatch.setattr("app.engine.extraction.links.http.socket.getaddrinfo", fail)
    with pytest.raises(RetrievalError) as exc:
        resolve_hostname("example.com", 443)
    assert exc.value.error_code == ERROR_DNS_RESOLUTION_FAILED
    assert "blocked" not in exc.value.error_code


def test_resolve_hostname_deduplicates_addresses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.engine.extraction.links.http.socket.getaddrinfo",
        lambda *_args, **_kwargs: [
            (0, 0, 0, "", (SAFE_IP, 443)),
            (0, 0, 0, "", (SAFE_IP, 443)),
            (0, 0, 0, "", ("1.1.1.1", 443)),
        ],
    )
    assert resolve_hostname("example.com", 443) == [SAFE_IP, "1.1.1.1"]


def test_resolve_hostname_rejects_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.engine.extraction.links.http.socket.getaddrinfo",
        lambda *_args, **_kwargs: [],
    )
    with pytest.raises(RetrievalError) as exc:
        resolve_hostname("example.com", 443)
    assert exc.value.error_code == ERROR_DNS_RESOLUTION_FAILED


def test_send_pinned_get_reads_mocked_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["host"] == "example.com"
        return httpx.Response(
            200,
            headers={"content-type": "text/plain; charset=utf-8"},
            content=b"visible text",
        )

    class FakePinned(httpx.MockTransport):
        def __init__(self, _ip: str, _hostname: str) -> None:
            super().__init__(handler)

        def close(self) -> None:
            return None

    monkeypatch.setattr("app.engine.extraction.links.http.PinnedIPTransport", FakePinned)
    hop = PinnedHop("https://example.com/x", "https", "example.com", 443, SAFE_IP)
    response = original_send_pinned_get(hop)
    assert response.status_code == 200
    assert response.content == b"visible text"
    assert content_type_of(response.headers) == "text/plain"
    assert decode_body(response.content, response.headers) == "visible text"


def test_send_pinned_get_maps_timeout_and_redirect_without_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def timeout_handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("slow")

    class TimeoutPinned(httpx.MockTransport):
        def __init__(self, _ip: str, _hostname: str) -> None:
            super().__init__(timeout_handler)

        def close(self) -> None:
            return None

    monkeypatch.setattr("app.engine.extraction.links.http.PinnedIPTransport", TimeoutPinned)
    hop = PinnedHop("https://example.com/x", "https", "example.com", 443, SAFE_IP)
    with pytest.raises(RetrievalError) as timed_out:
        original_send_pinned_get(hop)
    assert timed_out.value.error_code == ERROR_TIMEOUT

    def redirect_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "/next"}, content=b"ignored")

    class RedirectPinned(httpx.MockTransport):
        def __init__(self, _ip: str, _hostname: str) -> None:
            super().__init__(redirect_handler)

        def close(self) -> None:
            return None

    monkeypatch.setattr("app.engine.extraction.links.http.PinnedIPTransport", RedirectPinned)
    redirected = original_send_pinned_get(hop)
    assert redirected.status_code == 302
    assert redirected.content == b""


def test_send_pinned_get_maps_connect_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    class BoomPinned(httpx.MockTransport):
        def __init__(self, _ip: str, _hostname: str) -> None:
            super().__init__(boom)

        def close(self) -> None:
            return None

    monkeypatch.setattr("app.engine.extraction.links.http.PinnedIPTransport", BoomPinned)
    hop = PinnedHop("https://example.com/x", "https", "example.com", 443, SAFE_IP)
    with pytest.raises(RetrievalError) as exc:
        original_send_pinned_get(hop)
    assert exc.value.error_code == ERROR_CONNECT_FAILURE


def test_content_length_header_rejects_before_read() -> None:
    class _Stream:
        headers = {"content-length": str(MAX_RESPONSE_BODY_BYTES + 1)}

        def iter_bytes(self) -> Any:
            raise AssertionError("must not stream an oversized declared body")

    with pytest.raises(RetrievalError) as exc:
        _read_capped_body(_Stream())  # type: ignore[arg-type]
    assert exc.value.error_code == ERROR_RESPONSE_TOO_LARGE


def test_pinned_transport_sets_sni_and_host() -> None:
    from app.engine.extraction.links.http import PinnedIPTransport

    captured: dict[str, Any] = {}

    class Inner(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            captured["host"] = request.headers["host"]
            captured["url_host"] = request.url.host
            captured["sni"] = request.extensions.get("sni_hostname")
            return httpx.Response(200, request=request, content=b"ok")

    transport = PinnedIPTransport(SAFE_IP, "example.com")
    transport._inner = Inner()
    request = httpx.Request("GET", "https://example.com/project")
    response = transport.handle_request(request)
    transport.close()
    assert response.status_code == 200
    assert captured["host"] == "example.com"
    assert captured["url_host"] == SAFE_IP
    assert captured["sni"] == "example.com"


def test_is_unsafe_ip_rejects_unparseable_values() -> None:
    assert is_unsafe_ip("not-an-ip") is True


def test_decode_body_falls_back_when_charset_is_unknown() -> None:
    assert decode_body(b"abc", {"content-type": "text/plain; charset=nope"}) == "abc"


def test_redirect_without_location_is_unsafe(
    monkeypatch: pytest.MonkeyPatch,
    allow_safe_dns: None,
) -> None:
    monkeypatch.setattr(
        "app.engine.extraction.links.http.send_pinned_get",
        lambda hop: HopResponse(302, {}, b"", hop.url),
    )
    outcome = _retrieve()
    _assert_safe(outcome)
    assert outcome["error_code"] == ERROR_UNSAFE_REDIRECT

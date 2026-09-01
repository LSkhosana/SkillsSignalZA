"""SSRF-safe HTTP retrieval for candidate-submitted links."""

from __future__ import annotations

import ipaddress
import socket
import ssl
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

from app.engine.extraction.links.outcomes import (
    ALLOWED_PORTS,
    ALLOWED_SCHEMES,
    CONNECT_TIMEOUT_SECONDS,
    ERROR_CONNECT_FAILURE,
    ERROR_DNS_RESOLUTION_FAILED,
    ERROR_MALFORMED_URL,
    ERROR_REDIRECT_LIMIT_EXCEEDED,
    ERROR_RESPONSE_TOO_LARGE,
    ERROR_TIMEOUT,
    ERROR_TLS_FAILURE,
    ERROR_UNSAFE_HOST,
    ERROR_UNSAFE_REDIRECT,
    ERROR_UNSUPPORTED_SCHEME,
    ERROR_URL_CREDENTIALS,
    ERROR_URL_TOO_LONG,
    MAX_REDIRECTS,
    MAX_RESPONSE_BODY_BYTES,
    READ_TIMEOUT_SECONDS,
)
from app.engine.extraction.links.url import is_ip_literal, parse_url, url_exceeds_length

_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_FIXED_HEADERS = {
    "Accept": "text/html, application/xhtml+xml, text/plain, text/markdown",
    "User-Agent": "SkillSignalZA-extract.link.v1",
}


@dataclass(frozen=True)
class HopResponse:
    """One validated HTTP hop result."""

    status_code: int
    headers: dict[str, str]
    content: bytes
    url: str


@dataclass(frozen=True)
class PinnedHop:
    """A URL hop pinned to one validated global address."""

    url: str
    scheme: str
    hostname: str
    port: int
    pinned_ip: str


class RetrievalError(Exception):
    """Safe retrieval failure carrying only a stable error code."""

    def __init__(self, error_code: str) -> None:
        super().__init__(error_code)
        self.error_code = error_code


def build_httpx_client(transport: httpx.BaseTransport | None = None) -> httpx.Client:
    """Return the production client with proxy inheritance disabled."""
    return httpx.Client(
        transport=transport,
        trust_env=False,
        follow_redirects=False,
        timeout=httpx.Timeout(READ_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS),
        headers=_FIXED_HEADERS,
        verify=True,
        cert=None,
        proxy=None,
        http2=False,
    )


def is_unsafe_ip(value: str) -> bool:
    """Return True when an address is not a global unicast address."""
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return True
    mapped = address.ipv4_mapped if isinstance(address, ipaddress.IPv6Address) else None
    if mapped is not None:
        return is_unsafe_ip(str(mapped))
    return not address.is_global


def resolve_hostname(hostname: str, port: int) -> list[str]:
    """Resolve a hostname to IP literals. Raises RetrievalError on DNS failure."""
    try:
        records = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise RetrievalError(ERROR_DNS_RESOLUTION_FAILED) from exc
    addresses: list[str] = []
    seen: set[str] = set()
    for record in records:
        ip_value = record[4][0]
        if ip_value in seen:
            continue
        seen.add(ip_value)
        addresses.append(ip_value)
    if not addresses:
        raise RetrievalError(ERROR_DNS_RESOLUTION_FAILED)
    return addresses


def validate_hop(url: str, *, previous_scheme: str | None = None) -> PinnedHop:
    """Validate one retrieval hop and pin it to a single safe address."""
    if url_exceeds_length(url):
        raise RetrievalError(ERROR_URL_TOO_LONG)
    try:
        scheme, hostname, port, _path, _query, normalized = parse_url(url)
    except (ValueError, TypeError) as exc:
        raise RetrievalError(ERROR_MALFORMED_URL) from exc
    parsed = urlsplit(normalized)
    if parsed.username is not None or parsed.password is not None:
        raise RetrievalError(ERROR_URL_CREDENTIALS)
    if scheme not in ALLOWED_SCHEMES:
        raise RetrievalError(ERROR_UNSUPPORTED_SCHEME)
    if previous_scheme == "https" and scheme == "http":
        raise RetrievalError(ERROR_UNSAFE_REDIRECT)
    if port not in ALLOWED_PORTS:
        raise RetrievalError(ERROR_UNSAFE_HOST)
    if is_ip_literal(hostname):
        raise RetrievalError(ERROR_UNSAFE_HOST)
    addresses = resolve_hostname(hostname, port)
    if any(is_unsafe_ip(address) for address in addresses):
        raise RetrievalError(ERROR_UNSAFE_HOST)
    pinned = str(sorted(addresses, key=_ip_sort_key)[0])
    return PinnedHop(
        url=normalized,
        scheme=scheme,
        hostname=hostname,
        port=port,
        pinned_ip=pinned,
    )


def retrieve_validated_resource(submitted_normalized_url: str) -> HopResponse:
    """Follow redirects only after revalidating every hop."""
    current = submitted_normalized_url
    previous_scheme: str | None = None
    for redirect_count in range(MAX_REDIRECTS + 1):
        hop = validate_hop(current, previous_scheme=previous_scheme)
        response = send_pinned_get(hop)
        if response.status_code in _REDIRECT_STATUSES:
            if redirect_count >= MAX_REDIRECTS:
                raise RetrievalError(ERROR_REDIRECT_LIMIT_EXCEEDED)
            location = _header(response.headers, "location")
            if not location:
                raise RetrievalError(ERROR_UNSAFE_REDIRECT)
            current = urljoin(hop.url, location)
            previous_scheme = hop.scheme
            continue
        return response
    raise RetrievalError(ERROR_REDIRECT_LIMIT_EXCEEDED)


def send_pinned_get(hop: PinnedHop) -> HopResponse:
    """GET one hop by connecting only to the validated address."""
    transport = PinnedIPTransport(hop.pinned_ip, hop.hostname)
    try:
        with build_httpx_client(transport=transport) as client:
            with client.stream("GET", hop.url) as response:
                headers = {key.lower(): value for key, value in response.headers.items()}
                if response.status_code in _REDIRECT_STATUSES or response.status_code >= 400:
                    response.close()
                    return HopResponse(
                        status_code=response.status_code,
                        headers=headers,
                        content=b"",
                        url=hop.url,
                    )
                content = _read_capped_body(response)
                return HopResponse(
                    status_code=response.status_code,
                    headers=headers,
                    content=content,
                    url=hop.url,
                )
    except RetrievalError:
        raise
    except httpx.TimeoutException as exc:
        raise RetrievalError(ERROR_TIMEOUT) from exc
    except (ssl.SSLError, httpx.ProtocolError) as exc:
        raise RetrievalError(ERROR_TLS_FAILURE) from exc
    except httpx.ConnectError as exc:
        if _is_tls_error(exc):
            raise RetrievalError(ERROR_TLS_FAILURE) from exc
        raise RetrievalError(ERROR_CONNECT_FAILURE) from exc
    except httpx.HTTPError as exc:
        raise RetrievalError(ERROR_CONNECT_FAILURE) from exc
    finally:
        transport.close()


def content_type_of(headers: dict[str, str]) -> str | None:
    """Return the lowercased MIME type without parameters."""
    raw = _header(headers, "content-type")
    if raw is None:
        return None
    return raw.split(";", 1)[0].strip().lower() or None


def charset_of(headers: dict[str, str]) -> str:
    """Return a charset from Content-Type, defaulting to UTF-8."""
    raw = _header(headers, "content-type") or ""
    for item in raw.split(";"):
        part = item.strip()
        if part.lower().startswith("charset="):
            value = part.split("=", 1)[1].strip().strip('"')
            if value:
                return value
    return "utf-8"


def decode_body(content: bytes, headers: dict[str, str]) -> str:
    """Decode assessed bytes using the declared charset."""
    charset = charset_of(headers)
    try:
        return content.decode(charset)
    except (LookupError, UnicodeDecodeError):
        return content.decode("utf-8", errors="replace")


class PinnedIPTransport(httpx.BaseTransport):
    """Connect to a pre-validated IP while preserving Host and TLS SNI."""

    def __init__(self, pinned_ip: str, server_hostname: str) -> None:
        self._pinned_ip = pinned_ip
        self._server_hostname = server_hostname
        self._inner = httpx.HTTPTransport(verify=True, retries=0, trust_env=False)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        headers = httpx.Headers(request.headers)
        headers["host"] = self._server_hostname
        pinned_url = request.url.copy_with(host=_url_host(self._pinned_ip))
        pinned = httpx.Request(
            request.method,
            pinned_url,
            headers=headers,
            stream=request.stream,
            extensions={**request.extensions, "sni_hostname": self._server_hostname},
        )
        return self._inner.handle_request(pinned)

    def close(self) -> None:
        self._inner.close()


def _read_capped_body(response: httpx.Response) -> bytes:
    declared = response.headers.get("content-length")
    if declared is not None:
        try:
            length = int(declared)
        except ValueError:
            length = -1
        if length > MAX_RESPONSE_BODY_BYTES:
            raise RetrievalError(ERROR_RESPONSE_TOO_LARGE)
    buffer = bytearray()
    for chunk in response.iter_bytes():
        buffer.extend(chunk)
        if len(buffer) > MAX_RESPONSE_BODY_BYTES:
            raise RetrievalError(ERROR_RESPONSE_TOO_LARGE)
    return bytes(buffer)


def _header(headers: dict[str, str], name: str) -> str | None:
    lowered = name.lower()
    for key, value in headers.items():
        if key.lower() == lowered:
            return value
    return None


def _is_tls_error(exc: BaseException) -> bool:
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, ssl.SSLError):
            return True
        current = current.__cause__ or current.__context__
    return "ssl" in type(exc).__name__.lower() or "certificate" in type(exc).__name__.lower()


def _url_host(ip_value: str) -> str:
    try:
        address = ipaddress.ip_address(ip_value)
    except ValueError:
        return ip_value
    if address.version == 6:
        return ip_value
    return ip_value


def _ip_sort_key(value: str) -> tuple[int, str]:
    return (ipaddress.ip_address(value).version, value)

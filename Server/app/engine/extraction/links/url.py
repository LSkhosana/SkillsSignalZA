"""Pure deterministic URL normalization for candidate-submitted links."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit, urlunsplit

from app.engine.extraction.links.outcomes import MAX_URL_LENGTH


def normalize_submitted_url(url: str) -> str:
    """Normalize a submitted URL without changing request semantics.

    Surrounding whitespace is trimmed. Scheme and hostname are lowercased,
    the hostname is IDNA-encoded, default HTTP/HTTPS ports are removed, and
    the fragment is dropped. Path case and query order/values are preserved.
    """
    trimmed = url.strip()
    parts = urlsplit(trimmed)
    scheme = parts.scheme.lower()
    hostname = parts.hostname
    if hostname is None:
        msg = "URL has no hostname"
        raise ValueError(msg)
    ascii_host = _idna_host(hostname)
    host_for_netloc = _bracket_ipv6(ascii_host)
    port = parts.port
    if port is not None and not _is_default_port(scheme, port):
        netloc = f"{host_for_netloc}:{port}"
    else:
        netloc = host_for_netloc
    if parts.username is not None:
        userinfo = parts.username
        if parts.password is not None:
            userinfo = f"{userinfo}:{parts.password}"
        netloc = f"{userinfo}@{netloc}"
    return urlunsplit((scheme, netloc, parts.path, parts.query, ""))


def parse_url(url: str) -> tuple[str, str, int, str, str, str]:
    """Return scheme, hostname, port, path, query, and normalized URL."""
    normalized = normalize_submitted_url(url)
    parts = urlsplit(normalized)
    hostname = parts.hostname
    if not parts.scheme or hostname is None:
        msg = "URL is malformed"
        raise ValueError(msg)
    port = parts.port
    if port is None:
        port = 443 if parts.scheme == "https" else 80
    return parts.scheme, hostname, port, parts.path, parts.query, normalized


def is_ip_literal(hostname: str) -> bool:
    """Return True when the hostname is an IPv4 or IPv6 literal."""
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return True


def url_exceeds_length(url: str) -> bool:
    """Return True when the URL exceeds the launch length limit."""
    return len(url) > MAX_URL_LENGTH


def _idna_host(hostname: str) -> str:
    lowered = hostname.lower()
    try:
        return lowered.encode("idna").decode("ascii")
    except UnicodeError:
        return lowered


def _bracket_ipv6(hostname: str) -> str:
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return hostname
    if address.version == 6:
        return f"[{hostname}]"
    return hostname


def _is_default_port(scheme: str, port: int) -> bool:
    return (scheme == "http" and port == 80) or (scheme == "https" and port == 443)

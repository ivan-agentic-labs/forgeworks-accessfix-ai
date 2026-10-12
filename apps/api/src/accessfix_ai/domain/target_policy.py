from __future__ import annotations

import ipaddress
import os
import socket
from collections.abc import Callable, Iterable
from urllib.parse import urlparse


# These limits are deliberately conservative.  They are part of the network
# policy hash and must be changed together with an explicit contract review.
MAX_REDIRECTS = 5
MIN_SCAN_PATHS = 1
MAX_SCAN_PATHS = 20
MAX_SCAN_PATH_LENGTH = 2048

Resolver = Callable[[str], Iterable[str]]


def _reject_unsafe_url_bytes(value: str) -> None:
    """Never let URL parser normalization change the checked target."""
    if not isinstance(value, str) or any(ord(ch) <= 0x20 or ord(ch) == 0x7f or ch == "\\" for ch in value):
        raise ValueError("unsafe URL characters")


def _resolve(host: str) -> list[str]:
    """Resolve a host to numeric addresses without following application URLs."""
    try:
        return sorted({item[4][0] for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)})
    except (OSError, socket.gaierror):
        # An unresolvable target is not safe to contact.  Returning no answers
        # lets the caller fail closed without exposing resolver details.
        return []


def _is_blocked_address(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return True
    # "not private" does not mean globally routable: e.g. RFC 6598
    # shared/CGNAT 100.64.0.0/10 has is_private=False and
    # is_reserved=False, but must never be eligible for outbound scans.
    # Deny every non-global range, including future special-purpose ranges.
    return not address.is_global


def _checked_answers(host: str, resolver: Resolver) -> tuple[str, ...]:
    answers = tuple(str(answer) for answer in resolver(host))
    if not answers:
        raise ValueError("DNS resolution failed")
    if any(_is_blocked_address(answer) for answer in answers):
        raise ValueError("private, loopback, link-local, or reserved targets are blocked")
    return tuple(sorted(set(answers)))


def validate_origin(origin: str, allow_fixture: bool = True) -> str:
    _reject_unsafe_url_bytes(origin)
    p = urlparse(origin)
    try:
        p.port  # Force malformed port numbers to fail at the validation boundary.
    except ValueError as exc:
        raise ValueError("invalid HTTPS origin port") from exc
    if allow_fixture and os.getenv("APP_ENV", "development") in {"development", "test"} and p.hostname == "fixture.local" and p.scheme == "http":
        if p.username or p.password or p.path not in ("", "/") or p.query or p.fragment or p.port:
            raise ValueError("only canonical fixture origins are allowed")
        return origin.rstrip("/")
    if p.scheme != "https" or not p.hostname or p.username or p.password or p.path not in ("", "/") or p.query or p.fragment:
        raise ValueError("only canonical HTTPS origins are allowed")
    # Remote proof fetches and the isolated scanner contract are pinned to TLS
    # port 443. Accepting a nonstandard port only at the scan boundary would
    # create an inconsistent ownership/egress policy.
    if p.port not in (None, 443):
        raise ValueError("only HTTPS port 443 is supported")
    # The fixture is local-only. An HTTPS spelling must never bypass DNS
    # validation or become a remotely scannable target.
    if p.hostname.lower() == "fixture.local":
        raise ValueError("fixture.local cannot be a public scan origin")
    try:
        # ip_address raises for DNS names; those are checked at connection time
        # by validate_redirect_chain/validate_scan_path with the resolver.
        ip = ipaddress.ip_address(p.hostname)
        if _is_blocked_address(str(ip)):
            raise ValueError("private, loopback, link-local, or reserved targets are blocked")
    except ValueError as exc:
        if "blocked" in str(exc):
            raise
    if p.hostname.lower() in {"169.254.169.254", "metadata.google.internal", "localhost"}:
        raise ValueError("metadata and localhost targets are blocked")
    return origin.rstrip("/")


def _same_origin(candidate: str, origin: str) -> bool:
    _reject_unsafe_url_bytes(candidate)
    target = urlparse(candidate)
    verified = urlparse(origin)
    return (
        target.scheme == verified.scheme
        and target.hostname is not None
        and target.hostname.lower() == (verified.hostname or "").lower()
        and target.port == verified.port
        and not target.username
        and not target.password
    )


def _require_bounded_path(path: str) -> None:
    if not isinstance(path, str) or not path:
        raise ValueError(f"scan path maximum length is {MAX_SCAN_PATH_LENGTH}")
    try:
        encoded_bytes = len(path.encode("utf-8", errors="strict"))
    except UnicodeError as exc:
        raise ValueError("scan path must be valid UTF-8") from exc
    if encoded_bytes > MAX_SCAN_PATH_LENGTH:
        raise ValueError(f"scan path maximum length is {MAX_SCAN_PATH_LENGTH} UTF-8 bytes")


def validate_scan_path(path: str, origin: str, resolver: Resolver | None = None) -> str:
    _require_bounded_path(path)
    _reject_unsafe_url_bytes(path)
    # A network-path reference must never be rewritten into a local-looking
    # path by stripping its leading slashes.
    if path.startswith("//"):
        raise ValueError("protocol-relative scan paths are not allowed")
    origin = validate_origin(origin)
    candidate = path if path.startswith(("http://", "https://")) else origin + "/" + path.lstrip("/")
    parsed = urlparse(candidate)
    if not _same_origin(candidate, origin) or parsed.fragment:
        raise ValueError("path leaves verified origin")
    # Literal addresses are checked even for the fixture host.  For DNS names,
    # resolution is deliberately injectable for deterministic tests and is
    # performed before a browser is allowed to connect.
    if parsed.hostname:
        # The synthetic fixture is intentionally not DNS-backed.  Every other
        # host must resolve successfully and all answers must be public before
        # it can reach a browser process.
        if parsed.hostname != "fixture.local":
            _checked_answers(parsed.hostname, resolver or _resolve)
    return candidate


def validate_scan_request(paths: list[str], origin: str | None = None) -> list[str]:
    if not isinstance(paths, list) or not (MIN_SCAN_PATHS <= len(paths) <= MAX_SCAN_PATHS):
        raise ValueError(f"scan paths must be between {MIN_SCAN_PATHS} and {MAX_SCAN_PATHS} items")
    for path in paths:
        _require_bounded_path(path)
        _reject_unsafe_url_bytes(path)
        if path.startswith("//"):
            raise ValueError("protocol-relative scan paths are not allowed")
    if origin is None:
        return paths
    return [validate_scan_path(path, origin) for path in paths]


def validate_redirect_chain(
    urls: list[str], verified_origin: str, resolver: Resolver | None = None
) -> list[str]:
    if not urls:
        raise ValueError("redirect chain must contain an initial URL")
    if len(urls) - 1 > MAX_REDIRECTS:
        raise ValueError("redirect limit exceeded")
    verified_origin = validate_origin(verified_origin)
    resolve = resolver or _resolve
    baseline = _checked_answers(urlparse(verified_origin).hostname or "", resolve)
    for url in urls:
        if not _same_origin(url, verified_origin):
            raise ValueError("redirect leaves verified origin")
        parsed = urlparse(url)
        current = _checked_answers(parsed.hostname or "", resolve)
        if current != baseline:
            raise ValueError("DNS answer changed during redirect chain")
    return urls

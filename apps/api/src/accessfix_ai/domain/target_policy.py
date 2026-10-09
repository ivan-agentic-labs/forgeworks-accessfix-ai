from __future__ import annotations

import ipaddress
from urllib.parse import urlparse


def validate_origin(origin: str, allow_fixture: bool = True) -> str:
    p = urlparse(origin)
    if allow_fixture and p.hostname == "fixture.local" and p.scheme == "http":
        return origin.rstrip("/")
    if p.scheme != "https" or not p.hostname or p.username or p.password or p.path not in ("", "/"):
        raise ValueError("only canonical HTTPS origins are allowed")
    try:
        ip = ipaddress.ip_address(p.hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("private, loopback, link-local, or reserved targets are blocked")
    except ValueError as exc:
        if "blocked" in str(exc): raise
    if p.hostname.lower() in {"169.254.169.254", "metadata.google.internal", "localhost"}:
        raise ValueError("metadata and localhost targets are blocked")
    return origin.rstrip("/")


def validate_scan_path(path: str, origin: str) -> str:
    candidate = path if path.startswith("http") else origin + "/" + path.lstrip("/")
    p = urlparse(candidate)
    if p.scheme != urlparse(origin).scheme or p.hostname != urlparse(origin).hostname:
        raise ValueError("path leaves verified origin")
    return candidate

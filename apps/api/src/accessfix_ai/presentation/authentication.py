"""Bearer verification. Development credentials require explicit test/development mode."""
from __future__ import annotations

import math
import os
from functools import lru_cache
from urllib.parse import urlsplit
from uuid import UUID

import jwt
from fastapi import HTTPException

PRODUCT = "accessfix-ai"

REQUIRED = ["exp", "iss", "aud", "sub", "tenant_id"]


def problem(status: int, code: str, detail: str):
    raise HTTPException(status_code=status, detail={"type": "about:blank", "title": "Request rejected", "status": status, "code": code, "detail": detail, "request_id": "runtime"})


def identity_url(url: str):
    """Reject malformed configuration rather than silently normalizing it."""
    try:
        if any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in url):
            raise ValueError("Whitespace or control character in identity URL")
        parsed = urlsplit(url)
        # Accessing port validates its syntax and range even for OIDC endpoints.
        parsed.port
    except ValueError:
        problem(503, "AUTH_NOT_CONFIGURED", "Identity URLs must be valid HTTPS endpoints")
    return parsed


def configuration():
    mode = os.getenv("AUTH_MODE", "oidc")
    environment = os.getenv("APP_ENV", "development")
    issuer = os.getenv("AUTH_ISSUER", "")
    audience = os.getenv("AUTH_AUDIENCE", "")
    if mode == "development":
        secret = os.getenv("DEV_AUTH_SECRET", "")
        if environment not in {"development", "test"} or len(secret.encode()) < 32 or not issuer or not audience:
            problem(503, "AUTH_NOT_CONFIGURED", "Explicit development configuration is required; development auth is forbidden outside test/development")
        return mode, issuer, audience, secret
    if mode == "supabase":
        base = os.getenv("SUPABASE_URL", "").rstrip("/")
        parsed = identity_url(base)
        if (parsed.scheme != "https" or not parsed.hostname
                or not parsed.hostname.endswith(".supabase.co")
                or parsed.username or parsed.password or parsed.port
                or parsed.path or parsed.query or parsed.fragment):
            problem(503, "AUTH_NOT_CONFIGURED", "SUPABASE_URL must be a hosted HTTPS project origin")
        return mode, base + "/auth/v1", "authenticated", base + "/auth/v1/.well-known/jwks.json"
    if mode != "oidc":
        problem(503, "AUTH_NOT_CONFIGURED", "Unsupported authentication mode")
    jwks_url = os.getenv("AUTH_JWKS_URL", "")
    for url in (issuer, jwks_url):
        parsed = identity_url(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            problem(503, "AUTH_NOT_CONFIGURED", "OIDC issuer and JWKS URL must be configured HTTPS endpoints")
    if not audience:
        problem(503, "AUTH_NOT_CONFIGURED", "OIDC audience is required")
    return mode, issuer, audience, jwks_url


@lru_cache(maxsize=8)
def jwks_client(url: str):
    # The endpoint comes only from trusted configuration, never token jku/x5u/iss.
    return jwt.PyJWKClient(url, timeout=3, lifespan=60, cache_keys=False)


def decode_bearer(authorization: str | None) -> dict:
    if not authorization or not authorization.startswith("Bearer ") or len(authorization) > 16384:
        problem(401, "UNAUTHENTICATED", "Bearer token is required")
    mode, issuer, audience, material = configuration()
    token = authorization[7:]
    try:
        algorithm = jwt.get_unverified_header(token).get("alg")
        allowed = ["HS256"] if mode == "development" else ["ES256", "RS256"] if mode == "supabase" else ["RS256"]
        if algorithm not in allowed:
            raise jwt.InvalidAlgorithmError("Unexpected algorithm")
        key = material if mode == "development" else jwks_client(material).get_signing_key_from_jwt(token).key
        required = ["exp", "iat", "iss", "aud", "sub", "role", "session_id", "is_anonymous"] if mode == "supabase" else REQUIRED
        claims = jwt.decode(token, key, algorithms=allowed, issuer=issuer, audience=audience, options={"require": required})
        for field in ("exp", "iat", "nbf"):
            if field in claims:
                value = claims[field]
                if (type(value) not in (int, float)
                        or isinstance(value, float) and not math.isfinite(value)):
                    raise jwt.InvalidTokenError("NumericDate must be a finite JSON number")
        if mode == "supabase":
            # Ignore user_metadata and top-level application claims entirely.
            if claims["role"] != "authenticated" or claims["is_anonymous"] is not False:
                raise jwt.InvalidTokenError("A non-anonymous user session is required")
            claims["sub"] = str(UUID(claims["sub"]))
            claims["session_id"] = str(UUID(claims["session_id"]))
            metadata = claims.get("app_metadata")
            grants = metadata.get("forgeworks") if isinstance(metadata, dict) else None
            grant = grants.get(PRODUCT) if isinstance(grants, dict) else None
            if not isinstance(grant, dict):
                raise jwt.InvalidTokenError("Server-provisioned product grant is required")
            scopes = grant.get("scopes")
            if not isinstance(scopes, list) or len(scopes) > 64 or any(not isinstance(s, str) or not s or any(c.isspace() for c in s) or len(s) > 100 for s in scopes):
                raise jwt.InvalidTokenError("Invalid product scopes")
            claims["tenant_id"] = grant.get("tenant_id")
            claims["scope"] = " ".join(scopes)
            claims["_supabase_session"] = True
        if not isinstance(claims["tenant_id"], str) or not claims["tenant_id"] or not claims["sub"]:
            raise jwt.InvalidTokenError("Missing tenant or subject")
        try:
            claims["tenant_id"] = str(UUID(claims["tenant_id"]))
        except ValueError as error:
            raise jwt.InvalidTokenError("Tenant claim must be a UUID") from error
        return claims
    except jwt.PyJWKClientConnectionError:
        problem(503, "IDENTITY_PROVIDER_UNAVAILABLE", "Identity key service is unavailable")
    except (jwt.PyJWTError, ValueError, TypeError, AttributeError, OverflowError):
        problem(401, "INVALID_TOKEN", "Token signature or required claims are invalid")


def verify_session(store, claims: dict) -> None:
    """Online revocation check in addition to signature/expiry and membership."""
    if not claims.get("_supabase_session"):
        return
    check = getattr(store, "session_active", None)
    if check is None:
        problem(503, "SESSION_CHECK_UNAVAILABLE", "A PostgreSQL session verifier is required")
    try:
        active = check(claims["tenant_id"], claims["sub"], claims["session_id"])
    except Exception:
        problem(503, "SESSION_CHECK_UNAVAILABLE", "Session verification is unavailable")
    if not active:
        problem(401, "SESSION_REVOKED", "The user session is inactive")


def readiness(store) -> dict:
    """Configuration, public signing keys and current database connectivity."""
    mode, _, _, material = configuration()
    try:
        if mode != "development":
            jwks_client(material).get_signing_keys()
        dsn = getattr(store, "dsn", None)
        if os.getenv("APP_ENV", "development") not in {"development", "test"} and not dsn:
            problem(503, "NOT_READY", "PostgreSQL is required outside development/test")
        if dsn:
            import psycopg
            with psycopg.connect(dsn, connect_timeout=5) as db:
                db.execute("SELECT 1")
        return {"status": "ready"}
    except HTTPException:
        raise
    except Exception:
        problem(503, "NOT_READY", "Identity keys or database are unavailable")

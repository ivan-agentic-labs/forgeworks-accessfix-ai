"""Bearer verification. Development credentials require explicit test/development mode."""
from __future__ import annotations

import os
from functools import lru_cache
from urllib.parse import urlsplit
from uuid import UUID

import jwt
from fastapi import HTTPException

REQUIRED = ["exp", "iss", "aud", "sub", "tenant_id"]


def problem(status: int, code: str, detail: str):
    raise HTTPException(status_code=status, detail={"type": "about:blank", "title": "Request rejected", "status": status, "code": code, "detail": detail, "request_id": "runtime"})


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
    if mode != "oidc":
        problem(503, "AUTH_NOT_CONFIGURED", "Unsupported authentication mode")
    jwks_url = os.getenv("AUTH_JWKS_URL", "")
    for url in (issuer, jwks_url):
        parsed = urlsplit(url)
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
        algorithm = "HS256" if mode == "development" else "RS256"
        if jwt.get_unverified_header(token).get("alg") != algorithm:
            raise jwt.InvalidAlgorithmError("Unexpected algorithm")
        key = material if mode == "development" else jwks_client(material).get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=[algorithm], issuer=issuer, audience=audience, options={"require": REQUIRED})
        if not isinstance(claims["tenant_id"], str) or not claims["tenant_id"] or not claims["sub"]:
            raise jwt.InvalidTokenError("Missing tenant or subject")
        try:
            claims["tenant_id"] = str(UUID(claims["tenant_id"]))
        except ValueError as error:
            raise jwt.InvalidTokenError("Tenant claim must be a UUID") from error
        return claims
    except jwt.PyJWKClientConnectionError:
        problem(503, "IDENTITY_PROVIDER_UNAVAILABLE", "Identity key service is unavailable")
    except jwt.PyJWTError:
        problem(401, "INVALID_TOKEN", "Token signature or required claims are invalid")

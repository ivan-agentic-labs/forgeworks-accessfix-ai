"""Malformed input must reject predictably; all credentials are synthetic."""
import time

import jwt
import pytest
from fastapi import HTTPException
from accessfix_ai.presentation.authentication import configuration, decode_bearer

@pytest.mark.parametrize("field", ["exp", "iat", "nbf"])
@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan"), True, False, "2000000000", None])
def test_invalid_numeric_dates_rejected(field, value):
    claims = {"sub": "test-user", "tenant_id": "00000000-0000-0000-0000-000000000001", "iss": "https://issuer.synthetic.invalid", "aud": "forgeworks-api", "exp": time.time() + 60}
    claims[field] = value
    signed = jwt.encode(claims, "forgeworks-development-secret-32-plus", algorithm="HS256")
    with pytest.raises(HTTPException) as error:
        decode_bearer("Bearer " + signed)
    assert error.value.status_code == 401
    assert error.value.detail["code"] == "INVALID_TOKEN"


def test_finite_fractional_numeric_dates_remain_valid():
    claims = {"sub": "test-user", "tenant_id": "00000000-0000-0000-0000-000000000001", "iss": "https://issuer.synthetic.invalid", "aud": "forgeworks-api", "exp": time.time() + 60, "iat": time.time() - 10, "nbf": time.time() - 5}
    signed = jwt.encode(claims, "forgeworks-development-secret-32-plus", algorithm="HS256")
    assert decode_bearer("Bearer " + signed)["sub"] == "test-user"

@pytest.mark.parametrize("url", ["https://[", "https://project.supabase.co:bad", "https://project.supabase.co:65536", "https://project.supabase.co\t", " https://project.supabase.co"])
@pytest.mark.parametrize("mode", ["supabase", "oidc"])
def test_malformed_identity_urls_are_configuration_errors(monkeypatch, url, mode):
    monkeypatch.setenv("AUTH_MODE", mode)
    monkeypatch.setenv("SUPABASE_URL", url)
    monkeypatch.setenv("AUTH_ISSUER", url)
    monkeypatch.setenv("AUTH_JWKS_URL", "https://idp.test.invalid/jwks")
    with pytest.raises(HTTPException) as error:
        configuration()
    assert error.value.status_code == 503
    assert error.value.detail["code"] == "AUTH_NOT_CONFIGURED"


@pytest.mark.parametrize("url", ["https://[", "https://idp.test.invalid:bad/jwks", "https://idp.test.invalid:65536/jwks", "https://idp.test.invalid/jwks\t"])
def test_malformed_jwks_urls_are_configuration_errors(monkeypatch, url):
    monkeypatch.setenv("AUTH_MODE", "oidc")
    monkeypatch.setenv("AUTH_JWKS_URL", url)
    with pytest.raises(HTTPException) as error:
        configuration()
    assert error.value.status_code == 503
    assert error.value.detail["code"] == "AUTH_NOT_CONFIGURED"


def test_valid_oidc_port_is_preserved(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "oidc")
    monkeypatch.setenv("AUTH_JWKS_URL", "https://idp.test.invalid:8443/jwks")
    assert configuration()[3] == "https://idp.test.invalid:8443/jwks"

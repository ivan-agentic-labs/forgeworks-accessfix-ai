import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from accessfix_ai.presentation.authentication import decode_bearer, jwks_client


def payload():
    return {"sub": "test-user", "tenant_id": "test-tenant", "scope": "job:read", "iss": "https://issuer.synthetic.invalid", "aud": "forgeworks-api", "exp": int(time.time()) + 60}


def bearer(claims, algorithm="HS256"):
    return "Bearer " + jwt.encode(claims, ("forgeworks-development-secret-32-plus" if algorithm == "HS256" else "x" * 64), algorithm=algorithm)


@pytest.mark.parametrize("missing", ["exp", "iss", "aud", "sub", "tenant_id"])
def test_required_claims(missing):
    claims = payload()
    del claims[missing]
    with pytest.raises(HTTPException) as error:
        decode_bearer(bearer(claims))
    assert error.value.status_code == 401


@pytest.mark.parametrize("change", [{"exp": 1}, {"iss": "https://attacker.invalid"}, {"aud": "wrong-api"}])
def test_reject_invalid_claims(change):
    with pytest.raises(HTTPException) as error:
        decode_bearer(bearer({**payload(), **change}))
    assert error.value.status_code == 401


def test_wrong_algorithm():
    with pytest.raises(HTTPException) as error:
        decode_bearer(bearer(payload(), "HS384"))
    assert error.value.status_code == 401


def test_development_auth_forbidden_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(HTTPException) as error:
        decode_bearer(bearer(payload()))
    assert error.value.status_code == 503


def test_no_implicit_secret(monkeypatch):
    monkeypatch.delenv("DEV_AUTH_SECRET")
    with pytest.raises(HTTPException) as error:
        decode_bearer(bearer(payload()))
    assert error.value.status_code == 503


def test_oidc_key_rotation_and_algorithm_confusion(monkeypatch):
    keys = [rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(2)]
    document = {"keys": [{**json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(keys[0].public_key())), "kid": "first", "use": "sig", "alg": "RS256"}]}
    monkeypatch.setenv("AUTH_MODE", "oidc")
    monkeypatch.setenv("AUTH_ISSUER", "https://idp.test.invalid")
    monkeypatch.setenv("AUTH_JWKS_URL", "https://idp.test.invalid/jwks")
    jwks_client.cache_clear()
    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", lambda _: document)
    claims = {**payload(), "iss": "https://idp.test.invalid"}
    for index, kid in enumerate(("first", "rotated")):
        document["keys"] = [{**json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(keys[index].public_key())), "kid": kid, "use": "sig", "alg": "RS256"}]
        token = jwt.encode(claims, keys[index], algorithm="RS256", headers={"kid": kid})
        assert decode_bearer("Bearer " + token)["sub"] == "test-user"
    with pytest.raises(HTTPException) as error:
        decode_bearer(bearer(claims))
    assert error.value.status_code == 401
    jwks_client.cache_clear()

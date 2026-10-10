"""Offline signing and denial tests; not live IdP acceptance."""
import json
import time
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi import HTTPException

from accessfix_ai.presentation.authentication import PRODUCT, decode_bearer, jwks_client, verify_session, readiness, configuration

TENANT = "00000000-0000-0000-0000-000000000001"

@pytest.fixture
def identity(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://abcdefghijklmnopqrst.supabase.co")
    jwks_client.cache_clear()
    key=ec.generate_private_key(ec.SECP256R1())
    document={"keys":[{**json.loads(jwt.algorithms.ECAlgorithm.to_jwk(key.public_key())), "kid":"test", "use":"sig", "alg":"ES256"}]}
    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", lambda _: document)
    claims={"exp":int(time.time())+60,"iat":int(time.time())-1,"iss":"https://abcdefghijklmnopqrst.supabase.co/auth/v1","aud":"authenticated","sub":str(uuid4()),"session_id":str(uuid4()),"role":"authenticated","is_anonymous":False,"app_metadata":{"forgeworks":{PRODUCT:{"tenant_id":TENANT,"scopes":["job:read"]}}}}
    yield key,claims,document
    jwks_client.cache_clear()

def token(key, claims, algorithm="ES256"):
    return "Bearer " + jwt.encode(claims,key,algorithm=algorithm,headers={"kid":"test"})

def test_supabase_es256_and_server_product_grants(identity):
    key,claims,_=identity
    claims.update({"tenant_id":"attacker","scope":"admin","user_metadata":{"forgeworks":{PRODUCT:{"tenant_id":"attacker","scopes":["admin"]}}}})
    result=decode_bearer(token(key,claims))
    assert result["tenant_id"]==TENANT and result["scope"]=="job:read"
    assert result["_supabase_session"] is True

def test_supabase_rs256(identity):
    _,claims,document=identity
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    document["keys"]=[{**json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key())),"kid":"test","use":"sig","alg":"RS256"}]
    assert decode_bearer(token(key,claims,"RS256"))["tenant_id"]==TENANT

@pytest.mark.parametrize("field",["exp","iat","sub","session_id","role","is_anonymous","iss","aud"])
def test_supabase_missing_claims(identity,field):
    key,claims,_=identity
    del claims[field]
    with pytest.raises(HTTPException) as error: decode_bearer(token(key,claims))
    assert error.value.status_code==401

@pytest.mark.parametrize("changes",[{"role":"service_role"},{"role":"anon"},{"is_anonymous":True},{"is_anonymous":"false"},{"sub":"not-uuid"},{"session_id":"not-uuid"},{"app_metadata":None},{"exp":1},{"aud":"other"},{"iss":"https://attacker.supabase.co/auth/v1"}])
def test_supabase_untrusted_or_invalid_identity(identity,changes):
    key,claims,_=identity
    claims.update(changes)
    with pytest.raises(HTTPException) as error: decode_bearer(token(key,claims))
    assert error.value.status_code==401

def test_supabase_user_metadata_cannot_grant_access(identity):
    key,claims,_=identity
    claims["user_metadata"]=claims.pop("app_metadata")
    with pytest.raises(HTTPException) as error: decode_bearer(token(key,claims))
    assert error.value.status_code==401

def test_supabase_different_product_denied(identity):
    key,claims,_=identity
    claims["app_metadata"]["forgeworks"]["other-product"]=claims["app_metadata"]["forgeworks"].pop(PRODUCT)
    with pytest.raises(HTTPException) as error: decode_bearer(token(key,claims))
    assert error.value.status_code==401

@pytest.mark.parametrize("scopes",["admin",["read write"],[None],[],["job:read"]*65])
def test_scope_type_and_boundaries(identity,scopes):
    key,claims,_=identity
    claims["app_metadata"]["forgeworks"][PRODUCT]["scopes"]=scopes
    if scopes==[]:
        assert decode_bearer(token(key,claims))["scope"]==""
    else:
        with pytest.raises(HTTPException) as error: decode_bearer(token(key,claims))
        assert error.value.status_code==401

def test_no_symmetric_fallback(identity):
    _,claims,_=identity
    with pytest.raises(HTTPException) as error: decode_bearer(token("x"*64,claims,"HS256"))
    assert error.value.status_code==401

@pytest.mark.parametrize("state",[True,False,"unavailable"])
def test_online_session_check(identity,state):
    key,claims,_=identity
    result=decode_bearer(token(key,claims))
    def check(tenant,user,sid):
        assert (tenant,user,sid)==(TENANT,claims["sub"],claims["session_id"])
        if state=="unavailable": raise RuntimeError("database unavailable")
        return state
    store=SimpleNamespace(session_active=check)
    if state is True: verify_session(store,result)
    else:
        with pytest.raises(HTTPException) as error: verify_session(store,result)
        assert error.value.status_code==(503 if state=="unavailable" else 401)

def test_no_session_adapter_fails_closed(identity):
    key,claims,_=identity
    with pytest.raises(HTTPException) as error: verify_session(object(),decode_bearer(token(key,claims)))
    assert error.value.status_code==503

def test_staging_sqlite_readiness_denied(identity):
    with pytest.raises(HTTPException) as error: readiness(object())
    assert error.value.status_code==503

@pytest.mark.parametrize("url",["http://project.supabase.co","https://attacker.invalid","https://user:pass@"+"project.supabase.co","https://project.supabase.co/path","https://project.supabase.co?x=y"], ids=["insecure", "foreign", "userinfo", "path", "query"])
def test_supabase_configuration_origin(monkeypatch,url):
    monkeypatch.setenv("AUTH_MODE","supabase")
    monkeypatch.setenv("SUPABASE_URL",url)
    with pytest.raises(HTTPException) as error: configuration()
    assert error.value.status_code==503


@pytest.mark.parametrize("field", ["exp", "iat", "nbf"])
@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan"), True, False, "2000000000", None])
def test_supabase_invalid_numeric_dates(identity, field, value):
    key, claims, _ = identity
    claims[field] = value
    with pytest.raises(HTTPException) as error:
        decode_bearer(token(key, claims))
    assert error.value.status_code == 401
    assert error.value.detail["code"] == "INVALID_TOKEN"


def test_supabase_fractional_numeric_dates(identity):
    key, claims, _ = identity
    claims.update(exp=time.time() + 60, iat=time.time() - 10, nbf=time.time() - 5)
    assert decode_bearer(token(key, claims))["tenant_id"] == TENANT

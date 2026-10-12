import importlib.util
import time
from pathlib import Path

import jwt
import pytest


def helper():
    path = Path(__file__).resolve().parents[2] / "scripts/development_token.py"
    spec = importlib.util.spec_from_file_location("local_token_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("environment,mode", [
    ("staging", "development"), ("production", "development"),
    ("development", "supabase"), ("local", "development"),
])
def test_local_token_refuses_hosted_or_ambiguous_mode(monkeypatch, environment, mode):
    monkeypatch.setenv("APP_ENV", environment)
    monkeypatch.setenv("AUTH_MODE", mode)
    with pytest.raises(ValueError):
        helper().mint_token()


def test_explicit_local_token_is_short_lived_synthetic_and_scoped(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_MODE", "development")
    monkeypatch.setenv("DEV_AUTH_SECRET", "synthetic-test-secret-" + "x" * 32)
    monkeypatch.setenv("AUTH_ISSUER", "https://issuer.synthetic.invalid")
    monkeypatch.setenv("AUTH_AUDIENCE", "forgeworks-api")
    token = helper().mint_token()
    payload = jwt.decode(token, "synthetic-test-secret-" + "x" * 32, algorithms=["HS256"],
                         issuer="https://issuer.synthetic.invalid", audience="forgeworks-api")
    assert payload["tenant_id"] == "00000000-0000-0000-0000-000000000001"
    assert payload["sub"] == "00000000-0000-0000-0000-000000000010"
    assert 0 < payload["exp"] - int(time.time()) <= 900
    assert payload["scope"] and "*" not in payload["scope"].split()

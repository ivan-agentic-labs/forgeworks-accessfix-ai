"""Network-free acceptance tests for user-provided HTML analysis."""

import hashlib
from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

from accessfix_ai.main import create_app
from accessfix_ai.infrastructure.store import TENANT, USER


def _auth(scopes="scan:start"):
    token = jwt.encode({
        "sub": USER, "tenant_id": TENANT, "scope": scopes,
        "iss": "https://issuer.synthetic.invalid", "aud": "forgeworks-api",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }, "forgeworks-development-secret-32-plus", algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def test_offline_html_detects_missing_alt_and_returns_source_digest(tmp_path):
    source = '<main><img id="hero" src="picture.png"><img alt="Existing label"></main>'
    with TestClient(create_app(str(tmp_path / "offline.db"), seed=True)) as client:
        response = client.post("/v1/offline/html-findings", headers=_auth(), json={"source_html": source})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["scan_mode"] == "OFFLINE_STATIC_IMAGE_ALT"
        assert body["source_kind"] == "USER_SUPPLIED_HTML"
        assert body["source_sha256"] == hashlib.sha256(source.encode()).hexdigest()
        assert body["finding_count"] == 1
        assert body["findings"][0]["selector"] == "img#hero"
        assert "picture.png" not in response.text
        assert client.app.state.store.conn is not None


def test_offline_html_requires_auth_and_scan_scope(tmp_path):
    with TestClient(create_app(str(tmp_path / "auth.db"), seed=True)) as client:
        unauthenticated = client.post("/v1/offline/html-findings", json={"source_html": "<img>"})
        assert unauthenticated.status_code in {401, 403}
        forbidden = client.post("/v1/offline/html-findings", headers=_auth("scan:read"), json={"source_html": "<img>"})
        assert forbidden.status_code == 403


def test_offline_html_invalid_duplicate_attributes_fail_closed(tmp_path):
    with TestClient(create_app(str(tmp_path / "invalid.db"), seed=True)) as client:
        response = client.post("/v1/offline/html-findings", headers=_auth(), json={"source_html": '<img alt="one" alt="two">'})
        assert response.status_code == 422
        assert response.json()["code"] == "OFFLINE_HTML_INVALID"


def test_offline_html_never_silently_truncates_large_result(tmp_path):
    source = "<main>" + '<img src="a">' * 501 + "</main>"
    with TestClient(create_app(str(tmp_path / "budget.db"), seed=True)) as client:
        response = client.post("/v1/offline/html-findings", headers=_auth(), json={"source_html": source})
        assert response.status_code == 413
        assert response.json()["code"] == "OFFLINE_FINDINGS_BUDGET_EXCEEDED"

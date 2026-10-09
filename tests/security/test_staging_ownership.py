"""Real deployments must never accept the development ownership proof."""
from fastapi.testclient import TestClient
from accessfix_ai.main import create_app
from accessfix_ai.presentation.auth import claims
from accessfix_ai.infrastructure.store import TENANT, USER, SITE


def test_staging_cannot_issue_or_accept_development_ownership(tmp_path, monkeypatch):
    app = create_app(str(tmp_path / "ownership.db"), seed=True)
    app.dependency_overrides[claims] = lambda: {"tenant_id": TENANT, "sub": USER, "scope": "site:verify"}
    monkeypatch.setenv("APP_ENV", "staging")
    with TestClient(app) as client:
        challenge = client.post("/v1/sites/verification-challenges", json={"canonical_origin": "https://example.com", "repository_id": "33333333-3333-3333-3333-333333333333"})
        assert challenge.status_code == 503
        assert challenge.json()["code"] == "OWNERSHIP_VERIFIER_NOT_CONFIGURED"
        assert "X-Development-Challenge-Token" not in challenge.headers
        verification = client.post(f"/v1/sites/{SITE}/verify", json={"challenge_id": "33333333-3333-3333-3333-333333333333", "evidence_token": "synthetic-proof"})
        assert verification.status_code == 503
        with app.state.store.conn(TENANT) as db:
            assert db.execute("SELECT COUNT(*) FROM challenges").fetchone()[0] == 0

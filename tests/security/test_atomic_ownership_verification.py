"""Proof of atomic, single-use site ownership verification."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from accessfix_ai.infrastructure.store import Store, TENANT, SITE
from accessfix_ai.main import create_app
from test_accessfix_flow import hdr


def future_expiry():
    return (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat().replace("+00:00", "Z")


def seed_store(tmp_path):
    store = Store(str(tmp_path / "ownership.sqlite"))
    store.seed()
    return store


def test_a_challenge_is_single_use_even_with_competing_verifiers(tmp_path):
    store = seed_store(tmp_path)
    challenge_id = store.challenge(TENANT, SITE, "synthetic-strong-token", future_expiry())
    start = Barrier(3)

    def consume():
        start.wait()
        return store.verify(TENANT, challenge_id, expected_origin="http://fixture.local")

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(consume)
        second = pool.submit(consume)
        start.wait()
        results = (first.result(timeout=10), second.result(timeout=10))
    assert sum(row is not None for row in results) == 1
    with store.conn() as db:
        row = db.execute("SELECT used_at FROM challenges WHERE tenant_id=? AND id=?", (TENANT, challenge_id)).fetchone()
        assert row["used_at"] is not None


def test_expired_or_replayed_challenge_never_revalidates_a_site(tmp_path):
    store = seed_store(tmp_path)
    expired = store.challenge(TENANT, SITE, "expired", "2000-01-01T00:00:00Z")
    assert store.verify(TENANT, expired, expected_origin="http://fixture.local") is None
    assert store.site(TENANT, SITE)["status"] == "UNVERIFIED"
    with store.conn() as db:
        assert db.execute("SELECT used_at FROM challenges WHERE id=?", (expired,)).fetchone()["used_at"] is None

    valid = store.challenge(TENANT, SITE, "valid", future_expiry())
    assert store.verify(TENANT, valid, expected_origin="http://fixture.local")["status"] == "VERIFIED"
    with store.conn() as db:
        db.execute("UPDATE sites SET status='UNVERIFIED',verified_until=NULL WHERE tenant_id=? AND id=?", (TENANT, SITE))
    assert store.verify(TENANT, valid, expected_origin="http://fixture.local") is None
    assert store.site(TENANT, SITE)["status"] == "UNVERIFIED"


def test_site_origin_change_rolls_back_token_consumption(tmp_path):
    store = seed_store(tmp_path)
    challenge_id = store.challenge(TENANT, SITE, "proof", future_expiry())
    with store.conn() as db:
        db.execute("UPDATE sites SET origin='https://different.example.invalid',status='UNVERIFIED' WHERE tenant_id=? AND id=?", (TENANT, SITE))
    with pytest.raises(ValueError, match="origin changed"):
        store.verify(TENANT, challenge_id, expected_origin="http://fixture.local")
    assert store.site(TENANT, SITE)["status"] == "UNVERIFIED"
    with store.conn() as db:
        assert db.execute("SELECT used_at FROM challenges WHERE id=?", (challenge_id,)).fetchone()["used_at"] is None
    assert store.verify(TENANT, challenge_id, expected_origin="https://different.example.invalid")["status"] == "VERIFIED"


def test_http_race_returns_typed_conflict_not_false_verification(tmp_path, monkeypatch):
    app = create_app(str(tmp_path / "http.sqlite"), seed=True)
    with TestClient(app) as client:
        created = client.post(
            "/v1/sites/verification-challenges",
            headers=hdr("site:verify"),
            json={"canonical_origin": "http://fixture.local",
                  "repository_id": "33333333-3333-3333-3333-333333333333"},
        )
        assert created.status_code == 201, created.text
        original = app.state.store.verify

        def other_request_wins(tenant, challenge_id, expected_origin=None):
            assert original(tenant, challenge_id, expected_origin=expected_origin) is not None
            return original(tenant, challenge_id, expected_origin=expected_origin)

        monkeypatch.setattr(app.state.store, "verify", other_request_wins)
        result = client.post(
            f"/v1/sites/{SITE}/verify",
            headers=hdr("site:verify"),
            json={"challenge_id": created.json()["id"],
                  "evidence_token": created.headers["X-Development-Challenge-Token"]},
        )
        assert result.status_code == 409, result.text
        assert result.json()["code"] == "VERIFICATION_RACE_REJECTED"

from datetime import datetime, timedelta, timezone
import time

import jwt
import pytest
from fastapi.testclient import TestClient

from accessfix_ai.infrastructure.store import SITE, TENANT, USER
from accessfix_ai.main import create_app

SECRET = "forgeworks-development-secret-32-plus"
ISS = "https://issuer.synthetic.invalid"
AUD = "forgeworks-api"
REPO = "a" * 40


@pytest.mark.parametrize("length", [39, 41, 48, 63, 65])
def test_intermediate_or_invalid_revision_lengths_rejected(tmp_path, length):
    with TestClient(create_app(str(tmp_path / "db.sqlite"), seed=True)) as client:
        result = client.post(f"/v1/sites/{SITE}/scans", headers=headers("scan:start"), json={"repo_commit_sha": "a" * length, "paths": ["/"]})
        assert result.status_code == 422
        result = client.post("/v1/fix-proposals/33333333-3333-3333-3333-333333333333/retests", headers=headers("patch:create"), json={"repo_commit_sha": "a" * length, "expected_version": 1})
        assert result.status_code == 422


@pytest.mark.parametrize("paths", [["/other"], ["/", "/"], ["/?page=2"]])
def test_fixture_scope_is_not_silently_replaced(tmp_path, paths):
    with TestClient(create_app(str(tmp_path / "db.sqlite"), seed=True)) as client:
        verified_scan(client)
        with client.app.state.store.conn() as db:
            before = db.execute("SELECT count(*) FROM scans").fetchone()[0]
        result = client.post(f"/v1/sites/{SITE}/scans", headers=headers("scan:start"), json={"repo_commit_sha": REPO, "paths": paths})
        assert result.status_code == 503
        assert result.json()["code"] == "SCAN_SCOPE_UNSUPPORTED"
        with client.app.state.store.conn() as db:
            assert db.execute("SELECT count(*) FROM scans").fetchone()[0] == before


def token(scope: str, tenant: str = TENANT):
    return jwt.encode(
        {"sub": USER, "tenant_id": tenant, "scope": scope, "iss": ISS, "aud": AUD, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        SECRET,
        algorithm="HS256",
    )


def headers(scope: str):
    return {"Authorization": "Bearer " + token(scope)}


def verified_scan(client):
    challenge = client.post(
        "/v1/sites/verification-challenges",
        headers=headers("site:verify"),
        json={"canonical_origin": "http://fixture.local", "repository_id": "33333333-3333-3333-3333-333333333333"},
    )
    assert challenge.status_code == 201
    verified = client.post(
        f"/v1/sites/{SITE}/verify",
        headers=headers("site:verify"),
        json={"challenge_id": challenge.json()["id"], "evidence_token": challenge.headers["X-Development-Challenge-Token"]},
    )
    assert verified.status_code == 200
    scan = client.post(f"/v1/sites/{SITE}/scans", headers=headers("scan:start"), json={"repo_commit_sha": REPO, "paths": ["/"]})
    assert scan.status_code == 202
    for _ in range(50):
        findings = client.get(f"/v1/scans/{scan.json()['id']}/findings", headers=headers("scan:read")).json()["items"]
        if findings:
            return scan.json(), findings[0]
        time.sleep(0.01)
    raise AssertionError("fixture finding was not produced")


def test_finding_evidence_and_source_mapping_are_returned(tmp_path):
    with TestClient(create_app(str(tmp_path / "db.sqlite"), seed=True)) as client:
        _, finding = verified_scan(client)
        assert finding["evidence"]["kind"] == "DOM_SNIPPET"
        assert len(finding["evidence"]["digest_sha256"]) == 64
        assert finding["source_mapping"]["verified"] is True
        assert finding["source_mapping"]["source_revision"] == REPO


def test_remote_scan_and_oversized_scan_fail_closed(tmp_path):
    with TestClient(create_app(str(tmp_path / "db.sqlite"), seed=True)) as client:
        challenge = client.post(
            "/v1/sites/verification-challenges",
            headers=headers("site:verify"),
            json={"canonical_origin": "https://example.com", "repository_id": "33333333-3333-3333-3333-333333333333"},
        )
        assert challenge.status_code == 201
        assert client.post(
            f"/v1/sites/{SITE}/verify",
            headers=headers("site:verify"),
            json={"challenge_id": challenge.json()["id"], "evidence_token": challenge.headers["X-Development-Challenge-Token"]},
        ).status_code == 200
        remote = client.post(f"/v1/sites/{SITE}/scans", headers=headers("scan:start"), json={"repo_commit_sha": REPO, "paths": ["/"]})
        assert remote.status_code == 503
        too_many = client.post(
            f"/v1/sites/{SITE}/scans", headers=headers("scan:start"), json={"repo_commit_sha": REPO, "paths": ["/"] * 21}
        )
        assert too_many.status_code == 422


def test_retest_is_bound_to_proposal_revision(tmp_path):
    with TestClient(create_app(str(tmp_path / "db.sqlite"), seed=True)) as client:
        _, finding = verified_scan(client)
        proposal = client.post(
            f"/v1/findings/{finding['id']}/fix-proposals",
            headers=headers("patch:create"),
            json={"source_mapping_id": finding["source_mapping"]["id"], "alt_text": "Synthetic fixture illustration"},
        ).json()
        wrong = client.post(
            f"/v1/fix-proposals/{proposal['id']}/retests",
            headers=headers("patch:create"),
            json={"repo_commit_sha": "b" * 40, "expected_version": 1},
        )
        assert wrong.status_code == 409 and wrong.json()["code"] == "REVISION_MISMATCH"
        retest = client.post(
            f"/v1/fix-proposals/{proposal['id']}/retests",
            headers=headers("patch:create"),
            json={"repo_commit_sha": REPO, "expected_version": 1},
        )
        assert retest.status_code == 202
        review = client.post(
            f"/v1/fix-proposals/{proposal['id']}/reviews",
            headers=headers("patch:review"),
            json={"patch_sha256": proposal["patch_sha256"], "decision": "approve", "manual_check_status": "passed", "expected_version": retest.json()["version"]},
        )
        assert review.status_code == 201


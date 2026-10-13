from datetime import datetime, timedelta, timezone
import hashlib
import json
import time

import jwt
from fastapi.testclient import TestClient

from accessfix_ai.infrastructure.store import SITE, TENANT, USER
from accessfix_ai.main import create_app

SECRET = "forgeworks-development-secret-32-plus"
ISSUER = "https://issuer.synthetic.invalid"
AUDIENCE = "forgeworks-api"
REPO = "a" * 40
REPOSITORY_ID = "33333333-3333-3333-3333-333333333333"


def headers(scope: str):
    token = jwt.encode(
        {
            "sub": USER,
            "tenant_id": TENANT,
            "scope": scope,
            "iss": ISSUER,
            "aud": AUDIENCE,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def test_fixture_workflow_ownership_job_findings_proposal_retest_review(tmp_path):
    auth = headers("site:verify scan:start scan:read job:read patch:create patch:review")
    with TestClient(create_app(str(tmp_path / "e2e.db"), seed=True)) as client:
        challenge = client.post(
            "/v1/sites/verification-challenges",
            headers=auth,
            json={"canonical_origin": "http://fixture.local", "repository_id": REPOSITORY_ID},
        )
        assert challenge.status_code == 201
        verified = client.post(
            f"/v1/sites/{SITE}/verify",
            headers=auth,
            json={"challenge_id": challenge.json()["id"], "evidence_token": challenge.headers["X-Development-Challenge-Token"]},
        )
        assert verified.status_code == 200 and verified.json()["status"] == "VERIFIED"

        scan_headers = {**auth, "Idempotency-Key": "e2e-scan-fixture-0001"}
        payload = {"repo_commit_sha": REPO, "paths": ["/"]}
        accepted = client.post(f"/v1/sites/{SITE}/scans", headers=scan_headers, json=payload)
        duplicate = client.post(f"/v1/sites/{SITE}/scans", headers=scan_headers, json=payload)
        assert accepted.status_code == duplicate.status_code == 202
        assert accepted.json()["id"] == duplicate.json()["id"]
        reused = client.post(
            f"/v1/sites/{SITE}/scans",
            headers=scan_headers,
            json={"repo_commit_sha": "b" * 40, "paths": ["/"]},
        )
        assert reused.status_code == 409
        assert reused.json()["code"] == "IDEMPOTENCY_KEY_REUSED"

        job = None
        for _ in range(50):
            job_response = client.get(f"/v1/jobs/{accepted.json()['job_id']}", headers=auth)
            assert job_response.status_code == 200
            job = job_response.json()
            if job["state"] in {"SUCCEEDED", "FAILED_TERMINAL", "CANCELLED"}:
                break
            time.sleep(0.01)
        assert job["state"] == "SUCCEEDED"
        assert job["attempt_count"] == 1

        findings = client.get(f"/v1/scans/{accepted.json()['id']}/findings", headers=auth)
        assert findings.status_code == 200
        items = findings.json()["items"]
        assert len(items) == 1
        assert items[0]["manual_check_required"] is True

        proposal_payload = {"source_mapping_id": items[0]["source_mapping"]["id"], "alt_text": "Synthetic fixture illustration"}
        proposal = client.post(f"/v1/findings/{items[0]['id']}/fix-proposals", headers=auth, json=proposal_payload)
        duplicate_proposal = client.post(f"/v1/findings/{items[0]['id']}/fix-proposals", headers=auth, json=proposal_payload)
        assert proposal.status_code == duplicate_proposal.status_code == 201
        assert proposal.json()["id"] == duplicate_proposal.json()["id"]

        proposal_body = proposal.json()
        wrong_revision = client.post(
            f"/v1/fix-proposals/{proposal_body['id']}/retests",
            headers=auth,
            json={"repo_commit_sha": "b" * 40, "expected_version": proposal_body["version"]},
        )
        assert wrong_revision.status_code == 409
        assert wrong_revision.json()["code"] == "REVISION_MISMATCH"

        retest_headers = {**auth, "Idempotency-Key": "e2e-retest-0001"}
        retest_payload = {"repo_commit_sha": proposal_body["base_sha"], "expected_version": proposal_body["version"]}
        retest = client.post(f"/v1/fix-proposals/{proposal_body['id']}/retests", headers=retest_headers, json=retest_payload)
        replayed_retest = client.post(f"/v1/fix-proposals/{proposal_body['id']}/retests", headers=retest_headers, json=retest_payload)
        assert retest.status_code == replayed_retest.status_code == 202
        assert replayed_retest.json() == retest.json()
        assert retest.json()["retest_status"] == "PASSED"
        assert retest.json()["version"] == proposal_body["version"] + 1
        conflicting_retest = client.post(f"/v1/fix-proposals/{proposal_body['id']}/retests", headers=retest_headers, json={"repo_commit_sha": "b" * 40, "expected_version": proposal_body["version"]})
        assert conflicting_retest.status_code == 409
        assert conflicting_retest.json()["code"] == "IDEMPOTENCY_KEY_REUSED"

        stale_retest = client.post(
            f"/v1/fix-proposals/{proposal_body['id']}/retests",
            headers=auth,
            json={"repo_commit_sha": proposal_body["base_sha"], "expected_version": proposal_body["version"]},
        )
        assert stale_retest.status_code == 409
        assert stale_retest.json()["code"] == "STALE_VERSION"

        review_headers = {**auth, "Idempotency-Key": "e2e-review-0001"}
        review_payload = {
            "patch_sha256": proposal_body["patch_sha256"],
            "decision": "approve",
            "manual_check_status": "passed",
            "expected_version": retest.json()["version"],
        }
        review = client.post(f"/v1/fix-proposals/{proposal_body['id']}/reviews", headers=review_headers, json=review_payload)
        replayed_review = client.post(f"/v1/fix-proposals/{proposal_body['id']}/reviews", headers=review_headers, json=review_payload)
        assert review.status_code == replayed_review.status_code == 201
        assert {key: replayed_review.json()[key] for key in replayed_review.json() if key != "created_at"} == {key: review.json()[key] for key in review.json() if key != "created_at"}
        assert review.json()["status"] == "APPROVED"
        conflicting_review = client.post(f"/v1/fix-proposals/{proposal_body['id']}/reviews", headers=review_headers, json={**review_payload, "decision": "reject"})
        assert conflicting_review.status_code == 409
        assert conflicting_review.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
        stale_review = client.post(
            f"/v1/fix-proposals/{proposal_body['id']}/reviews",
            headers=auth,
            json={
                "patch_sha256": proposal_body["patch_sha256"],
                "decision": "approve",
                "manual_check_status": "passed",
                "expected_version": retest.json()["version"],
            },
        )
        assert stale_review.status_code == 409
        assert stale_review.json()["code"] == "STALE_VERSION"

        exported = client.get(f"/v1/scans/{accepted.json()['id']}/evidence-export", headers=auth)
        assert exported.status_code == 200
        assert exported.headers["content-disposition"].startswith("attachment; filename=\"accessfix-evidence-")
        assert exported.headers["cache-control"] == "no-store"
        evidence = exported.json()
        bundle_sha = evidence.pop("bundle_sha256")
        canonical = json.dumps(evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        assert bundle_sha == hashlib.sha256(canonical).hexdigest()
        assert evidence["scope"] == "SYNTHETIC_LOCAL_FIXTURE_ONLY"
        assert evidence["source"]["content_included"] is False
        assert evidence["source"]["revision_verified"] is False
        assert evidence["coverage"]["browser_rendered"] is False
        assert evidence["coverage"]["wcag_conformance_claim"] is False
        assert evidence["findings"][0]["fingerprint"] == items[0]["fingerprint"]
        assert evidence["proposals"][0]["patch_sha256"] == proposal_body["patch_sha256"]
        assert evidence["proposals"][0]["retest_status"] == "PASSED"
        assert evidence["proposals"][0]["content_integrity_verified"] is True
        assert "alt_text_sha256" not in evidence["proposals"][0]
        assert evidence["proposals"][0]["reviews"][0]["actor_id"] == USER
        assert evidence["proposals"][0]["reviews"][0]["decision"] == "approve"
        assert "source_html" not in exported.text and "patch_text" not in exported.text
        assert "Synthetic fixture illustration" not in exported.text


def test_remote_origin_is_visible_and_fail_closed_without_queueing(tmp_path):
    auth = headers("site:verify scan:start")
    with TestClient(create_app(str(tmp_path / "remote.db"), seed=True)) as client:
        challenge = client.post(
            "/v1/sites/verification-challenges",
            headers=auth,
            json={"canonical_origin": "https://example.com", "repository_id": REPOSITORY_ID},
        )
        assert challenge.status_code == 201
        verified = client.post(
            f"/v1/sites/{SITE}/verify",
            headers=auth,
            json={"challenge_id": challenge.json()["id"], "evidence_token": challenge.headers["X-Development-Challenge-Token"]},
        )
        assert verified.status_code == 200
        blocked = client.post(
            f"/v1/sites/{SITE}/scans",
            headers=auth,
            json={"repo_commit_sha": REPO, "paths": ["/"]},
        )
        assert blocked.status_code == 503
        assert blocked.json()["code"] == "REMOTE_BROWSER_BLOCKED"
        with client.app.state.store.conn() as connection:
            assert connection.execute("SELECT COUNT(*) FROM scans").fetchone()[0] == 0

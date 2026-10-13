from datetime import datetime, timedelta, timezone
import hashlib
import time

import jwt
import pytest
from fastapi.testclient import TestClient

from accessfix_ai.infrastructure.store import SITE, TENANT, USER
import accessfix_ai.main as accessfix_main
from accessfix_ai.main import _local_fixture_evidence_export_enabled, create_app

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


@pytest.mark.parametrize(("environment", "enabled"), [
    ("development", True), ("test", True), ("staging", False), ("preview", False), ("production", False),
])
def test_evidence_export_environment_gate(monkeypatch, environment, enabled):
    monkeypatch.setenv("APP_ENV", environment)
    assert _local_fixture_evidence_export_enabled() is enabled


def test_evidence_export_environment_missing_is_disabled(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    assert _local_fixture_evidence_export_enabled() is False


def test_evidence_export_disabled_error_uses_problem_media_type(tmp_path, monkeypatch):
    with TestClient(create_app(str(tmp_path / "disabled.db"), seed=True)) as client:
        scan, _ = verified_scan(client)
        monkeypatch.setattr(accessfix_main, "_local_fixture_evidence_export_enabled", lambda: False)
        response = client.get(f"/v1/scans/{scan['id']}/evidence-export", headers=headers("scan:read"))
        assert response.status_code == 503
        assert response.json()["code"] == "EVIDENCE_EXPORT_DISABLED"
        assert response.headers["content-type"].startswith("application/problem+json")


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
        response = client.get(f"/v1/scans/{scan.json()['id']}/findings", headers=headers("scan:read"))
        assert response.status_code == 200, response.text
        findings = response.json()["items"]
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


def test_evidence_export_is_tenant_scoped_and_requires_scan_read(tmp_path):
    other_tenant = "00000000-0000-0000-0000-000000000002"
    other_user = "00000000-0000-0000-0000-000000000011"
    with TestClient(create_app(str(tmp_path / "db.sqlite"), seed=True)) as client:
        scan, _ = verified_scan(client)
        denied = client.get(f"/v1/scans/{scan['id']}/evidence-export", headers=headers("job:read"))
        assert denied.status_code == 403
        assert denied.json()["code"] == "INSUFFICIENT_SCOPE"
        assert denied.headers["content-type"].startswith("application/problem+json")
        invalid_id = client.get("/v1/scans/not-a-uuid/evidence-export", headers=headers("scan:read"))
        assert invalid_id.status_code == 422
        assert invalid_id.json()["code"] == "INVALID_REQUEST"
        assert invalid_id.headers["content-type"].startswith("application/problem+json")
        with client.app.state.store.conn() as db:
            db.execute("INSERT INTO tenants VALUES(?,?,?)", (other_tenant, "other-tenant", "ACTIVE"))
            db.execute("INSERT INTO memberships VALUES(?,?,?,?)", (other_tenant, other_user, "viewer", "ACTIVE"))
        other_token = jwt.encode(
            {"sub": other_user, "tenant_id": other_tenant, "scope": "scan:read", "iss": ISS, "aud": AUD,
             "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
            SECRET,
            algorithm="HS256",
        )
        hidden = client.get(f"/v1/scans/{scan['id']}/evidence-export", headers={"Authorization": f"Bearer {other_token}"})
        assert hidden.status_code == 404
        assert hidden.json()["code"] == "RESOURCE_NOT_FOUND"


def test_evidence_snapshot_passes_tenant_explicitly_to_database(tmp_path, monkeypatch):
    with TestClient(create_app(str(tmp_path / "tenant-connection.db"), seed=True)) as client:
        scan, _ = verified_scan(client)
        store = client.app.state.store
        original_conn = store.conn
        seen_tenants = []

        def require_explicit_tenant(tenant=None, *, repeatable_read=False):
            assert tenant == TENANT
            seen_tenants.append((tenant, repeatable_read))
            return original_conn(tenant, repeatable_read=repeatable_read)

        monkeypatch.setattr(store, "conn", require_explicit_tenant)
        snapshot = store.scan_evidence_export(TENANT, scan["id"])
        assert snapshot["findings_set_integrity_verified"] is True
        listing_snapshot = store.scan_findings_snapshot(TENANT, scan["id"])
        assert listing_snapshot["scan"]["status"] == "SUCCEEDED"
        assert len(listing_snapshot["findings"]) == 1 and listing_snapshot["source"] is not None
        assert seen_tenants == [(TENANT, True), (TENANT, False)]


@pytest.mark.parametrize("tamper_target", [
    "source", "proposal_patch", "proposal_alt_text", "proposal_null_alt_text",
    "finding_severity", "finding_manual_required", "finding_manual_required_invalid",
])
def test_evidence_export_fails_closed_on_tampered_bytes(tmp_path, tamper_target):
    with TestClient(create_app(str(tmp_path / f"{tamper_target}.db"), seed=True)) as client:
        scan, finding = verified_scan(client)
        if tamper_target.startswith("proposal_"):
            proposal = client.post(
                f"/v1/findings/{finding['id']}/fix-proposals",
                headers=headers("patch:create"),
                json={"source_mapping_id": finding["source_mapping"]["id"], "alt_text": "Synthetic fixture illustration"},
            )
            assert proposal.status_code == 201
            with client.app.state.store.conn() as db:
                if tamper_target == "proposal_patch":
                    db.execute("UPDATE proposal_sources SET patch_text=? WHERE tenant_id=? AND proposal_id=?", ("tampered", TENANT, proposal.json()["id"]))
                elif tamper_target == "proposal_alt_text":
                    db.execute("UPDATE proposal_sources SET alt_text=? WHERE tenant_id=? AND proposal_id=?", ("tampered alt text", TENANT, proposal.json()["id"]))
                else:
                    db.execute("UPDATE proposal_sources SET alt_text=NULL WHERE tenant_id=? AND proposal_id=?", (TENANT, proposal.json()["id"]))
        elif tamper_target == "finding_severity":
            with client.app.state.store.conn() as db:
                db.execute("UPDATE findings SET severity='MINOR' WHERE tenant_id=? AND id=?", (TENANT, finding["id"]))
        elif tamper_target == "finding_manual_required":
            with client.app.state.store.conn() as db:
                db.execute("UPDATE findings SET manual_required=0 WHERE tenant_id=? AND id=?", (TENANT, finding["id"]))
        elif tamper_target == "finding_manual_required_invalid":
            with client.app.state.store.conn() as db:
                db.execute("UPDATE findings SET manual_required=2 WHERE tenant_id=? AND id=?", (TENANT, finding["id"]))
        else:
            with client.app.state.store.conn() as db:
                db.execute("UPDATE scan_sources SET source_html='tampered' WHERE tenant_id=? AND scan_id=?", (TENANT, scan["id"]))
        exported = client.get(f"/v1/scans/{scan['id']}/evidence-export", headers=headers("scan:read"))
        assert exported.status_code == 409
        assert exported.json()["code"] == "SOURCE_INTEGRITY_FAILED"
        assert exported.headers["content-type"].startswith("application/problem+json")
        if tamper_target == "finding_manual_required_invalid":
            listed = client.get(f"/v1/scans/{scan['id']}/findings", headers=headers("scan:read"))
            assert listed.status_code == 409
            assert listed.json()["code"] == "SOURCE_INTEGRITY_FAILED"


def test_wrong_selector_is_not_exported_as_verified_source_mapping(tmp_path):
    with TestClient(create_app(str(tmp_path / "selector.db"), seed=True)) as client:
        scan, finding = verified_scan(client)
        with client.app.state.store.conn() as db:
            db.execute("UPDATE findings SET selector='img#forged' WHERE tenant_id=? AND id=?", (TENANT, finding["id"]))
        findings = client.get(f"/v1/scans/{scan['id']}/findings", headers=headers("scan:read"))
        evidence = client.get(f"/v1/scans/{scan['id']}/evidence-export", headers=headers("scan:read"))
        assert findings.status_code == evidence.status_code == 409
        assert findings.json()["code"] == evidence.json()["code"] == "SOURCE_INTEGRITY_FAILED"


def test_evidence_export_rejects_float_metadata(tmp_path):
    with TestClient(create_app(str(tmp_path / "float.db"), seed=True)) as client:
        scan, _ = verified_scan(client)
        with client.app.state.store.conn() as db:
            db.execute("UPDATE scans SET attempt_count=1.5 WHERE tenant_id=? AND id=?", (TENANT, scan["id"]))
        response = client.get(f"/v1/scans/{scan['id']}/evidence-export", headers=headers("scan:read"))
        assert response.status_code == 409
        assert response.json()["code"] == "EVIDENCE_SCHEMA_INVALID"


@pytest.mark.parametrize("tamper_target", ["finding_uuid", "negative_attempt_count"])
def test_evidence_export_rejects_semantically_invalid_manifest(tmp_path, tamper_target):
    with TestClient(create_app(str(tmp_path / f"schema-{tamper_target}.db"), seed=True)) as client:
        scan, finding = verified_scan(client)
        with client.app.state.store.conn() as db:
            if tamper_target == "finding_uuid":
                db.execute("UPDATE findings SET id='not-a-uuid' WHERE tenant_id=? AND id=?", (TENANT, finding["id"]))
            else:
                db.execute("UPDATE scans SET attempt_count=-1 WHERE tenant_id=? AND id=?", (TENANT, scan["id"]))
        response = client.get(f"/v1/scans/{scan['id']}/evidence-export", headers=headers("scan:read"))
        assert response.status_code == 409
        assert response.json()["code"] == "EVIDENCE_SCHEMA_INVALID"
        assert response.headers["content-type"].startswith("application/problem+json")


def test_findings_and_export_fail_closed_on_scanner_rejection(tmp_path):
    with TestClient(create_app(str(tmp_path / "invalid-source.db"), seed=True)) as client:
        scan, _ = verified_scan(client)
        invalid_source = '<html><img id="invalid"></html>\x00'
        with client.app.state.store.conn() as db:
            db.execute(
                "UPDATE scan_sources SET source_html=?,source_sha=? WHERE tenant_id=? AND scan_id=?",
                (invalid_source, hashlib.sha256(invalid_source.encode()).hexdigest(), TENANT, scan["id"]),
            )
        findings = client.get(f"/v1/scans/{scan['id']}/findings", headers=headers("scan:read"))
        exported = client.get(f"/v1/scans/{scan['id']}/evidence-export", headers=headers("scan:read"))
        assert findings.status_code == exported.status_code == 409
        assert findings.json()["code"] == exported.json()["code"] == "SOURCE_INTEGRITY_FAILED"
        assert findings.headers["content-type"].startswith("application/problem+json")
        assert exported.headers["content-type"].startswith("application/problem+json")


def test_evidence_export_fails_closed_when_stored_finding_is_deleted(tmp_path):
    with TestClient(create_app(str(tmp_path / "deleted-finding.db"), seed=True)) as client:
        scan, finding = verified_scan(client)
        with client.app.state.store.conn() as db:
            db.execute("DELETE FROM findings WHERE tenant_id=? AND id=?", (TENANT, finding["id"]))
        exported = client.get(f"/v1/scans/{scan['id']}/evidence-export", headers=headers("scan:read"))
        listed = client.get(f"/v1/scans/{scan['id']}/findings", headers=headers("scan:read"))
        assert exported.status_code == listed.status_code == 409
        assert exported.json()["code"] == listed.json()["code"] == "SOURCE_INTEGRITY_FAILED"


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

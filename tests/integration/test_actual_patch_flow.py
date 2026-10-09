import hashlib
import subprocess
import pytest
from fastapi.testclient import TestClient
from accessfix_ai.main import create_app
from test_accessfix_hardening import verified_scan, headers, REPO


def test_api_returns_applicable_patch_and_retest_rejects_tampering(tmp_path):
    with TestClient(create_app(str(tmp_path / "db.sqlite"), seed=True)) as client:
        scan, finding = verified_scan(client)
        assert finding["source_mapping"]["revision_verified"] is False
        body = {"source_mapping_id": finding["id"], "alt_text": "Owner-authored fixture illustration"}
        url = f"/v1/findings/{finding['id']}/fix-proposals"
        command_headers = {**headers("patch:create"), "Idempotency-Key": "actual-patch-command-001"}
        response = client.post(url, headers=command_headers, json=body)
        assert response.status_code == 201
        proposal = response.json()
        assert hashlib.sha256(proposal["patch"].encode()).hexdigest() == proposal["patch_sha256"]
        source = client.app.state.store.scan_source("00000000-0000-0000-0000-000000000001", scan["id"])
        (tmp_path / "source.html").write_bytes(source["source_html"].encode())
        subprocess.run(["git", "apply", "--no-index", "-"], input=proposal["patch"].encode(), cwd=tmp_path, check=True, capture_output=True)
        assert b'alt="Owner-authored fixture illustration"' in (tmp_path / "source.html").read_bytes()
        assert client.post(url, headers=headers("patch:create"), json=body).json()["id"] == proposal["id"]
        assert client.post(url, headers=command_headers, json=body).json()["id"] == proposal["id"]
        conflict = client.post(url, headers=command_headers, json={**body, "alt_text": "Changed command"})
        assert conflict.status_code == 409 and conflict.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
        assert client.post(url, headers=headers("patch:create"), json={**body, "alt_text": "Different label"}).status_code == 409
        with client.app.state.store.conn() as db:
            db.execute("UPDATE proposal_sources SET patched_html=? WHERE proposal_id=?", ("tampered", proposal["id"]))
        result = client.post(f"/v1/fix-proposals/{proposal['id']}/retests", headers=headers("patch:create"), json={"repo_commit_sha": REPO, "expected_version": 1})
        assert result.status_code == 409 and result.json()["code"] == "SOURCE_INTEGRITY_FAILED"
        assert client.app.state.store.proposal_get("00000000-0000-0000-0000-000000000001", proposal["id"])["retest_status"] == "NOT_RUN"

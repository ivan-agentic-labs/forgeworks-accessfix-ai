"""A digest-matching source patch must still fix the recorded accessibility rule."""
from fastapi.testclient import TestClient

import accessfix_ai.infrastructure.store as store_module
from accessfix_ai.main import create_app
from accessfix_ai.infrastructure.store import TENANT
from test_accessfix_hardening import REPO, headers, verified_scan


def test_patch_integrity_alone_cannot_pass_semantic_accessibility_retest(tmp_path, monkeypatch):
    with TestClient(create_app(str(tmp_path / "retest.sqlite"), seed=True)) as client:
        _, finding = verified_scan(client)
        proposal_response = client.post(
            f"/v1/findings/{finding['id']}/fix-proposals",
            headers=headers("patch:create"),
            json={
                "source_mapping_id": finding["id"],
                "alt_text": "Reviewer-authored synthetic photo description",
            },
        )
        assert proposal_response.status_code == 201
        proposal = proposal_response.json()
        original_analyzer = store_module.image_alt_findings

        # Simulate an analyzer confirming the *same* finding survives despite
        # the patched bytes matching the signed source snapshot.
        monkeypatch.setattr(
            store_module, "image_alt_findings",
            lambda patched_html: [{"selector": finding["selector"]}],
        )
        url = f"/v1/fix-proposals/{proposal['id']}/retests"
        body = {"repo_commit_sha": REPO, "expected_version": proposal["version"]}
        failed = client.post(url, headers=headers("patch:create"), json=body)
        assert failed.status_code == 409
        assert failed.json()["code"] == "RETEST_FINDING_PERSISTS"
        unchanged = client.app.state.store.proposal_get(TENANT, proposal["id"])
        assert unchanged["retest_status"] == "NOT_RUN"
        assert unchanged["version"] == proposal["version"]

        # A successful retry only occurs when the *real deterministic rule*
        # finds that this exact selector no longer violates image-alt.
        monkeypatch.setattr(store_module, "image_alt_findings", original_analyzer)
        passing = client.post(url, headers=headers("patch:create"), json=body)
        assert passing.status_code == 202, passing.text
        assert passing.json()["retest_status"] == "PASSED"
        assert passing.json()["version"] == proposal["version"] + 1

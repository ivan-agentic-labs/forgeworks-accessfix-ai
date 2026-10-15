"""Local, synthetic coverage for docs/verification/TEST_PLAN.md AX-T01..AX-T06.

These tests never contact a provider, IdP, storage service, remote site, or
browser service.  Network safety cases use injected DNS answers and the API
cases use the disposable SQLite fixture store.
"""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from accessfix_ai.domain.evidence_manifest import EvidenceExport
from accessfix_ai.domain.static_html import image_alt_findings
from accessfix_ai.domain.target_policy import validate_redirect_chain
from accessfix_ai.infrastructure.store import SITE, TENANT
from accessfix_ai.main import create_app
from test_accessfix_hardening import REPO, headers, verified_scan
from test_evidence_manifest_schema import valid_manifest


def test_ax_t01_redirect_to_loopback_is_rejected_before_egress():
    """A synthetic HTTP redirect chain cannot pivot from the verified origin."""
    queried_hosts = []

    def resolver(host):
        queried_hosts.append(host)
        return ["93.184.216.34"]

    with pytest.raises(ValueError, match="redirect leaves verified origin"):
        validate_redirect_chain(
            ["https://owned.example.test/", "https://127.0.0.1/admin"],
            "https://owned.example.test",
            resolver,
        )

    # Origin validation runs before DNS resolution, so the prohibited hop
    # cannot trigger an outbound lookup or a browser connection.
    assert queried_hosts == []


def test_ax_t02_dns_rebinding_to_metadata_is_rejected_fail_closed():
    """Injected DNS answers model a public-to-metadata rebinding without I/O."""
    answers = iter([
        ["93.184.216.34"],  # verified-origin baseline
        ["93.184.216.34"],  # first hop
        ["169.254.169.254"],  # metadata endpoint after rebinding
    ])
    queried_hosts = []

    def resolver(host):
        queried_hosts.append(host)
        return next(answers)

    with pytest.raises(ValueError, match="private, loopback, link-local, or reserved"):
        validate_redirect_chain(
            [
                "https://owned.example.test/",
                "https://owned.example.test/next",
                "https://owned.example.test/final",
            ],
            "https://owned.example.test",
            resolver,
        )

    assert queried_hosts == ["owned.example.test"] * 3


def test_ax_t03_expired_ownership_challenge_cannot_start_scan(tmp_path):
    """An expired synthetic ownership token leaves the site unverified."""
    with TestClient(create_app(str(tmp_path / "expired-ownership.sqlite"), seed=True)) as client:
        challenge = client.post(
            "/v1/sites/verification-challenges",
            headers=headers("site:verify"),
            json={
                "canonical_origin": "http://fixture.local",
                "repository_id": "33333333-3333-3333-3333-333333333333",
            },
        )
        assert challenge.status_code == 201
        token = challenge.headers["X-Development-Challenge-Token"]

        # Expiry is changed only inside the disposable local database; no clock
        # sleeps or external ownership verifier are involved.
        with client.app.state.store.conn() as db:
            db.execute(
                "UPDATE challenges SET expires_at=? WHERE id=?",
                ("2000-01-01T00:00:00Z", challenge.json()["id"]),
            )

        verify = client.post(
            f"/v1/sites/{SITE}/verify",
            headers=headers("site:verify"),
            json={"challenge_id": challenge.json()["id"], "evidence_token": token},
        )
        assert verify.status_code == 400
        assert verify.json()["code"] == "VERIFICATION_FAILED"

        scan = client.post(
            f"/v1/sites/{SITE}/scans",
            headers=headers("scan:start"),
            json={"repo_commit_sha": REPO, "paths": ["/"]},
        )
        assert scan.status_code == 403
        assert scan.json()["code"] == "OWNERSHIP_REQUIRED"


def test_ax_t04_empty_local_rule_result_never_claims_wcag_certification():
    """An empty supported-rule result remains explicitly non-conformance."""
    source = b"<main><h1>Accessible-looking synthetic fixture</h1></main>"
    assert image_alt_findings(source) == []

    payload = deepcopy(valid_manifest())
    payload["findings"] = []
    payload["proposals"] = []
    manifest = EvidenceExport.model_validate(payload)
    assert manifest.findings == []
    assert manifest.coverage.wcag_conformance_claim is False
    assert "NOT_A_WCAG_CONFORMANCE_CLAIM" in manifest.limitations


def test_ax_t05_approved_patch_mutation_fails_closed_at_evidence_gate(tmp_path):
    """Changing persisted patch bytes after approval invalidates the export."""
    with TestClient(create_app(str(tmp_path / "post-approval-mutation.sqlite"), seed=True)) as client:
        scan, finding = verified_scan(client)
        proposal_response = client.post(
            f"/v1/findings/{finding['id']}/fix-proposals",
            headers=headers("patch:create"),
            json={"source_mapping_id": finding["id"], "alt_text": "Synthetic approved label"},
        )
        assert proposal_response.status_code == 201
        proposal = proposal_response.json()

        retest = client.post(
            f"/v1/fix-proposals/{proposal['id']}/retests",
            headers=headers("patch:create"),
            json={"repo_commit_sha": proposal["base_sha"], "expected_version": proposal["version"]},
        )
        assert retest.status_code == 202
        review = client.post(
            f"/v1/fix-proposals/{proposal['id']}/reviews",
            headers=headers("patch:review"),
            json={
                "patch_sha256": proposal["patch_sha256"],
                "decision": "approve",
                "manual_check_status": "passed",
                "expected_version": retest.json()["version"],
            },
        )
        assert review.status_code == 201
        assert review.json()["status"] == "APPROVED"

        with client.app.state.store.conn() as db:
            db.execute(
                "UPDATE proposal_sources SET patch_text=? WHERE tenant_id=? AND proposal_id=?",
                ("tampered after approval", TENANT, proposal["id"]),
            )

        export = client.get(
            f"/v1/scans/{scan['id']}/evidence-export",
            headers=headers("scan:read"),
        )
        assert export.status_code == 409
        assert export.json()["code"] == "SOURCE_INTEGRITY_FAILED"


def test_ax_t06_failed_manual_keyboard_review_rejects_after_static_retest(tmp_path):
    """A static/axe-like pass cannot override a failed manual keyboard gate."""
    with TestClient(create_app(str(tmp_path / "keyboard-review.sqlite"), seed=True)) as client:
        _, finding = verified_scan(client)
        proposal_response = client.post(
            f"/v1/findings/{finding['id']}/fix-proposals",
            headers=headers("patch:create"),
            json={"source_mapping_id": finding["id"], "alt_text": "Synthetic keyboard-check label"},
        )
        assert proposal_response.status_code == 201
        proposal = proposal_response.json()

        retest = client.post(
            f"/v1/fix-proposals/{proposal['id']}/retests",
            headers=headers("patch:create"),
            json={"repo_commit_sha": proposal["base_sha"], "expected_version": proposal["version"]},
        )
        assert retest.status_code == 202
        assert retest.json()["retest_status"] == "PASSED"

        review = client.post(
            f"/v1/fix-proposals/{proposal['id']}/reviews",
            headers=headers("patch:review"),
            json={
                "patch_sha256": proposal["patch_sha256"],
                "decision": "approve",
                "manual_check_status": "failed",
                "expected_version": retest.json()["version"],
            },
        )
        assert review.status_code == 201
        assert review.json()["status"] == "REJECTED"

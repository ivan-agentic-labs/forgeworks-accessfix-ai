from copy import deepcopy

import pytest
from pydantic import ValidationError

from accessfix_ai.domain.evidence_manifest import EvidenceExport


SCAN_ID = "11111111-1111-1111-1111-111111111111"
SITE_ID = "22222222-2222-2222-2222-222222222222"
FINDING_ID = "33333333-3333-3333-3333-333333333333"
PROPOSAL_ID = "44444444-4444-4444-4444-444444444444"
REVISION = "a" * 40


def valid_manifest():
    return {
        "schema_version": "forgeworks.accessfix.evidence/v1",
        "product": "accessfix-ai",
        "scope": "SYNTHETIC_LOCAL_FIXTURE_ONLY",
        "exported_at": "2026-10-13T09:00:00Z",
        "scan": {
            "id": SCAN_ID,
            "status": "SUCCEEDED",
            "site_id": SITE_ID,
            "repo_commit_sha": REVISION,
            "revision_verified": False,
            "network_policy_sha256": "b" * 64,
            "created_at": "2026-10-13T08:59:00Z",
            "attempt_count": 1,
        },
        "source": {
            "kind": "LOCAL_FIXTURE",
            "digest_sha256": "c" * 64,
            "byte_length": 100,
            "content_included": False,
            "revision_verified": False,
        },
        "coverage": {
            "scan_mode": "STATIC_LOCAL_HTML_FIXTURE",
            "paths": ["/"],
            "pages_evaluated": 1,
            "rule_ids_evaluated": ["image-alt"],
            "browser_rendered": False,
            "wcag_conformance_claim": False,
        },
        "findings": [
            {
                "id": FINDING_ID,
                "scan_id": SCAN_ID,
                "rule_id": "image-alt",
                "severity": "SERIOUS",
                "selector": "img#fixture",
                "fingerprint": "d" * 64,
                "manual_check_required": True,
                "evidence": {"kind": "DOM_SNIPPET", "digest_sha256": "e" * 64},
                "source_mapping": {
                    "id": FINDING_ID,
                    "verified": True,
                    "source_revision": REVISION,
                    "revision_verified": False,
                    "source_kind": "LOCAL_FIXTURE",
                },
            }
        ],
        "proposals": [
            {
                "id": PROPOSAL_ID,
                "finding_id": FINDING_ID,
                "base_sha": REVISION,
                "patch_sha256": "f" * 64,
                "source_sha256": "a" * 64,
                "patched_source_sha256": "b" * 64,
                "content_integrity_verified": True,
                "status": "APPROVED",
                "retest_status": "OK",
                "version": 2,
                "reviews": [],
            }
        ],
        "limitations": [
            "SOURCE_REVISION_NOT_VERIFIED",
            "RAW_SOURCE_AND_PATCH_CONTENT_OMITTED",
            "NOT_SIGNED_OR_IMMUTABLE",
            "NOT_A_WCAG_CONFORMANCE_CLAIM",
        ],
        "bundle_sha256": "0" * 64,
    }


@pytest.mark.parametrize(
    ("path", "invalid_value"),
    [
        (("coverage", "pages_evaluated"), True),
        (("scan", "revision_verified"), 0),
        (("source", "content_included"), 0),
        (("coverage", "browser_rendered"), 0),
        (("proposals", 0, "content_integrity_verified"), 1),
    ],
)
def test_manifest_const_requires_exact_json_primitive_type(path, invalid_value):
    payload = valid_manifest()
    EvidenceExport.model_validate(payload)
    corrupted = deepcopy(payload)
    target = corrupted
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = invalid_value
    with pytest.raises(ValidationError):
        EvidenceExport.model_validate(corrupted)


@pytest.mark.parametrize("value", [
    "2026-10-13T09:00:00.1234567Z",
    "2026-10-13T09:00:00.123456789+07:00",
    "2026-10-13T09:00:00.Z",
])
def test_evidence_timestamp_rejects_ambiguous_precision(value):
    payload = valid_manifest()
    payload["exported_at"] = value
    with pytest.raises(ValidationError):
        EvidenceExport.model_validate(payload)


@pytest.mark.parametrize("value", [
    "2026-10-13T09:00:00Z",
    "2026-10-13T09:00:00.123456+07:00",
    "2026-10-13T09:00:00.1+00:00",
])
def test_evidence_timestamp_accepts_unambiguous_rfc3339_precision(value):
    payload = valid_manifest()
    payload["exported_at"] = value
    assert EvidenceExport.model_validate(payload).exported_at == value

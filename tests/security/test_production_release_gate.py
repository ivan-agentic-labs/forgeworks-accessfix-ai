"""Synthetic signatures exercise validation; these are not actual approvals."""
import base64
import copy
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from accessfix_ai.presentation.release_gate import (
    REQUIRED_CONTROLS, ReleaseRejected, canonical_payload, validate_receipt,
)

NOW = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)


@pytest.fixture
def receipt():
    key = Ed25519PrivateKey.generate()
    public = key.public_key()
    pem = public.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    payload = {"schema": "forgeworks-production-acceptance-v1", "product": "accessfix-ai",
               "environment": "production", "revision_sha": "a" * 40,
               "runtime_manifest_sha256": "b" * 64,
               "infrastructure": {"railway_project_id": "11111111-1111-4111-8111-111111111111",
                                  "railway_environment_id": "22222222-2222-4222-8222-222222222222",
                                  "supabase_project_ref": "abcdefghijklmnopqrst"},
               "issued_at": "2026-10-12T11:00:00Z", "expires_at": "2026-10-13T11:00:00Z",
               "controls": [{"id": control, "status": "PASS",
                             "evidence_uri": "https://evidence.synthetic.invalid/review",
                             "evidence_sha256": "c" * 64, "reviewer": "Synthetic test reviewer"}
                            for control in sorted(REQUIRED_CONTROLS)]}
    expected = {k: payload[k] for k in ("product", "environment", "revision_sha",
                                       "runtime_manifest_sha256", "infrastructure")}
    key_id = hashlib.sha256(public.public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)).hexdigest()
    def signed(candidate):
        return json.dumps({"algorithm": "Ed25519", "key_id": key_id, "payload": candidate,
                           "signature": base64.urlsafe_b64encode(key.sign(canonical_payload(candidate))).decode()}).encode()
    return payload, expected, pem, signed


def test_synthetic_current_trusted_receipt_validates(receipt):
    payload, expected, pem, signed = receipt
    result = validate_receipt(signed(payload), pem, expected, now=NOW)
    assert result["result"] == "ACCEPTANCE_RECEIPT_VERIFIED"
    assert result["control_count"] == 11


def test_tampered_signature_and_untrusted_key_rejected(receipt):
    payload, expected, pem, signed = receipt
    envelope = json.loads(signed(payload))
    envelope["payload"]["revision_sha"] = "d" * 40
    with pytest.raises(ReleaseRejected):
        validate_receipt(json.dumps(envelope).encode(), pem, expected, now=NOW)
    other = Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    with pytest.raises(ReleaseRejected):
        validate_receipt(signed(payload), other, expected, now=NOW)


@pytest.mark.parametrize("field,value", [
    ("product", "wrong-product"), ("environment", "staging"), ("revision_sha", "d" * 40),
    ("runtime_manifest_sha256", "d" * 64),
    ("infrastructure", {"railway_project_id": "wrong", "railway_environment_id": "wrong",
                        "supabase_project_ref": "wrong"}),
])
def test_signed_wrong_release_target_rejected(receipt, field, value):
    payload, expected, pem, signed = receipt
    payload[field] = value
    with pytest.raises(ReleaseRejected, match="TARGET_MISMATCH"):
        validate_receipt(signed(payload), pem, expected, now=NOW)


@pytest.mark.parametrize("status", ["OPEN", "FAIL", "BLOCKED", True])
def test_signed_unpassed_control_rejected(receipt, status):
    payload, expected, pem, signed = receipt
    payload["controls"][0]["status"] = status
    with pytest.raises(ReleaseRejected):
        validate_receipt(signed(payload), pem, expected, now=NOW)


@pytest.mark.parametrize("mutation", ["missing", "duplicate"])
def test_signed_missing_or_duplicate_control_rejected(receipt, mutation):
    payload, expected, pem, signed = receipt
    if mutation == "missing":
        payload["controls"].pop()
    else:
        payload["controls"][-1] = copy.deepcopy(payload["controls"][0])
    with pytest.raises(ReleaseRejected):
        validate_receipt(signed(payload), pem, expected, now=NOW)


@pytest.mark.parametrize("field,value", [
    ("issued_at", "2026-10-12T13:00:00Z"),
    ("expires_at", "2026-10-12T12:00:00Z"),
    ("issued_at", "2026-10-12T11:00:00+00:00"),
    ("expires_at", "2026-10-40T11:00:00Z"),
])
def test_signed_future_expired_or_ambiguous_time_rejected(receipt, field, value):
    payload, expected, pem, signed = receipt
    payload[field] = value
    with pytest.raises(ReleaseRejected):
        validate_receipt(signed(payload), pem, expected, now=NOW)


@pytest.mark.parametrize("uri", ["http://evidence.invalid/review",
                              "https://" + "user:password" + "@" + "evidence.invalid/review",
                              "https://evidence.invalid/review?token=private",
                              "https://evidence.invalid/review#fragment"])
def test_evidence_uri_cannot_transport_credentials(receipt, uri):
    payload, expected, pem, signed = receipt
    payload["controls"][0]["evidence_uri"] = uri
    with pytest.raises(ReleaseRejected):
        validate_receipt(signed(payload), pem, expected, now=NOW)


def test_duplicate_json_and_unsigned_template_rejected(receipt):
    payload, expected, pem, signed = receipt
    raw = signed(payload).replace(b'{"algorithm":', b'{"algorithm":"Ed25519","algorithm":', 1)
    with pytest.raises(ReleaseRejected, match="DUPLICATE_JSON"):
        validate_receipt(raw, pem, expected, now=NOW)
    template = Path(__file__).resolve().parents[2] / "infra/environments/production/acceptance-template.json"
    with pytest.raises(ReleaseRejected):
        validate_receipt(template.read_bytes(), pem, expected, now=NOW)


def load_entrypoint():
    path = Path(__file__).resolve().parents[2] / "scripts/start_service.py"
    spec = importlib.util.spec_from_file_location("release_start_service_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_staging_cannot_be_relabelled_production(monkeypatch):
    module = load_entrypoint()
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_MODE", "supabase")
    monkeypatch.setenv("ACCESSFIX_DATABASE_URL", "postgresql://runtime-placeholder")
    monkeypatch.setenv("ACCESSFIX_SEED_FIXTURE", "0")
    monkeypatch.delenv("DEV_AUTH_SECRET", raising=False)
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "a" * 40)
    monkeypatch.delenv("FORGEWORKS_RELEASE_SHA", raising=False)
    monkeypatch.setenv("RAILWAY_PROJECT_ID", module.STAGING_PROJECT)
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_ID", module.STAGING_ENVIRONMENT)
    monkeypatch.setenv("SUPABASE_URL", f"https://{module.STAGING_SUPABASE}.supabase.co")
    with pytest.raises(ValueError, match="SEPARATE_PRODUCTION"):
        module.validate_configuration()


@pytest.fixture
def forgeworks_staging(monkeypatch):
    module = load_entrypoint()
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("AUTH_MODE", "supabase")
    monkeypatch.setenv("ACCESSFIX_DATABASE_URL", "postgresql://runtime-placeholder")
    monkeypatch.setenv("ACCESSFIX_SEED_FIXTURE", "0")
    monkeypatch.delenv("DEV_AUTH_SECRET", raising=False)
    monkeypatch.setenv("RAILWAY_PROJECT_ID", module.STAGING_PROJECT)
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_ID", module.STAGING_ENVIRONMENT)
    monkeypatch.setenv("SUPABASE_URL", f"https://{module.STAGING_SUPABASE}.supabase.co")
    return module


def test_staging_accepts_exact_forgeworks_infrastructure(forgeworks_staging):
    assert forgeworks_staging.validate_configuration() == {
        "environment": "staging", "acceptance": "NOT_APPLICABLE"}


@pytest.mark.parametrize("key", ["RAILWAY_PROJECT_ID", "RAILWAY_ENVIRONMENT_ID"])
def test_staging_rejects_other_railway_target(forgeworks_staging, monkeypatch, key):
    monkeypatch.setenv(key, "00000000-0000-4000-8000-000000000000")
    with pytest.raises(ValueError, match="STAGING_RAILWAY_TARGET_MISMATCH"):
        forgeworks_staging.validate_configuration()


@pytest.mark.parametrize("url", [
    "http://fljekuwplgkrpdoajyhn.supabase.co",
    "https://another-project.supabase.co",
    "https://user@fljekuwplgkrpdoajyhn.supabase.co",
    "https://fljekuwplgkrpdoajyhn.supabase.co/rest/v1",
    "https://fljekuwplgkrpdoajyhn.supabase.co?token=1",
    "https://fljekuwplgkrpdoajyhn.supabase.co:443",
    "",
])
def test_staging_rejects_other_or_unsafe_supabase(forgeworks_staging, monkeypatch, url):
    monkeypatch.setenv("SUPABASE_URL", url)
    with pytest.raises(ValueError, match="STAGING_SUPABASE_TARGET_MISMATCH"):
        forgeworks_staging.validate_configuration()


def test_staging_rejects_missing_railway_binding(forgeworks_staging, monkeypatch):
    monkeypatch.delenv("RAILWAY_ENVIRONMENT_ID")
    with pytest.raises(ValueError, match="STAGING_RAILWAY_TARGET_MISMATCH"):
        forgeworks_staging.validate_configuration()

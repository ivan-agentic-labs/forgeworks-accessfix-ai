"""Verify a trusted operator's signed acceptance; never mint an approval."""
from __future__ import annotations

import base64
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

MAX_RECEIPT_BYTES = 64 * 1024
REQUIRED_CONTROLS = frozenset({
    "authenticated-own-tenant", "authenticated-cross-tenant", "session-revocation",
    "product-integration", "storage-lifecycle", "load-slo", "restore-dr",
    "security-review", "domain-review", "privacy-legal", "owner-release",
})


class ReleaseRejected(ValueError):
    pass


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReleaseRejected("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def reject_constant(value):
    raise ReleaseRejected("NONFINITE_JSON_VALUE")


def canonical_payload(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def reviewed_time(value) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise ReleaseRejected("ACCEPTANCE_TIME_FORMAT")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise ReleaseRejected("ACCEPTANCE_TIME_FORMAT") from None


def validate_receipt(raw: bytes, public_key_pem: bytes, expected: dict,
                     now: datetime | None = None) -> dict:
    if not 1 <= len(raw) <= MAX_RECEIPT_BYTES or not 1 <= len(public_key_pem) <= 16384:
        raise ReleaseRejected("ACCEPTANCE_SIZE_LIMIT")
    try:
        envelope = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ReleaseRejected("ACCEPTANCE_JSON_INVALID") from None
    if not isinstance(envelope, dict) or set(envelope) != {
            "algorithm", "key_id", "payload", "signature"} or envelope["algorithm"] != "Ed25519":
        raise ReleaseRejected("ACCEPTANCE_ENVELOPE_INVALID")
    try:
        key = serialization.load_pem_public_key(public_key_pem)
    except (ValueError, TypeError):
        raise ReleaseRejected("ACCEPTANCE_PUBLIC_KEY_INVALID") from None
    if not isinstance(key, Ed25519PublicKey):
        raise ReleaseRejected("ACCEPTANCE_PUBLIC_KEY_INVALID")
    key_id = hashlib.sha256(key.public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)).hexdigest()
    if envelope["key_id"] != key_id:
        raise ReleaseRejected("ACCEPTANCE_KEY_ID_MISMATCH")
    signature = envelope["signature"]
    if not isinstance(signature, str) or len(signature) != 88:
        raise ReleaseRejected("ACCEPTANCE_SIGNATURE_INVALID")
    try:
        decoded = base64.b64decode(signature, altchars=b"-_", validate=True)
        if len(decoded) != 64 or base64.urlsafe_b64encode(decoded).decode() != signature:
            raise ValueError()
        key.verify(decoded, canonical_payload(envelope["payload"]))
    except (InvalidSignature, ValueError, TypeError):
        raise ReleaseRejected("ACCEPTANCE_SIGNATURE_INVALID") from None
    payload = envelope["payload"]
    fields = {"schema", "product", "environment", "revision_sha", "runtime_manifest_sha256",
              "infrastructure", "issued_at", "expires_at", "controls"}
    if not isinstance(payload, dict) or set(payload) != fields:
        raise ReleaseRejected("ACCEPTANCE_PAYLOAD_INVALID")
    if payload["schema"] != "forgeworks-production-acceptance-v1":
        raise ReleaseRejected("ACCEPTANCE_SCHEMA_INVALID")
    if expected.get("environment") != "production":
        raise ReleaseRejected("PRODUCTION_TARGET_REQUIRED")
    for field in ("product", "environment", "revision_sha", "runtime_manifest_sha256", "infrastructure"):
        if payload[field] != expected.get(field):
            raise ReleaseRejected("ACCEPTANCE_TARGET_MISMATCH")
    if not isinstance(payload["revision_sha"], str) or not re.fullmatch(
            r"[0-9a-f]{40}|[0-9a-f]{64}", payload["revision_sha"]):
        raise ReleaseRejected("ACCEPTANCE_REVISION_INVALID")
    if not isinstance(payload["runtime_manifest_sha256"], str) or not re.fullmatch(
            r"[0-9a-f]{64}", payload["runtime_manifest_sha256"]):
        raise ReleaseRejected("ACCEPTANCE_MANIFEST_INVALID")
    infrastructure = payload["infrastructure"]
    if not isinstance(infrastructure, dict) or set(infrastructure) != {
            "railway_project_id", "railway_environment_id", "supabase_project_ref"}:
        raise ReleaseRejected("ACCEPTANCE_INFRASTRUCTURE_INVALID")
    if any(not isinstance(value, str) or not 1 <= len(value) <= 200
           for value in infrastructure.values()):
        raise ReleaseRejected("ACCEPTANCE_INFRASTRUCTURE_INVALID")
    issued, expires = reviewed_time(payload["issued_at"]), reviewed_time(payload["expires_at"])
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or not issued <= now < expires:
        raise ReleaseRejected("ACCEPTANCE_EXPIRED_OR_FUTURE")
    controls = payload["controls"]
    if not isinstance(controls, list) or not len(REQUIRED_CONTROLS) <= len(controls) <= 64:
        raise ReleaseRejected("ACCEPTANCE_CONTROLS_REQUIRED")
    control_ids = set()
    for control in controls:
        if not isinstance(control, dict) or set(control) != {
                "id", "status", "evidence_uri", "evidence_sha256", "reviewer"}:
            raise ReleaseRejected("ACCEPTANCE_CONTROL_INVALID")
        control_id = control["id"]
        if (not isinstance(control_id, str) or not re.fullmatch(r"[a-z][a-z0-9-]{1,63}", control_id)
                or control_id in control_ids or control["status"] != "PASS"):
            raise ReleaseRejected("ACCEPTANCE_CONTROL_NOT_PASSED")
        control_ids.add(control_id)
        reviewer = control["reviewer"]
        if (not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 200
                or any(unicodedata.category(c) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for c in reviewer)):
            raise ReleaseRejected("ACCEPTANCE_REVIEWER_REQUIRED")
        uri = control["evidence_uri"]
        if (not isinstance(uri, str) or len(uri) > 2000
                or any(c.isspace() or unicodedata.category(c) in {"Cc", "Cf", "Cs"} for c in uri)):
            raise ReleaseRejected("ACCEPTANCE_EVIDENCE_INVALID")
        try:
            parsed = urlsplit(uri)
            invalid = (parsed.scheme != "https" or not parsed.hostname or "@" in parsed.netloc
                       or parsed.query or parsed.fragment or parsed.port is not None)
        except ValueError:
            invalid = True
        digest = control["evidence_sha256"]
        if invalid or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ReleaseRejected("ACCEPTANCE_EVIDENCE_INVALID")
    if not REQUIRED_CONTROLS.issubset(control_ids):
        raise ReleaseRejected("ACCEPTANCE_CONTROLS_REQUIRED")
    return {"result": "ACCEPTANCE_RECEIPT_VERIFIED", "control_count": len(controls),
            "receipt_sha256": hashlib.sha256(raw).hexdigest(), "signing_key_id": key_id}

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from accessfix_ai.domain.evidence_manifest import validate_evidence_export
from accessfix_ai.domain.static_html import image_alt_findings

from accessfix_ai.domain.target_policy import (
    MAX_SCAN_PATH_LENGTH,
    MAX_SCAN_PATHS,
    MIN_SCAN_PATHS,
    validate_origin,
    validate_scan_path,
    validate_scan_request,
)
from accessfix_ai.infrastructure.store import IdempotencyConflict, SITE, TENANT, USER, Store
from accessfix_ai.presentation.auth import scope
from accessfix_ai.worker import ScanWorker, WorkerConfig

from accessfix_ai.presentation.body_budget import BodyBudgetMiddleware

ROOT = Path(__file__).resolve().parents[4]


class Challenge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    canonical_origin: str
    repository_id: UUID


class Verify(BaseModel):
    model_config = ConfigDict(extra="forbid")
    challenge_id: UUID
    evidence_token: str


class StartScan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repo_commit_sha: str = Field(pattern=r"^([0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
    paths: list[str] = Field(min_length=MIN_SCAN_PATHS, max_length=MAX_SCAN_PATHS)


class CreateFix(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_mapping_id: UUID
    alt_text: str = Field(min_length=1, max_length=500)


class Retest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repo_commit_sha: str = Field(pattern=r"^([0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
    expected_version: int = Field(ge=1, strict=True)


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patch_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: str
    manual_check_status: str
    expected_version: int = Field(ge=1, strict=True)


class Publish(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review_id: UUID


def problem(status: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "type": "about:blank",
            "title": "Request rejected",
            "status": status,
            "code": code,
            "detail": detail,
            "request_id": "runtime",
        },
        media_type="application/problem+json",
    )


def _timestamp(value: datetime | None = None) -> str:
    return (value or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z")


def _local_fixture_evidence_export_enabled() -> bool:
    return os.getenv("APP_ENV", "") in {"development", "test"}


def _validate_evidence_value(value) -> None:
    if value is None or type(value) in {str, int, bool}:
        return
    if type(value) is list:
        for item in value:
            _validate_evidence_value(item)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for item in value.values():
            _validate_evidence_value(item)
        return
    raise TypeError("Evidence JSON allows only strings, integers, booleans, null, arrays, and objects")


def _canonical_evidence_bytes(payload: dict) -> bytes:
    """Minified UTF-8 JSON: sorted object keys, array order retained, no floats or trailing newline."""
    _validate_evidence_value(payload)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def create_app(db_path: str | None = None, seed: bool = False) -> FastAPI:
    if os.getenv("ACCESSFIX_DATABASE_URL"):
        from accessfix_ai.infrastructure.postgres_store import PostgresStore
        store = PostgresStore(os.environ["ACCESSFIX_DATABASE_URL"])
    else:
        if os.getenv("APP_ENV", "development") not in {"development", "test"}:
            raise ValueError("SQLite is restricted to development/test")
        store = Store(db_path or os.getenv("ACCESSFIX_DB_PATH", str(ROOT / ".runtime/accessfix.db")))
    if seed:
        store.seed()
    stop = threading.Event()

    scan_worker = ScanWorker(store, WorkerConfig(lease_seconds=0.25, timeout_seconds=2.0, max_attempts=3))

    def worker() -> None:
        while not stop.is_set():
            scan_worker.run_once()
            stop.wait(0.05)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        thread = threading.Thread(target=worker, daemon=True, name="accessfix-worker")
        thread.start()
        yield
        stop.set()
        thread.join(1)

    app = FastAPI(title="AccessFix AI MVP", version="0.1.0", lifespan=lifespan)
    app.add_middleware(BodyBudgetMiddleware)
    from accessfix_ai.presentation.operations import register_operations
    register_operations(app, ROOT, "accessfix-ai")
    # The static fixture console is intentionally local-only. Never use a wildcard
    # origin or allow credentials here; production identity remains a future BFF.
    ui_origins = [
        origin.strip()
        for origin in os.getenv("ACCESSFIX_UI_ORIGINS", "http://127.0.0.1:8080,http://localhost:8080").split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ui_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Accept", "Authorization", "Content-Type", "Idempotency-Key"],
        expose_headers=["X-Development-Challenge-Token"],
    )
    app.state.store = store

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_, error: RequestValidationError):
        # Do not echo raw input or attempt to serialize non-finite values.
        return JSONResponse(status_code=422, content={
            "type": "about:blank", "title": "Request rejected", "status": 422,
            "code": "INVALID_REQUEST", "detail": "Request does not match the input contract",
            "request_id": "runtime",
        }, media_type="application/problem+json")

    @app.exception_handler(HTTPException)
    async def http_error(_, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {
            "type": "about:blank",
            "title": "Request rejected",
            "status": exc.status_code,
            "code": "REQUEST_REJECTED",
            "detail": str(exc.detail),
            "request_id": "runtime",
        }
        return JSONResponse(status_code=exc.status_code, content=detail, media_type="application/problem+json")

    @app.get("/v1/auth/config")
    def auth_config():
        key=os.getenv("SUPABASE_PUBLISHABLE_KEY","")
        return {"enabled":os.getenv("AUTH_MODE")=="supabase" and key.startswith("sb_publishable_"), "supabase_url":os.getenv("SUPABASE_URL",""), "publishable_key":key if key.startswith("sb_publishable_") else "", "product":"accessfix-ai", "environment":os.getenv("APP_ENV","development")}

    @app.get("/readyz")
    def ready():
        from accessfix_ai.presentation.authentication import readiness
        return readiness(store)

    @app.get("/healthz")
    def health():
        return {"status": "ok", "service": "accessfix-ai"}

    @app.post("/v1/sites/verification-challenges", status_code=201)
    def challenge(body: Challenge, response: Response, c=Depends(scope("site:verify", store))):
        if os.getenv("APP_ENV", "development") not in {"development", "test"} and os.getenv("OWNERSHIP_VERIFY_MODE") != "http-file":
            return problem(503, "OWNERSHIP_VERIFIER_NOT_CONFIGURED", "An external ownership verifier is required")
        try:
            origin = validate_origin(body.canonical_origin, allow_fixture=os.getenv("APP_ENV", "development") in {"development", "test"})
        except ValueError as exc:
            return problem(400, "TARGET_NOT_ALLOWED", str(exc))
        token = secrets.token_urlsafe(24)
        expires = _timestamp(datetime.now(timezone.utc) + timedelta(minutes=15))
        with store.conn(c["tenant_id"]) as db:
            db.execute(
                "INSERT INTO sites VALUES(?,?,?,?,?,?) ON CONFLICT(tenant_id,id) DO UPDATE SET origin=excluded.origin,repo_id=excluded.repo_id,status='UNVERIFIED',verified_until=NULL",
                (c["tenant_id"], SITE, origin, str(body.repository_id), "UNVERIFIED", None),
            )
        challenge_id = store.challenge(c["tenant_id"], SITE, token, expires)
        external = os.getenv("OWNERSHIP_VERIFY_MODE") == "http-file"
        if not external:
            response.headers["X-Development-Challenge-Token"] = token
        return {
            "id": challenge_id,
            "status": "PENDING",
            "created_at": _timestamp(),
            "site_id": SITE,
            "canonical_origin": origin,
            "verification_method": "HTTP_WELL_KNOWN_FILE" if external else "DEVELOPMENT_HEADER_TOKEN",
            **({"verification_token": token, "verification_path": "/.well-known/forgeworks-site-verification.txt"} if external else {}),
            "expires_at": expires,
        }

    @app.post("/v1/sites/{site_id}/verify")
    def verify(site_id: UUID, body: Verify, c=Depends(scope("site:verify", store))):
        if os.getenv("APP_ENV", "development") not in {"development", "test"} and os.getenv("OWNERSHIP_VERIFY_MODE") != "http-file":
            return problem(503, "OWNERSHIP_VERIFIER_NOT_CONFIGURED", "An external ownership verifier is required")
        row = store.get_challenge(c["tenant_id"], str(body.challenge_id))
        if (
            not row
            or row["site_id"] != str(site_id)
            or row["used_at"]
            or row["expires_at"] < _timestamp()
            or not hmac.compare_digest(hashlib.sha256(body.evidence_token.encode()).hexdigest(), row["token_hash"])
        ):
            return problem(400, "VERIFICATION_FAILED", "Challenge is invalid, expired, or already used")
        target = store.site(c["tenant_id"], str(site_id))
        if not target:
            return problem(400, "VERIFICATION_FAILED", "Site is no longer available")
        if os.getenv("OWNERSHIP_VERIFY_MODE") == "http-file":
            from accessfix_ai.infrastructure.ownership_verifier import verify_ownership
            if not verify_ownership(target["origin"], body.evidence_token):
                return problem(400, "OWNERSHIP_PROOF_UNAVAILABLE", "Publish the challenge token at the HTTPS verification path before verifying")
        try:
            site = store.verify(c["tenant_id"], str(body.challenge_id), expected_origin=target["origin"])
        except ValueError:
            site = None
        if site is None:
            return problem(409, "VERIFICATION_RACE_REJECTED", "Challenge expired, was used, or site origin changed")
        proof = hashlib.sha256((site["origin"] + body.evidence_token).encode()).hexdigest()
        return {
            "id": str(body.challenge_id),
            "status": "VERIFIED",
            "created_at": row["expires_at"],
            "site_id": site["id"],
            "verified_until": site["verified_until"],
            "proof_digest": proof,
        }

    @app.post("/v1/sites/{site_id}/scans", status_code=202)
    def scan(site_id: UUID, body: StartScan, response: Response, idempotency_key: Annotated[str | None, Header()] = None, c=Depends(scope("scan:start", store))):
        site = store.site(c["tenant_id"], str(site_id))
        if not site or site["status"] != "VERIFIED":
            return problem(403, "OWNERSHIP_REQUIRED", "Site ownership must be verified before scanning")
        try:
            validate_scan_request(body.paths)

        except ValueError as exc:
            return problem(400, "TARGET_NOT_ALLOWED", str(exc))
        # The fixture runner is deterministic and local-only.  Real remote
        # browser execution remains disabled until isolation and egress proof
        # are independently verified; never queue it optimistically.
        if site["origin"] != "http://fixture.local":
            return problem(503, "REMOTE_BROWSER_BLOCKED", "Remote browser scanning is disabled until isolation is verified")
        try:
            for path in body.paths:
                validate_scan_path(path, site["origin"])
        except ValueError as exc:
            return problem(400, "TARGET_NOT_ALLOWED", str(exc))
        if body.paths != ["/"]:
            return problem(503, "SCAN_SCOPE_UNSUPPORTED", "The local fixture runner supports exactly one root path; no scan was queued")
        policy = hashlib.sha256(
            (site["origin"] + "|same-origin|no-private-egress|redirects=" + "5").encode()
        ).hexdigest()
        try:
            row = store.scan(
                c["tenant_id"], str(site_id), body.repo_commit_sha, policy,
                principal=c["sub"], idempotency_key=idempotency_key,
            )
        except IdempotencyConflict as exc:
            return problem(409, "IDEMPOTENCY_KEY_REUSED", str(exc))
        return {
            "id": row["id"],
            "status": row["status"],
            "created_at": row["created_at"],
            "site_id": row["site_id"],
            "repo_commit_sha": row["commit_sha"],
            "network_policy_sha256": row["policy_sha"],
            "job_id": row["job_id"],
        }

    @app.get("/v1/scans/{scan_id}/findings")
    def findings(scan_id: UUID, c=Depends(scope("scan:read", store))):
        snapshot = store.scan_findings_snapshot(c["tenant_id"], str(scan_id))
        if not snapshot:
            return problem(404, "RESOURCE_NOT_FOUND", "Scan is not visible")
        scan = snapshot["scan"]
        items = []
        # One SQL statement provides one consistent tenant-scoped snapshot of
        # scan state, findings, and immutable source across SQLite/PostgreSQL.
        visible_findings = snapshot["findings"]
        source_snapshot = snapshot["source"]
        actual = {}
        if scan["status"] == "SUCCEEDED":
            source_html = source_snapshot.get("source_html") if source_snapshot else None
            if not isinstance(source_html, str) or hashlib.sha256(source_html.encode()).hexdigest() != source_snapshot["source_sha"]:
                return problem(409, "SOURCE_INTEGRITY_FAILED", "Stored source evidence failed its digest check")
            try:
                actual_rows = image_alt_findings(source_html.encode())
            except (ValueError, TypeError, UnicodeError):
                return problem(409, "SOURCE_INTEGRITY_FAILED", "Stored source is not accepted by the scanner")
            actual = {item["fingerprint"]: item for item in actual_rows}
            stored_fingerprints = [finding["fingerprint"] for finding in visible_findings]
            if (
                len(actual) != len(actual_rows)
                or len(actual_rows) != len(visible_findings)
                or len(set(stored_fingerprints)) != len(visible_findings)
                or set(stored_fingerprints) != set(actual)
            ):
                return problem(409, "SOURCE_INTEGRITY_FAILED", "Stored findings differ from the source scan")
        for finding in visible_findings:
            matched = actual.get(finding["fingerprint"])
            manual_required_raw = finding["manual_required"]
            manual_required_valid = type(manual_required_raw) is int and manual_required_raw in {0, 1}
            mapping_verified = bool(
                matched
                and manual_required_valid
                and matched["selector"] == finding["selector"]
                and matched["rule_id"] == finding["rule_id"]
                and matched["severity"] == finding["severity"]
                and matched["manual_required"] == manual_required_raw
            )
            if not mapping_verified:
                return problem(409, "SOURCE_INTEGRITY_FAILED", "Stored finding differs from the source scan")
            items.append(
                {
                    "id": finding["id"],
                    "scan_id": finding["scan_id"],
                    "rule_id": finding["rule_id"],
                    "severity": finding["severity"],
                    "selector": finding["selector"],
                    "fingerprint": finding["fingerprint"],
                    "manual_check_required": manual_required_raw == 1,
                    "evidence": {
                        "kind": "DOM_SNIPPET",
                        "digest_sha256": matched["evidence_sha256"],
                    },
                    "source_mapping": {
                        "id": finding["id"],
                        "verified": mapping_verified,
                        "source_revision": scan["commit_sha"],
                        "revision_verified": False,
                        "source_kind": "LOCAL_FIXTURE",
                    },
                }
            )
        return {"items": items, "next_cursor": None, "has_more": False}

    @app.get("/v1/scans/{scan_id}/evidence-export")
    def export_scan_evidence(scan_id: UUID, c=Depends(scope("scan:read", store))):
        if not _local_fixture_evidence_export_enabled():
            return problem(503, "EVIDENCE_EXPORT_DISABLED", "Evidence export is limited to local synthetic fixtures until retention and privacy controls are approved")
        snapshot = store.scan_evidence_export(c["tenant_id"], str(scan_id))
        if not snapshot:
            return problem(404, "RESOURCE_NOT_FOUND", "Scan is not visible")
        if snapshot["scan"]["status"] != "SUCCEEDED":
            return problem(409, "EVIDENCE_NOT_READY", "Only completed scans can be exported")
        if snapshot["origin"] != "http://fixture.local":
            return problem(503, "EVIDENCE_EXPORT_DISABLED", "Only the local synthetic fixture is supported")
        if not snapshot["source_integrity_verified"]:
            return problem(409, "SOURCE_INTEGRITY_FAILED", "Stored source evidence failed its digest check")
        if not snapshot["findings_set_integrity_verified"]:
            return problem(409, "SOURCE_INTEGRITY_FAILED", "Stored findings differ from the source scan")
        if any(not finding["finding_integrity_verified"] for finding in snapshot["findings"]):
            return problem(409, "SOURCE_INTEGRITY_FAILED", "Stored finding differs from the source scan")
        if any(not proposal["content_integrity_verified"] for proposal in snapshot["proposals"]):
            return problem(409, "SOURCE_INTEGRITY_FAILED", "Stored proposal evidence failed its integrity check")

        findings_export = [{
            "id": finding["id"],
            "scan_id": finding["scan_id"],
            "rule_id": finding["rule_id"],
            "severity": finding["severity"],
            "selector": finding["selector"],
            "fingerprint": finding["fingerprint"],
            "manual_check_required": finding["manual_check_required"],
            "evidence": {"kind": "DOM_SNIPPET", "digest_sha256": finding["evidence_sha256"]},
            "source_mapping": {
                "id": finding["id"],
                "verified": finding["source_mapping_verified"],
                "source_revision": snapshot["scan"]["commit_sha"],
                "revision_verified": False,
                "source_kind": "LOCAL_FIXTURE",
            },
        } for finding in snapshot["findings"]]
        payload = {
            "schema_version": "forgeworks.accessfix.evidence/v1",
            "product": "accessfix-ai",
            "scope": "SYNTHETIC_LOCAL_FIXTURE_ONLY",
            "exported_at": _timestamp(),
            "scan": {
                "id": snapshot["scan"]["id"],
                "status": snapshot["scan"]["status"],
                "site_id": snapshot["scan"]["site_id"],
                "repo_commit_sha": snapshot["scan"]["commit_sha"],
                "revision_verified": False,
                "network_policy_sha256": snapshot["scan"]["policy_sha"],
                "created_at": snapshot["scan"]["created_at"],
                "attempt_count": snapshot["scan"]["attempt_count"],
            },
            "source": {
                "kind": "LOCAL_FIXTURE",
                "digest_sha256": snapshot["source_sha256"],
                "byte_length": snapshot["source_byte_length"],
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
            "findings": findings_export,
            "proposals": snapshot["proposals"],
            "limitations": [
                "SOURCE_REVISION_NOT_VERIFIED",
                "RAW_SOURCE_AND_PATCH_CONTENT_OMITTED",
                "NOT_SIGNED_OR_IMMUTABLE",
                "NOT_A_WCAG_CONFORMANCE_CLAIM",
            ],
        }
        try:
            canonical = _canonical_evidence_bytes(payload)
            payload["bundle_sha256"] = hashlib.sha256(canonical).hexdigest()
            validate_evidence_export(payload)
            body = _canonical_evidence_bytes(payload).decode("utf-8")
        except (TypeError, ValueError, UnicodeError):
            return problem(409, "EVIDENCE_SCHEMA_INVALID", "Stored evidence contains unsupported values")
        return Response(
            content=body,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="accessfix-evidence-{scan_id}.json"',
                "Cache-Control": "no-store",
            },
        )

    @app.post("/v1/findings/{finding_id}/fix-proposals", status_code=201)
    def fix(finding_id: UUID, body: CreateFix, idempotency_key: Annotated[str | None, Header()] = None, c=Depends(scope("patch:create", store))):
        finding = store.finding(c["tenant_id"], str(finding_id))
        if not finding or str(body.source_mapping_id) != str(finding_id):
            return problem(409, "SOURCE_MAPPING_UNAVAILABLE", "Finding has no verified source mapping")
        scan = store.get_scan(c["tenant_id"], finding["scan_id"])
        try:
            row = store.proposal(c["tenant_id"], str(finding_id), scan["commit_sha"], body.alt_text, principal=c["sub"], idempotency_key=idempotency_key)
        except IdempotencyConflict as exc:
            return problem(409, "IDEMPOTENCY_KEY_REUSED", str(exc))
        except ValueError as exc:
            return problem(409, "SOURCE_MAPPING_UNAVAILABLE", str(exc))
        return {
            "id": row["id"],
            "status": row["status"],
            "created_at": _timestamp(),
            "finding_id": row["finding_id"],
            "base_sha": row["base_sha"],
            "patch_sha256": row["patch_sha"],
            "patch": store.proposal_content(c["tenant_id"], row["id"])["patch_text"],
            "retest_status": row["retest_status"],
            "version": row["version"],
        }

    @app.post("/v1/fix-proposals/{proposal_id}/retests", status_code=202)
    def retest(proposal_id: UUID, body: Retest, idempotency_key: Annotated[str | None, Header()] = None, c=Depends(scope("patch:create", store))):
        try:
            result, status = store.retest(c["tenant_id"], str(proposal_id), body.repo_commit_sha, body.expected_version, principal=c["sub"], idempotency_key=idempotency_key)
        except IdempotencyConflict as exc:
            return problem(409, "IDEMPOTENCY_KEY_REUSED", str(exc))
        if status == "NOT_FOUND":
            return problem(404, "RESOURCE_NOT_FOUND", "Proposal is not visible")
        if status == "STALE":
            return problem(409, "STALE_VERSION", "Proposal version is stale")
        if status == "REVISION_MISMATCH":
            return problem(409, "REVISION_MISMATCH", "Retest must use the proposal base revision")
        if status == "SOURCE_INTEGRITY_FAILED":
            return problem(409, "SOURCE_INTEGRITY_FAILED", "Stored source or patch failed integrity and static retest")
        if status == "RETEST_FINDING_PERSISTS":
            return problem(409, "RETEST_FINDING_PERSISTS", "Accessibility finding persists after the source patch")
        return {
            "id": str(proposal_id),
            "status": "ACCEPTED",
            "proposal_id": str(proposal_id),
            "repo_commit_sha": body.repo_commit_sha,
            "retest_status": result["retest_status"],
            "version": result["version"],
        }

    @app.post("/v1/fix-proposals/{proposal_id}/reviews", status_code=201)
    def review(proposal_id: UUID, body: Review, idempotency_key: Annotated[str | None, Header()] = None, c=Depends(scope("patch:review", store))):
        if body.decision not in {"approve", "reject"} or body.manual_check_status not in {"passed", "failed", "not_applicable"}:
            return problem(400, "INVALID_REVIEW", "Review decision or manual status is invalid")
        try:
            result, status = store.review(
                c["tenant_id"], str(proposal_id), c["sub"], body.patch_sha256,
                body.decision, body.manual_check_status, body.expected_version,
                idempotency_key=idempotency_key,
            )
        except IdempotencyConflict as exc:
            return problem(409, "IDEMPOTENCY_KEY_REUSED", str(exc))
        if status == "NOT_FOUND":
            return problem(404, "RESOURCE_NOT_FOUND", "Proposal is not visible")
        if status == "STALE":
            return problem(409, "STALE_VERSION", "Proposal version is stale")
        if status == "DIGEST_MISMATCH":
            return problem(409, "DIGEST_MISMATCH", "Patch digest is not the reviewed proposal")
        review_id, decision = result
        return {
            "id": review_id,
            "status": decision,
            "created_at": _timestamp(),
            "proposal_id": str(proposal_id),
            "reviewer_id": c["sub"],
            "decision": body.decision,
            "manual_check_status": body.manual_check_status,
        }

    @app.post("/v1/fix-proposals/{proposal_id}/pull-requests")
    def publish(proposal_id: UUID, body: Publish, c=Depends(scope("github:write", store))):
        return problem(503, "LIVE_INTEGRATION_BLOCKED", "GitHub write integration is disabled until permission and sandbox evidence are verified")

    @app.get("/v1/jobs/{job_id}")
    def job(job_id: UUID, c=Depends(scope("job:read", store))):
        with store.conn(c["tenant_id"]) as db:
            row = db.execute(
                "SELECT * FROM scans WHERE tenant_id=? AND job_id=?", (c["tenant_id"], str(job_id))
            ).fetchone()
        if not row:
            return problem(404, "RESOURCE_NOT_FOUND", "Job is not visible")
        return {
            "id": row["job_id"],
            "kind": "accessibility_scan",
            "state": "FAILED_TERMINAL" if row["status"] in {"FAILED", "TIMED_OUT"} else row["status"],
            "created_at": row["created_at"],
            "state_version": 1,
            "attempt_count": int(row["attempt_count"] or 0),
            "last_error_code": row["last_error_code"],
        }

    @app.get("/", include_in_schema=False)
    def home():
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/ui/",status_code=307)

    from fastapi.staticfiles import StaticFiles
    web_dir=ROOT / "apps" / "web"
    if web_dir.is_dir():
        app.mount("/ui", StaticFiles(directory=str(web_dir),html=True),name="web-console")

    return app


app = create_app(seed=os.getenv("ACCESSFIX_SEED_FIXTURE", "0") == "1")

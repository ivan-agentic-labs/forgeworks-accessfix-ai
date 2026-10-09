from __future__ import annotations

import hashlib
import os
import secrets
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

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
    repo_commit_sha: str = Field(pattern=r"^[0-9a-fA-F]{40,64}$")
    paths: list[str] = Field(min_length=MIN_SCAN_PATHS, max_length=MAX_SCAN_PATHS)


class CreateFix(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_mapping_id: UUID


class Retest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repo_commit_sha: str = Field(pattern=r"^[0-9a-fA-F]{40,64}$")
    expected_version: int = Field(ge=1)


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patch_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: str
    manual_check_status: str
    expected_version: int = Field(ge=1)


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
    )


def _timestamp(value: datetime | None = None) -> str:
    return (value or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z")


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
        return JSONResponse(status_code=exc.status_code, content=detail)

    @app.get("/healthz")
    def health():
        return {"status": "ok", "service": "accessfix-ai"}

    @app.post("/v1/sites/verification-challenges", status_code=201)
    def challenge(body: Challenge, response: Response, c=Depends(scope("site:verify", store))):
        try:
            origin = validate_origin(body.canonical_origin)
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
        response.headers["X-Development-Challenge-Token"] = token
        return {
            "id": challenge_id,
            "status": "PENDING",
            "created_at": _timestamp(),
            "site_id": SITE,
            "canonical_origin": origin,
            "verification_method": "DEVELOPMENT_HEADER_TOKEN",
            "expires_at": expires,
        }

    @app.post("/v1/sites/{site_id}/verify")
    def verify(site_id: UUID, body: Verify, c=Depends(scope("site:verify", store))):
        row = store.get_challenge(c["tenant_id"], str(body.challenge_id))
        if (
            not row
            or row["site_id"] != str(site_id)
            or row["used_at"]
            or row["expires_at"] < _timestamp()
            or hashlib.sha256(body.evidence_token.encode()).hexdigest() != row["token_hash"]
        ):
            return problem(400, "VERIFICATION_FAILED", "Challenge is invalid, expired, or already used")
        site = store.verify(c["tenant_id"], str(body.challenge_id))
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
        scan = store.get_scan(c["tenant_id"], str(scan_id))
        if not scan:
            return problem(404, "RESOURCE_NOT_FOUND", "Scan is not visible")
        items = []
        for finding in store.findings(c["tenant_id"], str(scan_id)):
            evidence_text = f"{scan['site_id']}:{finding['selector']}:{finding['rule_id']}"
            items.append(
                {
                    "id": finding["id"],
                    "scan_id": finding["scan_id"],
                    "rule_id": finding["rule_id"],
                    "severity": finding["severity"],
                    "selector": finding["selector"],
                    "fingerprint": finding["fingerprint"],
                    "manual_check_required": bool(finding["manual_required"]),
                    "evidence": {
                        "kind": "DOM_SNIPPET",
                        "digest_sha256": hashlib.sha256(evidence_text.encode()).hexdigest(),
                    },
                    "source_mapping": {
                        "id": finding["id"],
                        "verified": True,
                        "source_revision": scan["commit_sha"],
                    },
                }
            )
        return {"items": items, "next_cursor": None, "has_more": False}

    @app.post("/v1/findings/{finding_id}/fix-proposals", status_code=201)
    def fix(finding_id: UUID, body: CreateFix, idempotency_key: Annotated[str | None, Header()] = None, c=Depends(scope("patch:create", store))):
        finding = store.finding(c["tenant_id"], str(finding_id))
        if not finding or str(body.source_mapping_id) != str(finding_id):
            return problem(409, "SOURCE_MAPPING_UNAVAILABLE", "Finding has no verified source mapping")
        scan = store.get_scan(c["tenant_id"], finding["scan_id"])
        patch = hashlib.sha256(
            (finding["selector"] + "|add alt text|" + finding["fingerprint"]).encode()
        ).hexdigest()
        row = store.proposal(c["tenant_id"], str(finding_id), scan["commit_sha"], patch)
        return {
            "id": row["id"],
            "status": row["status"],
            "created_at": _timestamp(),
            "finding_id": row["finding_id"],
            "base_sha": row["base_sha"],
            "patch_sha256": row["patch_sha"],
            "retest_status": row["retest_status"],
            "version": row["version"],
        }

    @app.post("/v1/fix-proposals/{proposal_id}/retests", status_code=202)
    def retest(proposal_id: UUID, body: Retest, idempotency_key: Annotated[str | None, Header()] = None, c=Depends(scope("patch:create", store))):
        result, status = store.retest(c["tenant_id"], str(proposal_id), body.repo_commit_sha, body.expected_version)
        if status == "NOT_FOUND":
            return problem(404, "RESOURCE_NOT_FOUND", "Proposal is not visible")
        if status == "STALE":
            return problem(409, "STALE_VERSION", "Proposal version is stale")
        if status == "REVISION_MISMATCH":
            return problem(409, "REVISION_MISMATCH", "Retest must use the proposal base revision")
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
        result, status = store.review(
            c["tenant_id"], str(proposal_id), c["sub"], body.patch_sha256,
            body.decision, body.manual_check_status, body.expected_version,
        )
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

    return app


app = create_app(seed=os.getenv("ACCESSFIX_SEED_FIXTURE", "0") == "1")


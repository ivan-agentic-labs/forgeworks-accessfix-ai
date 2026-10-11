from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from accessfix_ai.domain.static_html import image_alt_findings, build_image_alt_patch, MAX_SOURCE_BYTES

TENANT = "00000000-0000-0000-0000-000000000001"
USER = "00000000-0000-0000-0000-000000000010"
SITE = "22222222-2222-2222-2222-222222222222"


class IdempotencyConflict(ValueError):
    """The same idempotency key was reused with a different request."""


class ScanUnavailable(ValueError):
    """A scan cannot be completed because it was cancelled or timed out."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def later(seconds: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def validate_attempt_budget(max_attempts: int) -> None:
    if type(max_attempts) is not int or max_attempts < 1:
        raise ValueError("max_attempts must be a positive integer")


class Store:
    def __init__(self, path: str):
        self._uri = path == ":memory:"
        self.path = f"file:accessfix-{uuid.uuid4().hex}?mode=memory&cache=shared" if self._uri else path
        self.lock = threading.RLock()
        if self._uri:
            self._keeper = sqlite3.connect(self.path, uri=True, check_same_thread=False)
        else:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.init()

    def conn(self, tenant=None) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, uri=self._uri, check_same_thread=False, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def init(self) -> None:
        with self.lock, self.conn() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS tenants(id TEXT PRIMARY KEY,slug TEXT,status TEXT);
                CREATE TABLE IF NOT EXISTS memberships(tenant_id TEXT,user_id TEXT,role TEXT,status TEXT,PRIMARY KEY(tenant_id,user_id));
                CREATE TABLE IF NOT EXISTS sites(tenant_id TEXT,id TEXT,origin TEXT,repo_id TEXT,status TEXT,verified_until TEXT,PRIMARY KEY(tenant_id,id));
                CREATE TABLE IF NOT EXISTS challenges(tenant_id TEXT,id TEXT,site_id TEXT,token_hash TEXT,expires_at TEXT,used_at TEXT,PRIMARY KEY(tenant_id,id));
                CREATE TABLE IF NOT EXISTS scans(tenant_id TEXT,id TEXT,site_id TEXT,commit_sha TEXT,policy_sha TEXT,status TEXT,created_at TEXT,job_id TEXT,attempt_count INTEGER NOT NULL DEFAULT 0,lease_until TEXT,last_error_code TEXT,cancel_requested INTEGER NOT NULL DEFAULT 0,timeout_at TEXT,PRIMARY KEY(tenant_id,id));
                CREATE TABLE IF NOT EXISTS findings(tenant_id TEXT,id TEXT,scan_id TEXT,rule_id TEXT,severity TEXT,selector TEXT,fingerprint TEXT,manual_required INTEGER,PRIMARY KEY(tenant_id,id));
                CREATE TABLE IF NOT EXISTS scan_sources(tenant_id TEXT,scan_id TEXT,source_sha TEXT,source_html TEXT,PRIMARY KEY(tenant_id,scan_id));
                CREATE TABLE IF NOT EXISTS proposal_sources(tenant_id TEXT,proposal_id TEXT,source_sha TEXT,patched_sha TEXT,patch_text TEXT,patched_html TEXT,alt_text TEXT,PRIMARY KEY(tenant_id,proposal_id));
                CREATE TABLE IF NOT EXISTS proposals(tenant_id TEXT,id TEXT,finding_id TEXT,base_sha TEXT,patch_sha TEXT,status TEXT,retest_status TEXT,version INTEGER,PRIMARY KEY(tenant_id,id));
                CREATE TABLE IF NOT EXISTS reviews(tenant_id TEXT,id TEXT,proposal_id TEXT,reviewer_id TEXT,decision TEXT,manual_status TEXT,version INTEGER,PRIMARY KEY(tenant_id,id));
                CREATE TABLE IF NOT EXISTS idempotency_keys(tenant_id TEXT,principal TEXT,action TEXT,key TEXT,request_hash TEXT,resource_id TEXT NOT NULL,response_status INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(tenant_id,principal,action,key));
                """
            )
            # Keep databases created by the first MVP runnable without a destructive migration.
            columns = {row[1] for row in c.execute("PRAGMA table_info(scans)").fetchall()}
            for name, definition in (
                ("attempt_count", "INTEGER NOT NULL DEFAULT 0"),
                ("lease_until", "TEXT"),
                ("last_error_code", "TEXT"),
                ("cancel_requested", "INTEGER NOT NULL DEFAULT 0"),
                ("timeout_at", "TEXT"),
            ):
                if name not in columns:
                    c.execute(f"ALTER TABLE scans ADD COLUMN {name} {definition}")
            c.execute("CREATE UNIQUE INDEX IF NOT EXISTS findings_scan_fingerprint ON findings(tenant_id,scan_id,fingerprint)")
            c.execute("CREATE UNIQUE INDEX IF NOT EXISTS proposals_finding_base ON proposals(tenant_id,finding_id,base_sha)")
            c.execute("CREATE UNIQUE INDEX IF NOT EXISTS reviews_proposal_reviewer_version ON reviews(tenant_id,proposal_id,reviewer_id,version)")

    def seed(self) -> None:
        with self.conn() as c:
            c.execute("INSERT OR IGNORE INTO tenants VALUES(?,?,?)", (TENANT, "synthetic-demo", "ACTIVE"))
            c.execute("INSERT OR IGNORE INTO memberships VALUES(?,?,?,?)", (TENANT, USER, "editor", "ACTIVE"))
            c.execute(
                "INSERT OR IGNORE INTO sites VALUES(?,?,?,?,?,?)",
                (TENANT, SITE, "http://fixture.local", "synthetic-repo", "UNVERIFIED", None),
            )

    def member_role(self, tenant: str, user: str) -> str | None:
        """Return the role of an ACTIVE member in this exact tenant."""
        with self.conn() as db:
            row = db.execute(
                "SELECT role FROM memberships WHERE tenant_id=? AND user_id=? AND status='ACTIVE'",
                (tenant, user),
            ).fetchone()
            return str(row["role"]) if row else None

    def member(self, tenant: str, user: str) -> bool:
        with self.conn() as c:
            return c.execute("SELECT 1 FROM memberships WHERE tenant_id=? AND user_id=? AND status='ACTIVE'", (tenant, user)).fetchone() is not None

    def site(self, tenant: str, site_id: str):
        with self.conn() as c:
            return c.execute("SELECT * FROM sites WHERE tenant_id=? AND id=?", (tenant, site_id)).fetchone()

    def challenge(self, tenant: str, site_id: str, token: str, expires: str) -> str:
        challenge_id = str(uuid.uuid4())
        with self.conn() as c:
            c.execute("INSERT INTO challenges VALUES(?,?,?,?,?,NULL)", (tenant, challenge_id, site_id, hashlib.sha256(token.encode()).hexdigest(), expires))
        return challenge_id

    def get_challenge(self, tenant: str, challenge_id: str):
        with self.conn() as c:
            return c.execute("SELECT * FROM challenges WHERE tenant_id=? AND id=?", (tenant, challenge_id)).fetchone()

    def verify(self, tenant: str, challenge_id: str):
        with self.conn() as c:
            row = c.execute("SELECT * FROM challenges WHERE tenant_id=? AND id=?", (tenant, challenge_id)).fetchone()
            if not row:
                return None
            c.execute("UPDATE challenges SET used_at=? WHERE tenant_id=? AND id=? AND used_at IS NULL", (now(), tenant, challenge_id))
            verified_until = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat().replace("+00:00", "Z")
            c.execute("UPDATE sites SET status='VERIFIED',verified_until=? WHERE tenant_id=? AND id=?", (verified_until, tenant, row["site_id"]))
            return c.execute("SELECT * FROM sites WHERE tenant_id=? AND id=?", (tenant, row["site_id"])).fetchone()

    def _idempotent_resource(self, tenant: str, principal: str, action: str, key: str | None, request_hash: str, resource_id: str) -> str:
        if not key:
            return resource_id
        with self.lock, self.conn() as c:
            existing = c.execute("SELECT request_hash,resource_id FROM idempotency_keys WHERE tenant_id=? AND principal=? AND action=? AND key=?", (tenant, principal, action, key)).fetchone()
            if existing:
                if existing["request_hash"] != request_hash:
                    raise IdempotencyConflict("Idempotency-Key was reused for a different request")
                return existing["resource_id"]
            try:
                c.execute("INSERT INTO idempotency_keys VALUES(?,?,?,?,?,?,?)", (tenant, principal, action, key, request_hash, resource_id, 0))
            except sqlite3.IntegrityError:
                existing = c.execute("SELECT request_hash,resource_id FROM idempotency_keys WHERE tenant_id=? AND principal=? AND action=? AND key=?", (tenant, principal, action, key)).fetchone()
                if existing["request_hash"] != request_hash:
                    raise IdempotencyConflict("Idempotency-Key was reused for a different request")
                return existing["resource_id"]
        return resource_id

    def scan(self, tenant: str, site_id: str, commit_sha: str, policy: str, *, principal: str = "system", idempotency_key: str | None = None):
        request_hash = hashlib.sha256(json.dumps([site_id, commit_sha, policy], separators=(",", ":")).encode()).hexdigest()
        with self.lock, self.conn() as c:
            existing = None
            if idempotency_key:
                existing = c.execute("SELECT request_hash,resource_id FROM idempotency_keys WHERE tenant_id=? AND principal=? AND action='scan' AND key=?", (tenant, principal, idempotency_key)).fetchone()
                if existing and existing["request_hash"] != request_hash:
                    raise IdempotencyConflict("Idempotency-Key was reused for a different request")
            if existing:
                return self.get_scan(tenant, existing["resource_id"])
            scan_id, job_id = str(uuid.uuid4()), str(uuid.uuid4())
            c.execute("INSERT INTO scans(tenant_id,id,site_id,commit_sha,policy_sha,status,created_at,job_id) VALUES(?,?,?,?,?,?,?,?)", (tenant, scan_id, site_id, commit_sha, policy, "PENDING", now(), job_id))
            if idempotency_key:
                c.execute("INSERT INTO idempotency_keys VALUES(?,?,?,?,?,?,?)", (tenant, principal, "scan", idempotency_key, request_hash, scan_id, 202))
        return self.get_scan(tenant, scan_id)

    def get_scan(self, tenant: str, scan_id: str):
        with self.conn() as c:
            return c.execute("SELECT * FROM scans WHERE tenant_id=? AND id=?", (tenant, scan_id)).fetchone()

    def claim_scan(self, lease_seconds: float = 5.0, timeout_seconds: float = 30.0, *, max_attempts: int = 3):
        validate_attempt_budget(max_attempts)
        with self.lock, self.conn() as c:
            c.execute("BEGIN IMMEDIATE")
            current = now()
            c.execute("UPDATE scans SET status=CASE WHEN cancel_requested=1 THEN 'CANCELLED' ELSE 'FAILED' END, "
                      "last_error_code=CASE WHEN cancel_requested=1 THEN 'CANCELLED' ELSE 'MAX_ATTEMPTS_EXCEEDED' END, "
                      "lease_until=NULL,timeout_at=NULL WHERE attempt_count>=? AND "
                      "(status='PENDING' OR (status='RUNNING' AND lease_until IS NOT NULL AND lease_until<?))",
                      (max_attempts, current))
            row = c.execute("SELECT * FROM scans WHERE attempt_count<? AND (status='PENDING' OR (status='RUNNING' AND lease_until IS NOT NULL AND lease_until<?)) ORDER BY created_at LIMIT 1", (max_attempts, current)).fetchone()
            if not row:
                return None
            attempt = int(row["attempt_count"] or 0) + 1
            lease = later(lease_seconds)
            timeout = later(timeout_seconds)
            changed = c.execute("UPDATE scans SET status='RUNNING',attempt_count=?,lease_until=?,timeout_at=?,last_error_code=NULL WHERE tenant_id=? AND id=? AND (status='PENDING' OR (status='RUNNING' AND lease_until IS NOT NULL AND lease_until<?))", (attempt, lease, timeout, row["tenant_id"], row["id"], current)).rowcount
            if not changed:
                return None
            return c.execute("SELECT * FROM scans WHERE tenant_id=? AND id=?", (row["tenant_id"], row["id"])).fetchone()

    def complete_scan(self, tenant: str, scan_id: str, lease_until: str | None = None) -> bool:
        with self.lock, self.conn() as c:
            if isinstance(c, sqlite3.Connection):
                c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM scans WHERE tenant_id=? AND id=?", (tenant, scan_id)).fetchone()
            if not row or row["cancel_requested"] or row["status"] not in ("PENDING", "RUNNING"):
                return False
            if lease_until is not None and row["lease_until"] != lease_until:
                return False
            if row["timeout_at"] and row["timeout_at"] < now():
                c.execute("UPDATE scans SET status='TIMED_OUT',last_error_code='WORKER_TIMEOUT',lease_until=NULL WHERE tenant_id=? AND id=? AND status='RUNNING'", (tenant, scan_id))
                return False
            fixture = Path(__file__).resolve().parents[5] / "fixtures/golden/fixture.html"
            with fixture.open("rb") as source:
                source_bytes = source.read(MAX_SOURCE_BYTES + 1)
                findings = image_alt_findings(source_bytes)
            lease_clause = " AND lease_until=?" if lease_until is not None else ""
            values = (tenant, scan_id, lease_until) if lease_until is not None else (tenant, scan_id)
            changed = c.execute(f"UPDATE scans SET status='SUCCEEDED',lease_until=NULL,timeout_at=NULL WHERE tenant_id=? AND id=? AND status IN ('PENDING','RUNNING'){lease_clause}", values).rowcount
            if changed == 1:
                c.execute("INSERT INTO scan_sources(tenant_id,scan_id,source_sha,source_html) VALUES(?,?,?,?)", (tenant, scan_id, hashlib.sha256(source_bytes).hexdigest(), source_bytes.decode("utf-8")))
                for finding in findings:
                    c.execute("INSERT OR IGNORE INTO findings VALUES(?,?,?,?,?,?,?,?)", (tenant, str(uuid.uuid4()), scan_id, finding["rule_id"], finding["severity"], finding["selector"], finding["fingerprint"], finding["manual_required"]))
            return changed == 1

    def finish_scan(self, tenant: str, scan_id: str) -> None:
        self.complete_scan(tenant, scan_id)

    def scan_source(self, tenant: str, scan_id: str):
        with self.conn() as c:
            return c.execute("SELECT * FROM scan_sources WHERE tenant_id=? AND scan_id=?", (tenant, scan_id)).fetchone()

    def fail_scan(self, tenant: str, scan_id: str, error_code: str, *, max_attempts: int = 3, lease_until: str | None = None) -> str:
        with self.lock, self.conn() as c:
            if isinstance(c, sqlite3.Connection):
                c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM scans WHERE tenant_id=? AND id=?", (tenant, scan_id)).fetchone()
            if not row:
                return "NOT_FOUND"
            if lease_until is not None and row["lease_until"] != lease_until:
                return "STALE_LEASE"
            if row["status"] not in ("PENDING", "RUNNING"):
                return row["status"]
            if row["cancel_requested"]:
                c.execute("UPDATE scans SET status='CANCELLED',lease_until=NULL,last_error_code='CANCELLED' WHERE tenant_id=? AND id=?", (tenant, scan_id))
                return "CANCELLED"
            terminal = int(row["attempt_count"] or 0) >= max_attempts
            lease_clause = " AND lease_until=?" if lease_until is not None else ""
            values = ("FAILED" if terminal else "PENDING", error_code, tenant, scan_id, lease_until) if lease_until is not None else ("FAILED" if terminal else "PENDING", error_code, tenant, scan_id)
            c.execute(f"UPDATE scans SET status=?,lease_until=NULL,last_error_code=?,timeout_at=NULL WHERE tenant_id=? AND id=? AND status='RUNNING'{lease_clause}", values)
            return "FAILED" if terminal else "RETRYING"

    def request_cancel(self, tenant: str, scan_id: str) -> bool:
        with self.conn() as c:
            return c.execute("UPDATE scans SET cancel_requested=1 WHERE tenant_id=? AND id=? AND status IN ('PENDING','RUNNING')", (tenant, scan_id)).rowcount == 1

    def findings(self, tenant: str, scan_id: str):
        with self.conn() as c:
            return c.execute("SELECT * FROM findings WHERE tenant_id=? AND scan_id=? ORDER BY id", (tenant, scan_id)).fetchall()

    def finding(self, tenant: str, finding_id: str):
        with self.conn() as c:
            return c.execute("SELECT * FROM findings WHERE tenant_id=? AND id=?", (tenant, finding_id)).fetchone()

    def proposal(self, tenant: str, finding_id: str, base_sha: str, alt_text: str, *, principal: str = "system", idempotency_key: str | None = None):
        request_hash = hashlib.sha256(json.dumps([finding_id, base_sha, alt_text], separators=(",", ":")).encode()).hexdigest()
        with self.lock, self.conn() as c:
            if isinstance(c, sqlite3.Connection):
                c.execute("BEGIN IMMEDIATE")
            if idempotency_key:
                command = c.execute("SELECT * FROM idempotency_keys WHERE tenant_id=? AND principal=? AND action='proposal' AND key=?", (tenant, principal, idempotency_key)).fetchone()
                if command:
                    if command["request_hash"] != request_hash:
                        raise IdempotencyConflict("Idempotency-Key was reused for a different proposal request")
                    return c.execute("SELECT * FROM proposals WHERE tenant_id=? AND id=?", (tenant, command["resource_id"])).fetchone()
            existing = c.execute("SELECT * FROM proposals WHERE tenant_id=? AND finding_id=? AND base_sha=?", (tenant, finding_id, base_sha)).fetchone()
            if existing:
                content = c.execute("SELECT * FROM proposal_sources WHERE tenant_id=? AND proposal_id=?", (tenant, existing["id"])).fetchone()
                if not content or content["alt_text"] != alt_text:
                    raise ValueError("Existing proposal has different or unavailable source content")
                if idempotency_key:
                    c.execute("INSERT INTO idempotency_keys VALUES(?,?,?,?,?,?,?)", (tenant, principal, "proposal", idempotency_key, request_hash, existing["id"], 201))
                return existing
            finding = c.execute("SELECT * FROM findings WHERE tenant_id=? AND id=?", (tenant, finding_id)).fetchone()
            if not finding or not finding["selector"].startswith("img#"):
                raise ValueError("A unique image source mapping is required")
            scan = c.execute("SELECT * FROM scans WHERE tenant_id=? AND id=?", (tenant, finding["scan_id"])).fetchone()
            snapshot = c.execute("SELECT * FROM scan_sources WHERE tenant_id=? AND scan_id=?", (tenant, finding["scan_id"])).fetchone()
            if not snapshot or not scan or scan["commit_sha"] != base_sha:
                raise ValueError("Source snapshot or revision is unavailable")
            source = snapshot["source_html"].encode("utf-8")
            if hashlib.sha256(source).hexdigest() != snapshot["source_sha"]:
                raise ValueError("Source snapshot digest mismatch")
            actual = image_alt_findings(source)
            if not any(item["fingerprint"] == finding["fingerprint"] and item["selector"] == finding["selector"] for item in actual):
                raise ValueError("Finding is not bound to the stored source")
            patch = build_image_alt_patch(source, finding["selector"][4:], alt_text)
            proposal_id = str(uuid.uuid4())
            c.execute("INSERT INTO proposals VALUES(?,?,?,?,?,?,?,?)", (tenant, proposal_id, finding_id, base_sha, patch["patch_sha256"], "PENDING_RETEST", "NOT_RUN", 1))
            c.execute("INSERT INTO proposal_sources(tenant_id,proposal_id,source_sha,patched_sha,patch_text,patched_html,alt_text) VALUES(?,?,?,?,?,?,?)", (tenant, proposal_id, patch["source_sha256"], patch["patched_sha256"], patch["patch"], patch["patched_source"].decode("utf-8"), alt_text))
            if idempotency_key:
                c.execute("INSERT INTO idempotency_keys VALUES(?,?,?,?,?,?,?)", (tenant, principal, "proposal", idempotency_key, request_hash, proposal_id, 201))
        return self.proposal_get(tenant, proposal_id)

    def proposal_content(self, tenant: str, proposal_id: str):
        with self.conn() as c:
            return c.execute("SELECT * FROM proposal_sources WHERE tenant_id=? AND proposal_id=?", (tenant, proposal_id)).fetchone()

    def proposal_get(self, tenant: str, proposal_id: str):
        with self.conn() as c:
            return c.execute("SELECT * FROM proposals WHERE tenant_id=? AND id=?", (tenant, proposal_id)).fetchone()

    def retest(self, tenant: str, proposal_id: str, commit_sha: str, expected_version: int, *, principal: str = "system", idempotency_key: str | None = None):
        request_hash = hashlib.sha256(json.dumps([proposal_id, commit_sha, expected_version], separators=(",", ":")).encode()).hexdigest()
        with self.lock, self.conn() as c:
            if isinstance(c, sqlite3.Connection):
                c.execute("BEGIN IMMEDIATE")
            if idempotency_key:
                command = c.execute("SELECT request_hash,resource_id FROM idempotency_keys WHERE tenant_id=? AND principal=? AND action='retest' AND key=?", (tenant, principal, idempotency_key)).fetchone()
                if command:
                    if command["request_hash"] != request_hash:
                        raise IdempotencyConflict("Idempotency-Key was reused for a different retest request")
                    return c.execute("SELECT * FROM proposals WHERE tenant_id=? AND id=?", (tenant, command["resource_id"])).fetchone(), "OK"
            row = c.execute("SELECT * FROM proposals WHERE tenant_id=? AND id=?", (tenant, proposal_id)).fetchone()
            if not row:
                return None, "NOT_FOUND"
            if row["version"] != expected_version or row["retest_status"] != "NOT_RUN" or row["status"] != "PENDING_RETEST":
                return row, "STALE"
            if row["base_sha"] != commit_sha:
                return row, "REVISION_MISMATCH"
            content = c.execute("SELECT * FROM proposal_sources WHERE tenant_id=? AND proposal_id=?", (tenant, proposal_id)).fetchone()
            finding = c.execute("SELECT * FROM findings WHERE tenant_id=? AND id=?", (tenant, row["finding_id"])).fetchone()
            source = c.execute("SELECT * FROM scan_sources WHERE tenant_id=? AND scan_id=?", (tenant, finding["scan_id"])).fetchone() if finding else None
            try:
                if not content or not source or hashlib.sha256(source["source_html"].encode()).hexdigest() != source["source_sha"]:
                    raise ValueError("Missing or corrupted source")
                rebuilt = build_image_alt_patch(source["source_html"].encode(), finding["selector"][4:], content["alt_text"])
                if rebuilt["source_sha256"] != content["source_sha"] or rebuilt["patched_sha256"] != content["patched_sha"] or rebuilt["patch_sha256"] != row["patch_sha"] or rebuilt["patch"] != content["patch_text"] or rebuilt["patched_source"].decode() != content["patched_html"]:
                    raise ValueError("Patch integrity mismatch")
            except (ValueError, TypeError):
                return row, "SOURCE_INTEGRITY_FAILED"
            changed = c.execute("UPDATE proposals SET retest_status='PASSED',status='PENDING_REVIEW',version=version+1 WHERE tenant_id=? AND id=? AND version=? AND status='PENDING_RETEST'", (tenant, proposal_id, expected_version)).rowcount
            if not changed:
                return row, "STALE"
            if idempotency_key:
                c.execute("INSERT INTO idempotency_keys VALUES(?,?,?,?,?,?,?)", (tenant, principal, "retest", idempotency_key, request_hash, proposal_id, 202))
        return self.proposal_get(tenant, proposal_id), "OK"

    def review(self, tenant: str, proposal_id: str, reviewer: str, patch: str, decision: str, manual: str, version: int, *, idempotency_key: str | None = None):
        request_hash = hashlib.sha256(json.dumps([proposal_id, reviewer, patch, decision, manual, version], separators=(",", ":")).encode()).hexdigest()
        with self.lock, self.conn() as c:
            if isinstance(c, sqlite3.Connection):
                c.execute("BEGIN IMMEDIATE")
            if idempotency_key:
                command = c.execute("SELECT request_hash,resource_id FROM idempotency_keys WHERE tenant_id=? AND principal=? AND action='review' AND key=?", (tenant, reviewer, idempotency_key)).fetchone()
                if command:
                    if command["request_hash"] != request_hash:
                        raise IdempotencyConflict("Idempotency-Key was reused for a different review request")
                    existing = c.execute("SELECT id,decision,manual_status FROM reviews WHERE tenant_id=? AND id=?", (tenant, command["resource_id"])).fetchone()
                    if existing:
                        status = "APPROVED" if existing["decision"] == "approve" and existing["manual_status"] == "passed" else "REJECTED"
                        return (existing["id"], status), "OK"
            row = c.execute("SELECT * FROM proposals WHERE tenant_id=? AND id=?", (tenant, proposal_id)).fetchone()
            if not row:
                return None, "NOT_FOUND"
            if row["version"] != version or row["status"] != "PENDING_REVIEW" or row["retest_status"] != "PASSED":
                return row, "STALE"
            if row["patch_sha"] != patch:
                return row, "DIGEST_MISMATCH"
            review_id = str(uuid.uuid4())
            status = "APPROVED" if decision == "approve" and manual == "passed" else "REJECTED"
            changed = c.execute("UPDATE proposals SET status=?,version=version+1 WHERE tenant_id=? AND id=? AND version=? AND status='PENDING_REVIEW' AND retest_status='PASSED'", (status, tenant, proposal_id, version)).rowcount
            if changed != 1:
                return row, "STALE"
            c.execute("INSERT INTO reviews VALUES(?,?,?,?,?,?,?)", (tenant, review_id, proposal_id, reviewer, decision, manual, version))
            if idempotency_key:
                c.execute("INSERT INTO idempotency_keys VALUES(?,?,?,?,?,?,?)", (tenant, reviewer, "review", idempotency_key, request_hash, review_id, 201))
            return (review_id, status), "OK"

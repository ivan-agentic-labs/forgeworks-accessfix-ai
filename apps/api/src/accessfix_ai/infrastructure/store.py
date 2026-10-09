from __future__ import annotations

import hashlib
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

TENANT = "00000000-0000-0000-0000-000000000001"
USER = "00000000-0000-0000-0000-000000000010"
SITE = "22222222-2222-2222-2222-222222222222"


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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

    def conn(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, uri=self._uri, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def init(self) -> None:
        with self.conn() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS tenants(id TEXT PRIMARY KEY,slug TEXT,status TEXT);
                CREATE TABLE IF NOT EXISTS memberships(tenant_id TEXT,user_id TEXT,role TEXT,status TEXT,PRIMARY KEY(tenant_id,user_id));
                CREATE TABLE IF NOT EXISTS sites(tenant_id TEXT,id TEXT,origin TEXT,repo_id TEXT,status TEXT,verified_until TEXT,PRIMARY KEY(tenant_id,id));
                CREATE TABLE IF NOT EXISTS challenges(tenant_id TEXT,id TEXT,site_id TEXT,token_hash TEXT,expires_at TEXT,used_at TEXT,PRIMARY KEY(tenant_id,id));
                CREATE TABLE IF NOT EXISTS scans(tenant_id TEXT,id TEXT,site_id TEXT,commit_sha TEXT,policy_sha TEXT,status TEXT,created_at TEXT,job_id TEXT,PRIMARY KEY(tenant_id,id));
                CREATE TABLE IF NOT EXISTS findings(tenant_id TEXT,id TEXT,scan_id TEXT,rule_id TEXT,severity TEXT,selector TEXT,fingerprint TEXT,manual_required INTEGER,PRIMARY KEY(tenant_id,id));
                CREATE TABLE IF NOT EXISTS proposals(tenant_id TEXT,id TEXT,finding_id TEXT,base_sha TEXT,patch_sha TEXT,status TEXT,retest_status TEXT,version INTEGER,PRIMARY KEY(tenant_id,id));
                CREATE TABLE IF NOT EXISTS reviews(tenant_id TEXT,id TEXT,proposal_id TEXT,reviewer_id TEXT,decision TEXT,manual_status TEXT,version INTEGER,PRIMARY KEY(tenant_id,id));
                """
            )

    def seed(self) -> None:
        with self.conn() as c:
            c.execute("INSERT OR IGNORE INTO tenants VALUES(?,?,?)", (TENANT, "synthetic-demo", "ACTIVE"))
            c.execute("INSERT OR IGNORE INTO memberships VALUES(?,?,?,?)", (TENANT, USER, "editor", "ACTIVE"))
            c.execute(
                "INSERT OR IGNORE INTO sites VALUES(?,?,?,?,?,?)",
                (TENANT, SITE, "http://fixture.local", "synthetic-repo", "UNVERIFIED", None),
            )

    def member(self, tenant: str, user: str) -> bool:
        with self.conn() as c:
            return c.execute(
                "SELECT 1 FROM memberships WHERE tenant_id=? AND user_id=? AND status='ACTIVE'",
                (tenant, user),
            ).fetchone() is not None

    def site(self, tenant: str, site_id: str):
        with self.conn() as c:
            return c.execute("SELECT * FROM sites WHERE tenant_id=? AND id=?", (tenant, site_id)).fetchone()

    def challenge(self, tenant: str, site_id: str, token: str, expires: str) -> str:
        challenge_id = str(uuid.uuid4())
        with self.conn() as c:
            c.execute(
                "INSERT INTO challenges VALUES(?,?,?,?,?,NULL)",
                (tenant, challenge_id, site_id, hashlib.sha256(token.encode()).hexdigest(), expires),
            )
        return challenge_id

    def get_challenge(self, tenant: str, challenge_id: str):
        with self.conn() as c:
            return c.execute(
                "SELECT * FROM challenges WHERE tenant_id=? AND id=?", (tenant, challenge_id)
            ).fetchone()

    def verify(self, tenant: str, challenge_id: str):
        with self.conn() as c:
            row = c.execute(
                "SELECT * FROM challenges WHERE tenant_id=? AND id=?", (tenant, challenge_id)
            ).fetchone()
            c.execute(
                "UPDATE challenges SET used_at=? WHERE tenant_id=? AND id=?",
                (now(), tenant, challenge_id),
            )
            verified_until = datetime.now(timezone.utc).replace(year=datetime.now(timezone.utc).year + 1).isoformat().replace("+00:00", "Z")
            c.execute(
                "UPDATE sites SET status='VERIFIED',verified_until=? WHERE tenant_id=? AND id=?",
                (verified_until, tenant, row["site_id"]),
            )
            return c.execute(
                "SELECT * FROM sites WHERE tenant_id=? AND id=?", (tenant, row["site_id"])
            ).fetchone()

    def scan(self, tenant: str, site_id: str, commit_sha: str, policy: str):
        scan_id, job_id = str(uuid.uuid4()), str(uuid.uuid4())
        with self.conn() as c:
            c.execute(
                "INSERT INTO scans VALUES(?,?,?,?,?,?,?,?)",
                (tenant, scan_id, site_id, commit_sha, policy, "PENDING", now(), job_id),
            )
        return self.get_scan(tenant, scan_id)

    def get_scan(self, tenant: str, scan_id: str):
        with self.conn() as c:
            return c.execute(
                "SELECT * FROM scans WHERE tenant_id=? AND id=?", (tenant, scan_id)
            ).fetchone()

    def finish_scan(self, tenant: str, scan_id: str) -> None:
        finding_id = str(uuid.uuid4())
        fingerprint = hashlib.sha256(b"fixture.local:/main:img-alt").hexdigest()
        with self.conn() as c:
            c.execute(
                "INSERT INTO findings VALUES(?,?,?,?,?,?,?,?)",
                (tenant, finding_id, scan_id, "image-alt", "SERIOUS", "img#hero", fingerprint, 1),
            )
            c.execute(
                "UPDATE scans SET status='SUCCEEDED' WHERE tenant_id=? AND id=?",
                (tenant, scan_id),
            )

    def findings(self, tenant: str, scan_id: str):
        with self.conn() as c:
            return c.execute(
                "SELECT * FROM findings WHERE tenant_id=? AND scan_id=?", (tenant, scan_id)
            ).fetchall()

    def finding(self, tenant: str, finding_id: str):
        with self.conn() as c:
            return c.execute(
                "SELECT * FROM findings WHERE tenant_id=? AND id=?", (tenant, finding_id)
            ).fetchone()

    def proposal(self, tenant: str, finding_id: str, base_sha: str, patch: str):
        proposal_id = str(uuid.uuid4())
        with self.conn() as c:
            c.execute(
                "INSERT INTO proposals VALUES(?,?,?,?,?,?,?,?)",
                (tenant, proposal_id, finding_id, base_sha, patch, "PENDING_RETEST", "NOT_RUN", 1),
            )
        return self.proposal_get(tenant, proposal_id)

    def proposal_get(self, tenant: str, proposal_id: str):
        with self.conn() as c:
            return c.execute(
                "SELECT * FROM proposals WHERE tenant_id=? AND id=?", (tenant, proposal_id)
            ).fetchone()

    def retest(self, tenant: str, proposal_id: str, commit_sha: str, expected_version: int):
        row = self.proposal_get(tenant, proposal_id)
        if not row:
            return None, "NOT_FOUND"
        if row["version"] != expected_version:
            return row, "STALE"
        if row["base_sha"] != commit_sha:
            return row, "REVISION_MISMATCH"
        with self.conn() as c:
            c.execute(
                "UPDATE proposals SET retest_status='PASSED',status='PENDING_REVIEW' WHERE tenant_id=? AND id=? AND version=?",
                (tenant, proposal_id, expected_version),
            )
        return self.proposal_get(tenant, proposal_id), "OK"

    def review(self, tenant: str, proposal_id: str, reviewer: str, patch: str, decision: str, manual: str, version: int):
        row = self.proposal_get(tenant, proposal_id)
        if not row:
            return None, "NOT_FOUND"
        if row["version"] != version:
            return row, "STALE"
        if row["patch_sha"] != patch:
            return row, "DIGEST_MISMATCH"
        review_id = str(uuid.uuid4())
        status = "APPROVED" if decision == "approve" and manual == "passed" else "REJECTED"
        with self.conn() as c:
            c.execute(
                "INSERT INTO reviews VALUES(?,?,?,?,?,?,?)",
                (tenant, review_id, proposal_id, reviewer, decision, manual, version),
            )
            c.execute(
                "UPDATE proposals SET status=? WHERE tenant_id=? AND id=? AND version=?",
                (status, tenant, proposal_id, version),
            )
        return (review_id, status), "OK"

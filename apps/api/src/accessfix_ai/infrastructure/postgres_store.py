"""PostgreSQL runtime adapter; migrations are applied separately by the migration role."""
from __future__ import annotations

import inspect
import json
import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from functools import wraps
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from accessfix_ai.infrastructure.security_catalog import verify_tenant_catalog
from accessfix_ai.infrastructure.store import Store, now, later, validate_attempt_budget

TENANT_CONTEXT = ContextVar("accessfix_tenant", default=None)
ROLE = "fw_accessfix_ai_rw"
ALIASES = {"challenges": "verification_challenges", "scans": "scan_jobs"}
COLUMN_ALIASES = {"origin": "canonical_origin", "repo_id": "repository_id", "token_hash": "token_sha256", "commit_sha": "repo_commit_sha", "policy_sha": "network_policy_sha256"}
ACTIVE_CONNECTION = ContextVar("accessfix_connection", default=None)
INSERT_COLUMNS = {"sites": "tenant_id,id,origin,repo_id,status,verified_until", "challenges": "tenant_id,id,site_id,token_hash,expires_at,used_at", "findings": "tenant_id,id,scan_id,rule_id,severity,selector,fingerprint,manual_required", "proposals": "tenant_id,id,finding_id,base_sha,patch_sha,status,retest_status,version", "reviews": "tenant_id,id,proposal_id,reviewer_id,decision,manual_status,version", "idempotency_keys": "tenant_id,principal,action,key,request_hash,resource_id,response_status"}


class Row(dict):
    def __getitem__(self, key):
        return list(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


def normalize(row):
    if row is None:
        return None
    return Row({({value:key for key,value in COLUMN_ALIASES.items()} | {"verification_status":"status"}).get(key,key): str(value) if isinstance(value, UUID) else value.isoformat().replace("+00:00", "Z") if isinstance(value, datetime) else json.dumps(value, sort_keys=True, separators=(",", ":")) if isinstance(value, (dict,list)) else value for key, value in row.items()})


class Cursor:
    def __init__(self, cursor):
        self.cursor = cursor
        self.rowcount = cursor.rowcount

    def fetchone(self):
        return normalize(self.cursor.fetchone())

    def fetchall(self):
        return [normalize(row) for row in self.cursor.fetchall()]


class Connection:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, statement, parameters=()):
        for table, columns in INSERT_COLUMNS.items():
            statement = re.sub(r"\bINTO " + table + r" VALUES", "INTO " + table + "(" + columns + ") VALUES", statement)
        if re.search(r"\b(?:INTO|FROM|UPDATE) sites\b", statement):
            statement = re.sub(r"\bstatus\b", "verification_status", statement)
        for source,target in COLUMN_ALIASES.items():
            statement = re.sub(r"\b" + source + r"\b",target,statement)
        for source, target in ALIASES.items():
            statement = re.sub(r"\b" + source + r"\b", target, statement)
        statement = statement.replace("ORDER BY rowid", "ORDER BY id")
        if statement.startswith("INSERT OR IGNORE INTO"):
            statement = statement.replace("INSERT OR IGNORE INTO", "INSERT INTO", 1) + " ON CONFLICT DO NOTHING"
        statement = statement.replace("?", "%s")
        try:
            # Reads and SET LOCAL do not require a write savepoint. Read errors
            # roll back the owning transaction before the pool reuses a connection.
            if statement.lstrip().upper().startswith(("SELECT ", "SET ")):
                return Cursor(self.connection.execute(statement, parameters))
            # A savepoint preserves SQLite's recoverable statement-failure semantics.
            with self.connection.transaction():
                cursor = self.connection.execute(statement, parameters)
            return Cursor(cursor)
        except psycopg.IntegrityError as error:
            raise sqlite3.IntegrityError("Database integrity constraint rejected the command") from error


def tenant_method(method):
    @wraps(method)
    def wrapped(self, tenant, *args, **kwargs):
        tenant = str(UUID(str(tenant)))
        token = TENANT_CONTEXT.set(tenant)
        try:
            return method(self, tenant, *args, **kwargs)
        finally:
            TENANT_CONTEXT.reset(token)
    return wrapped


class PostgresStore(Store):
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.lock = threading.RLock()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as db:
            role = db.execute("SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname=current_user").fetchone()
            if any(role.values()):
                raise ValueError("Runtime must not use a superuser, BYPASSRLS, CREATEROLE or CREATEDB role")
            if not db.execute("SELECT pg_has_role(current_user, %s, 'MEMBER') AS allowed", (ROLE,)).fetchone()["allowed"]:
                raise ValueError("Runtime login must be a member of the tenant application role")
            if db.execute("SELECT 1 FROM pg_tables WHERE schemaname=current_schema() AND tableowner IN (current_user, %s) AND tablename IN ('tenants','sites','verification_challenges','scan_jobs','findings','proposals','reviews','memberships','idempotency_keys')", (ROLE,)).fetchone():
                raise ValueError("Runtime must not own product tables")
            attributes = db.execute("SELECT rolsuper, rolbypassrls, rolcanlogin, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname=%s", (ROLE,)).fetchone()
            if not attributes or any(attributes.values()):
                raise ValueError("Tenant group role must be NOLOGIN, NOSUPERUSER and NOBYPASSRLS")
            verify_tenant_catalog(db)
            if not db.execute("SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='scan_jobs' AND column_name='lease_until'").fetchone():
                raise ValueError("Apply migration 002 with the migration role before starting runtime")
            if not db.execute("SELECT 1 FROM information_schema.tables WHERE table_schema=current_schema() AND table_name='scan_sources'").fetchone():
                raise ValueError("Apply migration 003 before starting runtime")
            if not db.execute("SELECT 1 FROM information_schema.tables WHERE table_schema=current_schema() AND table_name='proposal_sources'").fetchone():
                raise ValueError("Apply migration 004 before starting runtime")
            if db.execute("SELECT 1 FROM pg_tables WHERE schemaname=current_schema() AND tablename='proposal_sources' AND tableowner IN (current_user, %s)", (ROLE,)).fetchone():
                raise ValueError("Runtime must not own product patch tables")
            if db.execute("SELECT 1 FROM pg_tables WHERE schemaname=current_schema() AND tablename='scan_sources' AND tableowner IN (current_user, %s)", (ROLE,)).fetchone():
                raise ValueError("Runtime must not own product source tables")

        self._pool = ConnectionPool(
            dsn, kwargs={"row_factory": dict_row, "connect_timeout": 5,
                         "prepare_threshold": None},
            min_size=1, max_size=4, timeout=5, max_waiting=16,
            # Reject and replace dead idle connections before exposing them to
            # readiness checks or tenant-scoped application transactions.
            check=ConnectionPool.check_connection,
            open=False, name="accessfix-ai-runtime",
        )

    def readiness_check(self):
        """Check database health through the already-bounded runtime connection pool."""
        self._pool.open()
        with self._pool.connection(timeout=3) as db:
            row = db.execute("SELECT 1 AS alive").fetchone()
            if not row or row["alive"] != 1:
                raise RuntimeError("READINESS_DATABASE_CHECK_FAILED")

    def start_pool(self):
        self._pool.open(wait=True, timeout=8)

    def close(self):
        self._pool.close()

    @tenant_method
    def session_active(self, tenant, user, session_id):
        with self.conn() as db:
            db.execute("SELECT set_config('request.jwt.claim.sub', ?, true)", (str(UUID(user)),))
            row = db.execute("SELECT session_active(?, ?) AS active", (str(UUID(session_id)), str(UUID(user)))).fetchone()
            return bool(row["active"])

    @tenant_method
    def member_role(self, tenant, user):
        """Return only the current ACTIVE membership role, inside tenant RLS."""
        try:
            user = str(UUID(str(user)))
        except (ValueError, TypeError):
            return None
        with self.conn() as db:
            row = db.execute(
                "SELECT role FROM memberships WHERE tenant_id=? AND user_id=? AND status='ACTIVE'",
                (tenant, user),
            ).fetchone()
            return str(row["role"]) if row else None

    @tenant_method
    def member(self, tenant, user):
        try:
            user = str(UUID(str(user)))
        except ValueError:
            return False  # No provisioned UUID identity mapping; fail closed before SQL.
        with self.conn() as db:
            return db.execute("SELECT 1 FROM memberships WHERE tenant_id=? AND user_id=? AND status='ACTIVE'", (tenant, user)).fetchone() is not None

    @contextmanager
    def conn(self, tenant=None, *, repeatable_read=False):
        tenant = tenant or TENANT_CONTEXT.get()
        if tenant is None:
            raise ValueError("A transaction requires an explicit tenant context")
        tenant = str(UUID(str(tenant)))
        active = ACTIVE_CONNECTION.get()
        if active:
            if active[0] != id(self) or active[1] != tenant:
                raise ValueError("Nested transaction cannot change store or tenant")
            if repeatable_read:
                raise ValueError("A repeatable-read snapshot requires an owning transaction")
            yield active[2]
            return
        self._pool.open()
        with self._pool.connection() as db:
            if repeatable_read:
                db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            db.execute("SET LOCAL ROLE fw_accessfix_ai_rw")
            db.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant,))
            # Retain per-tenant serialization across reused connections.
            db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (tenant,))
            connection = Connection(db)
            token = ACTIVE_CONNECTION.set((id(self), tenant, connection))
            try:
                yield connection
            finally:
                ACTIVE_CONNECTION.reset(token)

    def seed(self):
        raise ValueError("PostgreSQL provisioning requires a separate migration/provisioning role")
    def claim_scan(self, lease_seconds=5.0, timeout_seconds=30.0, *, max_attempts=3):
        validate_attempt_budget(max_attempts)
        tenants = [str(UUID(value.strip())) for value in os.getenv("ACCESSFIX_WORKER_TENANTS", "").split(",") if value.strip()]
        for tenant in tenants:
            with self.conn(tenant) as db:
                current = now()
                db.execute("UPDATE scans SET status=CASE WHEN cancel_requested=1 THEN 'CANCELLED' ELSE 'FAILED' END, "
                           "last_error_code=CASE WHEN cancel_requested=1 THEN 'CANCELLED' ELSE 'MAX_ATTEMPTS_EXCEEDED' END, "
                           "lease_until=NULL,timeout_at=NULL WHERE tenant_id=? AND attempt_count>=? AND "
                           "(status='PENDING' OR (status='RUNNING' AND lease_until IS NOT NULL AND lease_until<?))",
                           (tenant, max_attempts, current))
                row = db.execute("SELECT * FROM scans WHERE attempt_count<? AND (status='PENDING' OR (status='RUNNING' AND lease_until IS NOT NULL AND lease_until<?)) ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED", (max_attempts, current)).fetchone()
                if row:
                    db.execute("UPDATE scans SET status='RUNNING',attempt_count=attempt_count+1,lease_until=?,timeout_at=?,last_error_code=NULL WHERE tenant_id=? AND id=?", (later(lease_seconds),later(timeout_seconds),tenant,row["id"]))
                    return db.execute("SELECT * FROM scans WHERE tenant_id=? AND id=?",(tenant,row["id"])).fetchone()
        return None


for name, method in inspect.getmembers(Store, predicate=inspect.isfunction):
    parameters = list(inspect.signature(method).parameters)
    if len(parameters) > 1 and parameters[1] == "tenant" and name not in PostgresStore.__dict__:
        setattr(PostgresStore, name, tenant_method(method))

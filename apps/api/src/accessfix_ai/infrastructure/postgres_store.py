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

from accessfix_ai.infrastructure.store import Store, now, later

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
            if db.execute("SELECT 1 FROM pg_tables WHERE schemaname=current_schema() AND tableowner IN (current_user, %s) AND tablename IN ('sites','verification_challenges','scan_jobs','findings','proposals','reviews','memberships','idempotency_keys')", (ROLE,)).fetchone():
                raise ValueError("Runtime must not own product tables")
            attributes = db.execute("SELECT rolsuper, rolbypassrls, rolcanlogin, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname=%s", (ROLE,)).fetchone()
            if not attributes or any(attributes.values()):
                raise ValueError("Tenant group role must be NOLOGIN, NOSUPERUSER and NOBYPASSRLS")
            if not db.execute("SELECT 1 FROM information_schema.columns WHERE table_name='scan_jobs' AND column_name='lease_until'").fetchone():
                raise ValueError("Apply migration 002 with the migration role before starting runtime")

    @tenant_method
    def member(self, tenant, user):
        try:
            user = str(UUID(str(user)))
        except ValueError:
            return False  # No provisioned UUID identity mapping; fail closed before SQL.
        with self.conn() as db:
            return db.execute("SELECT 1 FROM memberships WHERE tenant_id=? AND user_id=? AND status='ACTIVE'", (tenant, user)).fetchone() is not None

    @contextmanager
    def conn(self, tenant=None):
        tenant = tenant or TENANT_CONTEXT.get()
        if tenant is None:
            raise ValueError("A transaction requires an explicit tenant context")
        tenant = str(UUID(str(tenant)))
        active = ACTIVE_CONNECTION.get()
        if active:
            if active[0] != id(self) or active[1] != tenant:
                raise ValueError("Nested transaction cannot change store or tenant")
            yield active[2]
            return
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as db:
            db.execute("SET LOCAL ROLE fw_accessfix_ai_rw")
            db.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant,))
            # Conservative serialization for this low-volume adapter. No pooling.
            db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (tenant,))
            connection = Connection(db)
            token = ACTIVE_CONNECTION.set((id(self), tenant, connection))
            try:
                yield connection
            finally:
                ACTIVE_CONNECTION.reset(token)

    def seed(self):
        raise ValueError("PostgreSQL provisioning requires a separate migration/provisioning role")
    def claim_scan(self, lease_seconds=5.0, timeout_seconds=30.0):
        tenants = [str(UUID(value.strip())) for value in os.getenv("ACCESSFIX_WORKER_TENANTS", "").split(",") if value.strip()]
        for tenant in tenants:
            with self.conn(tenant) as db:
                current = now()
                row = db.execute("SELECT * FROM scans WHERE status='PENDING' OR (status='RUNNING' AND lease_until IS NOT NULL AND lease_until<?) ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED", (current,)).fetchone()
                if row:
                    db.execute("UPDATE scans SET status='RUNNING',attempt_count=attempt_count+1,lease_until=?,timeout_at=?,last_error_code=NULL WHERE tenant_id=? AND id=?", (later(lease_seconds),later(timeout_seconds),tenant,row["id"]))
                    return db.execute("SELECT * FROM scans WHERE tenant_id=? AND id=?",(tenant,row["id"])).fetchone()
        return None


for name, method in inspect.getmembers(Store, predicate=inspect.isfunction):
    parameters = list(inspect.signature(method).parameters)
    if len(parameters) > 1 and parameters[1] == "tenant" and name not in PostgresStore.__dict__:
        setattr(PostgresStore, name, tenant_method(method))

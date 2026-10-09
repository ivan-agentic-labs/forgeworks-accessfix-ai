#!/usr/bin/env bash
set -euo pipefail

# This test is deliberately restricted to a local, disposable database.
[[ "${G1_DISPOSABLE_DB:-}" == 'yes' ]] || { echo 'G1_DISPOSABLE_DB=yes required' >&2; exit 2; }
[[ "${PGHOST:-}" == '127.0.0.1' ]] || { echo 'only 127.0.0.1 is allowed' >&2; exit 2; }
[[ "${PGDATABASE:-}" == 'forgeworks_g1' ]] || { echo 'only disposable database forgeworks_g1 is allowed' >&2; exit 2; }
[[ "${PGUSER:-}" == 'postgres' ]] || { echo 'bootstrap must run as disposable postgres owner' >&2; exit 2; }
command -v psql >/dev/null || { echo 'psql unavailable' >&2; exit 2; }

root="$(cd "$(dirname "$0")/.." && pwd)"
# The migration is the only schema source used here. No remote host or third-party target is contacted.
psql -X -v ON_ERROR_STOP=1 -f "$root/migrations/versions/001_accessfix_mvp.sql"

psql -X -v ON_ERROR_STOP=1 <<'SQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fw_accessfix_ai_rw') THEN
    CREATE ROLE fw_accessfix_ai_rw NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname = 'fw_accessfix_ai_rw'
      AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)
  ) THEN
    RAISE EXCEPTION 'unsafe application role attributes';
  END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO fw_accessfix_ai_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON sites, scan_jobs, findings TO fw_accessfix_ai_rw;

-- Seed two tenants as the migration owner. The application role below is not the owner.
INSERT INTO tenants(id, slug, status) VALUES
  ('10000000-0000-0000-0000-000000000001', 'rls-a', 'ACTIVE'),
  ('10000000-0000-0000-0000-000000000002', 'rls-b', 'ACTIVE')
ON CONFLICT (id) DO NOTHING;
INSERT INTO sites(tenant_id, id, canonical_origin, repository_id, verification_status)
VALUES
  ('10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', 'http://fixture.local', '30000000-0000-0000-0000-000000000001', 'VERIFIED'),
  ('10000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000002', 'http://fixture.local', '30000000-0000-0000-0000-000000000002', 'VERIFIED')
ON CONFLICT (tenant_id, id) DO NOTHING;
INSERT INTO scan_jobs(tenant_id, id, site_id, repo_commit_sha, network_policy_sha256, status, budget_pages)
VALUES
  ('10000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', repeat('a', 40), repeat('b', 64), 'SUCCEEDED', 1),
  ('10000000-0000-0000-0000-000000000002', '40000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000002', repeat('a', 40), repeat('b', 64), 'SUCCEEDED', 1)
ON CONFLICT (tenant_id, id) DO NOTHING;
INSERT INTO findings(tenant_id, id, scan_id, rule_id, selector, fingerprint, severity)
VALUES
  ('10000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000001', 'image-alt', 'img#tenant-a', repeat('c', 64), 'SERIOUS'),
  ('10000000-0000-0000-0000-000000000002', '50000000-0000-0000-0000-000000000002', '40000000-0000-0000-0000-000000000002', 'image-alt', 'img#tenant-b', repeat('c', 64), 'SERIOUS')
ON CONFLICT (tenant_id, id) DO NOTHING;

BEGIN;
SET ROLE fw_accessfix_ai_rw;
SET LOCAL app.tenant_id = '10000000-0000-0000-0000-000000000001';
DO $$
BEGIN
  IF current_user <> 'fw_accessfix_ai_rw' THEN
    RAISE EXCEPTION 'test did not run as application role';
  END IF;
END
$$;

DO $$
DECLARE changed integer;
BEGIN
  IF (SELECT count(*) FROM sites) <> 1 OR EXISTS (SELECT 1 FROM sites WHERE tenant_id <> '10000000-0000-0000-0000-000000000001') THEN
    RAISE EXCEPTION 'cross-tenant site read was visible';
  END IF;
  IF (SELECT count(*) FROM scan_jobs) <> 1 OR EXISTS (SELECT 1 FROM scan_jobs WHERE tenant_id <> '10000000-0000-0000-0000-000000000001') THEN
    RAISE EXCEPTION 'cross-tenant scan read was visible';
  END IF;
  IF (SELECT count(*) FROM findings) <> 1 OR EXISTS (SELECT 1 FROM findings WHERE tenant_id <> '10000000-0000-0000-0000-000000000001') THEN
    RAISE EXCEPTION 'cross-tenant finding read was visible';
  END IF;
  UPDATE sites SET canonical_origin = 'http://should-not-change.invalid' WHERE tenant_id = '10000000-0000-0000-0000-000000000002';
  GET DIAGNOSTICS changed = ROW_COUNT;
  IF changed <> 0 THEN
    RAISE EXCEPTION 'cross-tenant update changed % rows', changed;
  END IF;
END
$$;

DO $$
BEGIN
  BEGIN
    INSERT INTO findings(tenant_id, id, scan_id, rule_id, selector, fingerprint, severity)
    VALUES ('10000000-0000-0000-0000-000000000002', '50000000-0000-0000-0000-000000000099', '40000000-0000-0000-0000-000000000002', 'blocked', 'img#blocked', repeat('d', 64), 'SERIOUS');
    RAISE EXCEPTION 'cross-tenant insert unexpectedly succeeded';
  EXCEPTION WHEN insufficient_privilege THEN
    NULL;
  END;
END
$$;
COMMIT;

RESET ROLE;
SELECT 'RLS tenant isolation negative test: PASS' AS result;
SQL

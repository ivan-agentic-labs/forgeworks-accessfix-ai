-- Staging only: fresh private schema in the connected Supabase project.
-- Apply exactly once through the migration/provisioning role. Never at app startup.
CREATE SCHEMA fw_accessfix_ai;
REVOKE ALL ON SCHEMA fw_accessfix_ai FROM PUBLIC, anon, authenticated;
SET LOCAL search_path TO fw_accessfix_ai, pg_catalog;
ALTER DEFAULT PRIVILEGES IN SCHEMA fw_accessfix_ai REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA fw_accessfix_ai REVOKE ALL ON FUNCTIONS FROM PUBLIC, anon, authenticated;
-- Source: 001_accessfix_mvp.sql
-- AccessFix MVP disposable migration. The review-only FK addendum is intentionally excluded.
CREATE TABLE IF NOT EXISTS tenants(id uuid PRIMARY KEY,slug text UNIQUE NOT NULL,status text NOT NULL);
CREATE TABLE IF NOT EXISTS sites(tenant_id uuid NOT NULL,id uuid NOT NULL,canonical_origin text NOT NULL,repository_id uuid NOT NULL,verification_status text NOT NULL,verified_until timestamptz,PRIMARY KEY(tenant_id,id),UNIQUE(tenant_id,canonical_origin),FOREIGN KEY(tenant_id) REFERENCES tenants(id));
CREATE TABLE IF NOT EXISTS verification_challenges(tenant_id uuid NOT NULL,id uuid NOT NULL,site_id uuid NOT NULL,token_sha256 char(64) NOT NULL,expires_at timestamptz NOT NULL,used_at timestamptz,PRIMARY KEY(tenant_id,id),FOREIGN KEY(tenant_id,site_id) REFERENCES sites(tenant_id,id));
CREATE TABLE IF NOT EXISTS scan_jobs(tenant_id uuid NOT NULL,id uuid NOT NULL,site_id uuid NOT NULL,repo_commit_sha text NOT NULL,network_policy_sha256 char(64) NOT NULL,status text NOT NULL,budget_pages integer NOT NULL,PRIMARY KEY(tenant_id,id),FOREIGN KEY(tenant_id,site_id) REFERENCES sites(tenant_id,id));
CREATE TABLE IF NOT EXISTS findings(tenant_id uuid NOT NULL,id uuid NOT NULL,scan_id uuid NOT NULL,rule_id text NOT NULL,selector text NOT NULL,fingerprint char(64) NOT NULL,severity text NOT NULL,PRIMARY KEY(tenant_id,id),UNIQUE(tenant_id,scan_id,fingerprint),FOREIGN KEY(tenant_id,scan_id) REFERENCES scan_jobs(tenant_id,id));
ALTER TABLE sites ENABLE ROW LEVEL SECURITY; ALTER TABLE scan_jobs ENABLE ROW LEVEL SECURITY; ALTER TABLE findings ENABLE ROW LEVEL SECURITY;
CREATE POLICY sites_tenant ON sites USING(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
CREATE POLICY scan_jobs_tenant ON scan_jobs USING(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
CREATE POLICY findings_tenant ON findings USING(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);

-- Source: 002_accessfix_runtime.sql
-- Runtime MVP extension; no design-candidate FK addendum or production deployment.
ALTER TABLE scan_jobs ALTER COLUMN budget_pages SET DEFAULT 20;
ALTER TABLE scan_jobs ADD COLUMN created_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE scan_jobs ADD COLUMN job_id uuid;
ALTER TABLE scan_jobs ADD COLUMN attempt_count integer NOT NULL DEFAULT 0;
ALTER TABLE scan_jobs ADD COLUMN lease_until timestamptz;
ALTER TABLE scan_jobs ADD COLUMN last_error_code text;
ALTER TABLE scan_jobs ADD COLUMN cancel_requested integer NOT NULL DEFAULT 0 CHECK(cancel_requested IN (0,1));
ALTER TABLE scan_jobs ADD COLUMN timeout_at timestamptz;
ALTER TABLE findings ADD COLUMN manual_required integer NOT NULL DEFAULT 1 CHECK(manual_required IN (0,1));
CREATE TABLE memberships(tenant_id uuid NOT NULL REFERENCES tenants(id),user_id uuid NOT NULL,role text NOT NULL,status text NOT NULL,PRIMARY KEY(tenant_id,user_id));
CREATE TABLE proposals(tenant_id uuid NOT NULL,id uuid NOT NULL,finding_id uuid NOT NULL,base_sha text NOT NULL,patch_sha char(64) NOT NULL,status text NOT NULL,retest_status text NOT NULL,version integer NOT NULL,PRIMARY KEY(tenant_id,id),UNIQUE(tenant_id,finding_id,base_sha),FOREIGN KEY(tenant_id,finding_id) REFERENCES findings(tenant_id,id));
CREATE TABLE reviews(tenant_id uuid NOT NULL,id uuid NOT NULL,proposal_id uuid NOT NULL,reviewer_id uuid NOT NULL,decision text NOT NULL,manual_status text NOT NULL,version integer NOT NULL,PRIMARY KEY(tenant_id,id),UNIQUE(tenant_id,proposal_id,reviewer_id,version),FOREIGN KEY(tenant_id,proposal_id) REFERENCES proposals(tenant_id,id));
CREATE TABLE idempotency_keys(tenant_id uuid NOT NULL REFERENCES tenants(id),principal text NOT NULL,action text NOT NULL,key text NOT NULL,request_hash char(64) NOT NULL,resource_id uuid NOT NULL,response_status integer NOT NULL DEFAULT 0,PRIMARY KEY(tenant_id,principal,action,key));
CREATE ROLE fw_accessfix_ai_rw NOLOGIN NOSUPERUSER NOBYPASSRLS;
GRANT USAGE ON SCHEMA fw_accessfix_ai TO fw_accessfix_ai_rw;
DO $$
DECLARE tbl text;
BEGIN
  FOREACH tbl IN ARRAY ARRAY['sites','verification_challenges','scan_jobs','findings','proposals','reviews','memberships','idempotency_keys']
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',tbl);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',tbl);
    IF tbl NOT IN ('sites','scan_jobs','findings') THEN
      EXECUTE format('CREATE POLICY tenant_boundary ON %I USING (tenant_id=nullif(current_setting(''app.tenant_id'',true),'''')::uuid) WITH CHECK (tenant_id=nullif(current_setting(''app.tenant_id'',true),'''')::uuid)',tbl);
    END IF;
    EXECUTE format('GRANT SELECT ON %I TO fw_accessfix_ai_rw',tbl);
    IF tbl <> 'memberships' THEN
      EXECUTE format('GRANT INSERT ON %I TO fw_accessfix_ai_rw',tbl);
    END IF;
    IF tbl IN ('sites','verification_challenges','scan_jobs','proposals') THEN
      EXECUTE format('GRANT UPDATE,DELETE ON %I TO fw_accessfix_ai_rw',tbl);
    END IF;
  END LOOP;
END $$;

-- Source: 003_accessfix_source_snapshots.sql
-- Immutable tenant-scoped local source evidence; not remote revision verification.
CREATE TABLE scan_sources(
  tenant_id uuid NOT NULL,
  scan_id uuid NOT NULL,
  source_sha char(64) NOT NULL CHECK(source_sha ~ '^[0-9a-f]{64}$'),
  source_html text NOT NULL CHECK(octet_length(source_html) <= 1048576),
  PRIMARY KEY(tenant_id,scan_id),
  FOREIGN KEY(tenant_id,scan_id) REFERENCES scan_jobs(tenant_id,id)
);
ALTER TABLE scan_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE scan_sources FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_boundary ON scan_sources
USING (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid)
WITH CHECK (tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
GRANT SELECT,INSERT ON scan_sources TO fw_accessfix_ai_rw;

-- Source: 004_accessfix_proposal_sources.sql
-- Actual immutable local patch content. Remote Git revision binding is separate.
CREATE TABLE proposal_sources(
 tenant_id uuid NOT NULL, proposal_id uuid NOT NULL,
 source_sha char(64) NOT NULL, patched_sha char(64) NOT NULL,
 patch_text text NOT NULL, patched_html text NOT NULL CHECK(octet_length(patched_html)<=1048576),
 alt_text text NOT NULL CHECK(length(alt_text) BETWEEN 1 AND 500),
 PRIMARY KEY(tenant_id,proposal_id),
 FOREIGN KEY(tenant_id,proposal_id) REFERENCES proposals(tenant_id,id)
);
ALTER TABLE proposal_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposal_sources FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_boundary ON proposal_sources
USING(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid)
WITH CHECK(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
GRANT SELECT,INSERT ON proposal_sources TO fw_accessfix_ai_rw;

-- Auth-managed tables remain untouched. Return only a boolean for the JWT-bound user.
CREATE FUNCTION fw_accessfix_ai.session_active(session_id uuid, user_id uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
 SELECT auth.uid() = $2 AND EXISTS (
   SELECT 1 FROM auth.sessions s JOIN auth.users u ON u.id=s.user_id
   WHERE s.id=$1 AND s.user_id=$2
     AND (s.not_after IS NULL OR s.not_after > now())
     AND u.deleted_at IS NULL AND (u.banned_until IS NULL OR u.banned_until <= now())
 );
$$;
REVOKE ALL ON FUNCTION fw_accessfix_ai.session_active(uuid, uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION fw_accessfix_ai.session_active(uuid, uuid) TO fw_accessfix_ai_rw;
GRANT USAGE ON SCHEMA fw_accessfix_ai TO fw_accessfix_ai_rw;
-- Restrict all product tables, including unexposed tenants, as defense in depth.
DO $$ DECLARE t record; BEGIN
 FOR t IN SELECT tablename FROM pg_tables WHERE schemaname='fw_accessfix_ai' LOOP
   EXECUTE format('ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY','fw_accessfix_ai',t.tablename);
   EXECUTE format('ALTER TABLE %I.%I FORCE ROW LEVEL SECURITY','fw_accessfix_ai',t.tablename);
   EXECUTE format('REVOKE ALL ON %I.%I FROM PUBLIC, anon, authenticated','fw_accessfix_ai',t.tablename);
 END LOOP;
END $$;
RESET search_path;

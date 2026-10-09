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
GRANT USAGE ON SCHEMA public TO fw_accessfix_ai_rw;
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

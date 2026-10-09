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

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

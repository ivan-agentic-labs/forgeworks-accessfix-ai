-- Additive index for scan jobs by verified site. Apply only with the migration role
-- and search_path set to this product's private schema, pg_catalog.
CREATE INDEX IF NOT EXISTS idx_scan_jobs_tenant_site ON scan_jobs (tenant_id, site_id);

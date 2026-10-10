-- Additive FK lookup indexes for this product's small staging tables.
-- Apply after bootstrap and prior numbered staging migrations, in one transaction
-- with search_path set to the product schema, pg_catalog. Fail on lock contention.
SET LOCAL lock_timeout = '3s';
SET LOCAL statement_timeout = '30s';
CREATE INDEX IF NOT EXISTS idx_verification_challenges_tenant_site ON verification_challenges (tenant_id, site_id);

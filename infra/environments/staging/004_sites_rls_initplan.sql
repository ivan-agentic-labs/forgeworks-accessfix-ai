-- 2026-10-11: same tenant predicate as the existing sites_tenant policy.
-- The tenant context is query-constant. Wrapping current_setting() in SELECT
-- permits a PostgreSQL initPlan instead of evaluating it per candidate row.
-- Requires the existing sites_tenant policy and migration/provisioning role.
-- Apply with search_path = fw_accessfix_ai, pg_catalog on connected staging.
-- Disposable test runs against the dedicated public schema of its throwaway DB.
ALTER POLICY sites_tenant ON sites
  USING (tenant_id = (SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid))
  WITH CHECK (tenant_id = (SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid));

-- Follow-up: put the query-constant subselect directly around current_setting().
-- Keep the same NULL/fail-closed tenant equality in USING and WITH CHECK.
-- Apply only as an additive policy migration with search_path fw_accessfix_ai,pg_catalog.
ALTER POLICY sites_tenant ON sites
  USING (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid)
  WITH CHECK (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid);

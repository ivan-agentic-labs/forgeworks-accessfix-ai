-- Optimize only 9 identified ALL / TO PUBLIC tenant equality policies.
-- Their USING and WITH CHECK expressions are semantically unchanged.
-- Migration role, search_path=fw_accessfix_ai,pg_catalog; disposable CI uses public.
ALTER POLICY findings_tenant ON findings USING (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid) WITH CHECK (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid);
ALTER POLICY tenant_boundary ON idempotency_keys USING (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid) WITH CHECK (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid);
ALTER POLICY tenant_boundary ON memberships USING (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid) WITH CHECK (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid);
ALTER POLICY tenant_boundary ON proposal_sources USING (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid) WITH CHECK (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid);
ALTER POLICY tenant_boundary ON proposals USING (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid) WITH CHECK (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid);
ALTER POLICY tenant_boundary ON reviews USING (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid) WITH CHECK (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid);
ALTER POLICY scan_jobs_tenant ON scan_jobs USING (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid) WITH CHECK (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid);
ALTER POLICY tenant_boundary ON scan_sources USING (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid) WITH CHECK (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid);
ALTER POLICY tenant_boundary ON verification_challenges USING (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid) WITH CHECK (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid);

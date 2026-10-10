-- Reviewed rollback for this exact 2026-10-11 staging viewer-only grant.
-- Never execute after adding independent user permissions without reconciliation.
DELETE FROM fw_accessfix_ai.memberships m
USING auth.users u, fw_accessfix_ai.tenants t
WHERE m.tenant_id=t.id AND m.user_id=u.id
  AND m.role='viewer' AND m.status='ACTIVE'
  AND t.slug LIKE 'fw-live-20261010-%'
  AND u.raw_app_meta_data->'forgeworks'->'accessfix-ai'->>'tenant_id'=t.id::text;

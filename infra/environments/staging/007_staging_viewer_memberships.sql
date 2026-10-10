-- Staging only: least-privilege viewer membership for exactly two pre-granted,
-- verified identities in their own two explicitly named staging tenants.
-- Grants come from auth.users.raw_app_meta_data (server owned), never user_metadata.
-- No cross-tenant, editor, approver, owner, or production access is conferred.
DO $$
DECLARE matching_count integer; final_count integer;
BEGIN
  SELECT count(*) INTO matching_count
    FROM auth.users u JOIN fw_accessfix_ai.tenants t ON t.status='ACTIVE'
      AND t.slug LIKE 'fw-live-20261010-%'
      AND u.email_confirmed_at IS NOT NULL
      AND (u.banned_until IS NULL OR u.banned_until < now())
      AND u.last_sign_in_at IS NOT NULL
      AND (u.raw_app_meta_data->'forgeworks'->'accessfix-ai'->'scopes') ? 'job:read'
      AND u.raw_app_meta_data->'forgeworks'->'accessfix-ai'->>'tenant_id'=t.id::text;
  IF matching_count <> 2 THEN
    RAISE EXCEPTION 'Expected exactly two verified pre-granted staging identities; got %', matching_count;
  END IF;
  INSERT INTO fw_accessfix_ai.memberships (tenant_id,user_id,role,status)
  SELECT t.id,u.id,'viewer','ACTIVE'
    FROM auth.users u JOIN fw_accessfix_ai.tenants t ON t.status='ACTIVE'
      AND t.slug LIKE 'fw-live-20261010-%'
      AND u.email_confirmed_at IS NOT NULL
      AND (u.banned_until IS NULL OR u.banned_until < now())
      AND u.last_sign_in_at IS NOT NULL
      AND (u.raw_app_meta_data->'forgeworks'->'accessfix-ai'->'scopes') ? 'job:read'
      AND u.raw_app_meta_data->'forgeworks'->'accessfix-ai'->>'tenant_id'=t.id::text
  ON CONFLICT (tenant_id,user_id) DO NOTHING;
  SELECT count(*) INTO final_count
    FROM fw_accessfix_ai.memberships m
    JOIN auth.users u ON u.id=m.user_id
    JOIN fw_accessfix_ai.tenants t ON t.id=m.tenant_id
   WHERE t.status='ACTIVE'
      AND t.slug LIKE 'fw-live-20261010-%'
      AND u.email_confirmed_at IS NOT NULL
      AND (u.banned_until IS NULL OR u.banned_until < now())
      AND u.last_sign_in_at IS NOT NULL
      AND (u.raw_app_meta_data->'forgeworks'->'accessfix-ai'->'scopes') ? 'job:read'
      AND u.raw_app_meta_data->'forgeworks'->'accessfix-ai'->>'tenant_id'=t.id::text AND m.role='viewer' AND m.status='ACTIVE';
  IF final_count <> 2 THEN
    RAISE EXCEPTION 'Staging viewer membership postcondition failed: %', final_count;
  END IF;
END $$;

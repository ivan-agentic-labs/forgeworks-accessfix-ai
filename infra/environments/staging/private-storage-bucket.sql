-- ForgeWorks staging-only private storage bucket provisioning.
-- Apply through a privileged Supabase operator. No client access policies,
-- no S3 credentials, and no production customer data are created here.
-- Dedicated per-product bucket, max 1 MiB per object.
BEGIN;
INSERT INTO storage.buckets (id, name, public, file_size_limit)
VALUES ('fw-staging-accessfix-ai', 'fw-staging-accessfix-ai', false, 1048576)
ON CONFLICT (id) DO NOTHING;
DO $check$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM storage.buckets
    WHERE id = 'fw-staging-accessfix-ai'
      AND name = 'fw-staging-accessfix-ai'
      AND public IS FALSE
      AND file_size_limit = 1048576
  ) THEN
    RAISE EXCEPTION 'FORGEWORKS_PRIVATE_STAGING_BUCKET_CONFIG_DRIFT';
  END IF;
END
$check$;
COMMIT;
-- No INSERT/SELECT/UPDATE/DELETE policies on storage.objects are granted.
-- Configure S3 access keys only as server-side Railway secrets after approval.

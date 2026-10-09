-- DESIGN CANDIDATE: run ONLY on an isolated disposable PostgreSQL 17 instance.
-- Cluster-level role names are unique per product to avoid cross-product grants.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fw_accessfix_ai_rw') THEN
    CREATE ROLE fw_accessfix_ai_rw NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
  END IF;
END $$;
-- Do not use this role for migrations. Do not grant login or global tables.

-- Reject an existing role that has dangerous attributes. Creation alone is not a proof of safe role state.
DO $$ BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname = 'fw_accessfix_ai_rw'
      AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)
  ) THEN
    RAISE EXCEPTION 'unsafe database role attributes: fw_accessfix_ai_rw';
  END IF;
END $$;

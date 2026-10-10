# Staging identity authorization checkpoint, 2026-10-11

## Evidence, without personal identifiers

A read-only inspection found exactly **two verified accounts** in Supabase Auth, with server-owned product tenant grants matching the two named ForgeWorks staging tenants in each of the five product schemas. The accounts have existing `OWNER` membership rows in every product schema, but **all ten rows are `REVOKED`**, not missing.

Before this discovery, an attempt to add `viewer` memberships using `INSERT ... ON CONFLICT DO NOTHING` was attempted for AccessFix staging. It **failed its transaction postcondition** because the `(tenant_id,user_id)` primary keys already belong to revoked memberships. The PostgreSQL transaction rolled back. Subsequent counts confirmed both AccessFix rows remain `OWNER / REVOKED`. No membership was activated or created. Other schemas received **no** membership changes.

The proposed SQL and corresponding rollback have been removed from the repository to prevent unintentional reactivation or misuse. The authorization history of the revoked rows is not known, so **do not** issue a new grant, overwrite `REVOKED`, or bypass `member_role`.

## Mandatory clearance before live Auth E2E

1. Verify the intended operator/owner for each account and why access was revoked. Do not disclose emails, passwords, tokens or account IDs in public issues.
2. Explicitly decide whether these specific identities may be re-authorized. Prefer fresh, narrowly scoped staging-only test accounts over reversing a historical revocation.
3. Require an independently reviewed user-to-tenant mapping, intended `role`, exact allowed JWT scopes, a revocation/rollback plan and a bounded test window.
4. Use Supabase Auth Admin for identity operations and a dedicated provisioning/migration role for membership writes. Never use a runtime DB login or client-supplied user metadata to grant privileges.
5. Test authenticated read/write authorization, session revocation, and two-tenant isolation using test data only. Record evidence for G3 before any production deployment.

Production gate remains **NO-GO**.

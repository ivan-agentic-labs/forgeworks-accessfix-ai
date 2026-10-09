# Connected staging infrastructure

This is a staging integration, not a production release or G1-E acceptance.

- Supabase project: `fljekuwplgkrpdoajyhn` (Seoul). Product schema: `fw_accessfix_ai`.
- Railway project: `1b35f35d-ad5b-4b93-ad20-ed68251b4589`, staging environment `0395e7ac-10f8-4004-8bb7-ddee901343c7`.
- Apply `supabase-bootstrap.sql` once to a fresh schema using the migration/provisioning role. Apply any numbered staging follow-up SQL afterward. This bootstrap assembles the existing MVP migrations in a private schema; it does not apply the review-only design SQL.
- A separate `fw_accessfix_ai_login` is a member of `fw_accessfix_ai_rw`, is not a table owner, and has no superuser, BYPASSRLS, CREATEROLE or CREATEDB privilege. Its login search_path is `fw_accessfix_ai, pg_catalog`.
- Login passwords, artifact signing material and cursor keys are configured only in Railway variables. They are absent from the source and committed migration history. Migration credentials must never be configured on runtime services.
- All 62 product tables across the five schemas have ENABLE/FORCE RLS. `anon` and `authenticated` have no USAGE on these schemas. The seven advisor INFO notices for no-policy tables represent denied access: the five tenant provisioning tables and two disabled webhook inbox/state tables. The DataReconcile trigger function search_path warning was fixed.
- `/healthz` is process liveness. `/readyz` checks configured auth, public signing keys and current database connectivity. Neither proves complete workflows or customer acceptance.
- The Docker runtime is a non-root CPython 3.12 Linux x86_64 process with a writable disposable runtime directory and 42 exact, hash-locked dependencies. Railway outbound IPv6 is enabled for Supabase direct database access. TLS verifies the host using the system trust store.

## Identity provisioning

There were zero application users in Supabase at verification. Before authenticated end-to-end tests, provision a real test user through Supabase Auth, provision an ACTIVE membership in this product's schema, and set the server-owned grant below through the Auth admin path. Never trust `user_metadata`, accept client-supplied tenant grants, or copy a project service key into a browser.

```json
{"app_metadata":{"forgeworks":{"accessfix-ai":{"tenant_id":"<provisioned-tenant-uuid>","scopes":["<explicit-product-scopes>"]}}}}
```

The API verifies ES256/RS256 against this project's public JWKS, issuer, audience, UUID subject/session, expiration and non-anonymous authenticated role. It then checks the current session (including deleted/banned user and session not_after) through a private SECURITY DEFINER function returning only a boolean for the JWT-bound auth.uid(), and independently checks current product membership. Removed sessions fail 401; unavailable checks fail 503. Provisioned grant changes still require refreshed JWTs; this is not a completed BFF, CSRF, MFA or browser session implementation.

## Verification and limitations

- Exact runtime-lock environment: `101 passed, 2 skipped` from `python -W error -m pytest tests --ignore=tests/e2e -q`. The new offline Supabase suite contains 38 cases. PostgreSQL/disposable runner tests were not rerun locally without their infrastructure, and browser tests were excluded from this local command.
- Static bootstrap, heuristic sensitive-content scan, event/OpenAPI sanity, independent OpenAPI validation and diff whitespace checks passed.
- Live catalog checks confirmed forced RLS, non-owner/non-privileged logins, per-product memberships and no public schema access. A connector attempt to run a role-switched row/session negative proof returned `Invalid or expired requestState`; it is not counted as a passing proof. Existing disposable proofs retain their original source scope.
- Live authenticated login/provisioning, user session revocation, writable business workflows, external artifact storage/scanning/retention, isolated remote execution, live GitHub App effects, production recovery/load/cost and independent acceptance remain open.
- Seed fixture provisioning, development JWT secrets, remote GitHub reads/writes and agent execution are disabled on this staging deployment.

## Rollback

Keep the private database schemas intact when rolling back the app. Select an earlier tested app commit in Railway and verify `/readyz`. Schema deletion, membership changes and credential rotation are separate provisioning operations. Empty staging is not evidence of a successful production restore.

## Current platform checkpoint

All five Railway services and runtime variables are configured. Every GitHub source connection returned `User does not have access to the repo`; no deployment exists. Grant the Railway GitHub App access to the five private repositories under the ivan-agentic-labs account and confirm that account is connected inside Railway. Reconnect the exact source commit after CI verification. See `docs/evidence/STAGING_PLATFORM_CHECKPOINT_2026-10-09.json` for immutable source CI receipts and the remaining test limits.

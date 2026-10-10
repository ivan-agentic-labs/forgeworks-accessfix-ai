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

The Railway GitHub App is installed on ivan-agentic-labs with access limited to the five ForgeWorks repositories. All five services reached terminal SUCCESS in the staging environment on 2026-10-10 (Asia/Jakarta). The 2026-10-10 receipt was pinned at that time. After briefly tracking `main`, staging was deliberately re-pinned on 2026-10-11 to commit `d4b6319255d1540d2e8172e24aabc07de31cdb6b` following green CI. Current Railway source remains pinned: pushes to `main` do **not** automatically deploy. Railway `Wait for CI` has **not** been enabled; promotion requires explicit green CI, change review, and a release action that updates the pinned commit. This pin is a safety guard, not a production release gate or evidence of business acceptance.

The image includes the official Supabase Root 2021 CA. Configure `SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt` alongside the database URL with `sslmode=verify-full&sslrootcert=system`. The bundled psycopg OpenSSL runtime needs this explicit trust-store path. The certificate was downloaded from the project dashboard link, has SHA-256 fingerprint `807025ad50d4ed219d2c9c7d299c004f824eb00cf7f65afef607d07b72e6cafa`, and expires 2031-04-26. Review CA rotation before expiration.

See `docs/evidence/STAGING_DEPLOYMENT_2026-10-10.json` for deployment IDs, source and CI receipts, live smoke checks, and remaining limitations. The earlier checkpoint records the resolved repository-access blocker and is retained as historical evidence. Positive authenticated workflows and user session revocation still require provisioned test identities and have not been accepted.

## Additive foreign-key index rollout

After bootstrap, execute `003_fk_lookup_index.sql` using the migration role with `search_path` set to `fw_accessfix_ai, pg_catalog`. Verify `idx_scan_jobs_tenant_site` on `scan_jobs (tenant_id, site_id)`, rerun the Supabase advisor, and retain rollback: `DROP INDEX IF EXISTS fw_accessfix_ai.idx_scan_jobs_tenant_site;` (only after query-plan review). This closes one index finding, **not** a measured application latency requirement.

## AccessFix sites RLS policy performance change

After independent review, apply `004_sites_rls_initplan.sql` through the migration role using `search_path=fw_accessfix_ai,pg_catalog`. This is an **ALTER POLICY** with the same tenant_id equality predicate, but evaluates `current_setting('app.tenant_id',true)` using a PostgreSQL initPlan. Verify the resulting `pg_policies.qual` and `with_check`, rerun the Supabase advisor, and retain the disposable PostgreSQL RLS negative tests as the security regression proof. Do not claim latency gains without a workload benchmark.

Rollback requires separately reviewed restoration of the original policy predicate:
`ALTER POLICY sites_tenant ON fw_accessfix_ai.sites USING (tenant_id = nullif(current_setting('app.tenant_id', true),'')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id',true),'')::uuid);`.

## Remaining FK index rollout (2026-10-11)

`007_remaining_fk_indexes.sql` adds tenant-prefixed indexes for referencing
foreign keys not covered by existing primary/unique/lookup indexes. The tables
in connected staging are small (each below 128 KiB at review). Apply using the
migration role, the product's private `search_path`, and a single transaction.
Lock and statement timeouts bound this small-table rollout. For a populated
production deployment, separately assess write overhead and use a reviewed
concurrent-index procedure; this staging script is not a production benchmark.

The disposable runtime proof executes the migration twice and verifies exact
index definitions, followed by the existing business-flow and RLS negatives.
Do not drop unused indexes merely to remove advisor INFO notices. Rollback is
limited to the newly named indexes after query-plan review; it requires no
row, membership, constraint, grant or tenant-policy changes.

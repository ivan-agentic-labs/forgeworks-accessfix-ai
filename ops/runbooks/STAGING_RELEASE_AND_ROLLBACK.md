# Staging release and rollback gate

This product's Railway staging source is **commit-pinned**, not branch-auto-deployed. This is a guard against untested code, **not** production readiness.

## Promotion
1. Identify a candidate full Git SHA and review the exact diff, security/privacy impact, dependencies and any migration.
2. Verify all required GitHub Actions completed successfully **for that SHA**, including application tests, contract checks and disposable PostgreSQL/tenant proof. A green workflow on a different commit is not release evidence.
3. If schema changes are necessary, apply an independently reviewed additive migration using the provisioning role. Retain previous schema/API compatibility and a backup/recovery plan. Never apply review-only SQL.
4. In Railway staging, change this service's GitHub source to that **exact full SHA**. Do not reconnect to floating `main` while Wait for CI is disabled.
5. Confirm Railway deployment is `SUCCESS`, `/readyz` passes in an independently observable probe, no crash/restart loop, and the exact promoted SHA matches.
6. Execute consented or synthetic positive/negative API and UI smoke tests including session revocation, cross-tenant denial, upload integrity and the product's business path. If network/identity prevents tests, record **OPEN**, not PASS.
7. Record commit, PR, CI links, migration hash, release/deployment ID, rollback SHA, failure modes and human signoff. Production promotion separately requires gates G3-G6.

## Rollback
- Prior known-running commit before the HTTP body release: `3ffa4e326627122a47fad21ce0fcb0a9ab6ebab8`.
- Current staging HTTP body release commit: `d4b6319255d1540d2e8172e24aabc07de31cdb6b`.
- If a new staging release fails the readiness or functional checks, reconnect this Railway service to the prior verified SHA and verify recovery. Database rollback is **separate** and must not be improvised when data/schema compatibility is unknown.

## Open release blockers
- Staging Auth has two accounts with server-owned product grants but zero ACTIVE product memberships at last check. No account must be granted product access without verified identity, tenant and intended role.
- Supabase leaked-password protection remains disabled according to the security advisor and requires supported Auth administrative configuration.
- Runtime-role RLS checks through the Supabase connector are restricted (permission denied to SET ROLE); disposable CI proofs are narrower than live role verification.
- Direct independent HTTPS `/readyz` probe was unavailable from the evaluation environment. Railway health and startup status do not establish live browser acceptance.
- Dedicated production environment, monitored SLO/load results, incident drills, recovery targets, retention/legal and domain reviewer acceptance are still OPEN. Do not deploy production or use customer data based on staging success.

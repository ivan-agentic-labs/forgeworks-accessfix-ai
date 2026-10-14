# Hosted production acceptance gap — AccessFix AI
 
Audit snapshot: 2026-10-14. Source: connected GitHub main, Railway ForgeWorks staging, Supabase ForgeWorks project, and read-only catalog/aggregate SQL. **Not a production acceptance receipt.** SealAngel and customer data are excluded.

## Distinct evidence layers

| Layer | Observation | What it does NOT establish |
| --- | --- | --- |
| Source | GitHub main at audit: `1b38b10d2bc5c4462f76364af298ad10fe21272e` | Main commit automatically deployed |
| CI | [Observed successful workflow](https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai/actions/runs/38527443663) | Real authenticated two-tenant business acceptance |
| Railway staging | Terminal SUCCESS deployment `fd7e55a1-cd78-448c-a892-4c38827daede`; pinned source `023265e7e34b9328f6bb14c41d862ff4e05f6783` in Singapore | That every post-release main commit is deployed, or production readiness |
| Supabase | ForgeWorks project `fljekuwplgkrpdoajyhn` ACTIVE_HEALTHY; fw_accessfix_ai tables audited with RLS + FORCE RLS | RLS enforcement under real authenticated tenant sessions |
| Product membership | 2 membership rows, **0 ACTIVE, 2 REVOKED** | Any currently authorized test principal |
| Business fixtures | `fw_accessfix_ai.scan_jobs`: 0 rows / 0 represented tenant(s) | Independently signed ownership or two real principal read/write flows |
| Product G3 / production | **BLOCKED / NOT_ACCEPTED** | Production launch authorization |

The membership observation comes from a read-only grouped-status SQL query. Revocation history is not known: **do not reactivate existing accounts as a shortcut**, do not modify auth tables directly, and do not use customer identities. Create independently authorized, fresh staging-only test accounts through official provisioning if permitted.

## Last acceptance dependencies (not a GitHub CI pass)

1. Independently authorize two distinct consenting staging-only Supabase identities with active product membership, server-owned app_metadata grants, and fresh sessions. Verify both access and revocation without placing tokens in source or logs.
2. Create one tenant-owned business fixture for each identity through the product's normal authorized flow. Existing aggregate counts are insufficient. Test own-record HTTP 200 and both cross-tenant HTTP 403/404; add write isolation and session revocation tests separately.
3. Two authorized real scan flows and reviewed semantic patch results; external source/site ownership and revoke-after-login behavior.
4. Capture actual request IDs, observed deployed SHA + runtime manifest, secret-redacted test receipts, scoped performance/SLO, controlled restore/DR, security and privacy review, and independent signoff. Keep staging and production separately provisioned.
5. Review current Supabase security advisor findings: leaked-password protection warning and seven RLS-without-policy informational findings fleet-wide. Distinguish intentional deny-all internal tables from unintended exposure.

## Small, no-credential GitHub tasks

- Keep this evidence separate from synthetic/disposable test results. Bind each future test report to the exact reviewed source and observed runtime SHA.
- Validate release-record fields and reject candidate-vs-observed SHA/fingerprint drift. Avoid duplicating the existing fleet verifier.
- Exercise fail-closed unit tests for G3 fixture prerequisites and invalid/expired-session scenarios; never call a mocked token a hosted PASS.
- Prepare opt-in hosted G3 runbook. No automatic identities, credentials, database writes or production promotion.

## Verification boundary

A public `/healthz`, `/readyz` or anonymous HTTP 401 proves availability/boundary only. Production acceptance requires authenticated real end-to-end product and tenant proof. Current acceptance template stays UNSIGNED and all controls OPEN. Do not mark green because documentation or CI is present.

Audited references: [G3 fixture inventory](https://github.com/ivan-agentic-labs/forgeworks-apishield-agent/blob/main/docs/platform/STAGING_G3_AUTH_FIXTURE_READINESS_2026-10-14.md), [G3 acceptance harness](https://github.com/ivan-agentic-labs/forgeworks-apishield-agent/blob/main/scripts/probe_authenticated_tenant_isolation.py), [Staging release](https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai/blob/main/ops/releases/staging.json).

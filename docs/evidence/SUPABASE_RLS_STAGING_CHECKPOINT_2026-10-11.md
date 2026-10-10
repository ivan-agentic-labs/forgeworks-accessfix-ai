# Supabase RLS and Railway staging checkpoint, 2026-10-11

## Source and evidence scope

- Product repository: `ivan-agentic-labs/forgeworks-accessfix-ai`.
- Verified application/schema source commit: `a63bda62e1b57a9caf884552549fa9f69a4ad06c`.
- Railway staging **application** remains pinned to earlier verified commit `d4b6319255d1540d2e8172e24aabc07de31cdb6b`. Database policy migrations were applied separately. These are different version dimensions and should not be confused.
- Source of truth for applied SQL: `infra/environments/staging/` (004_sites_rls_initplan.sql, 005_sites_rls_current_setting_initplan.sql, 006_remaining_tenant_rls_initplans.sql).
- Supabase project `fljekuwplgkrpdoajyhn`, schema specific to this product. Railway project `1b35f35d-ad5b-4b93-ad20-ed68251b4589`, staging environment `0395e7ac-10f8-4004-8bb7-ddee901343c7`.
- Entire five-product catalog at checkpoint: **62 / 62** application tables have RLS and FORCE RLS enabled.
- Supabase advisor across five products: `auth_rls_initplan` **58 -> 0**; `multiple_permissive_policies` **14 -> 2**; `unindexed_foreign_keys` **24 -> 19**. These are advisor counts, **not** proof of latency, customer security or operational readiness.

## Green GitHub Actions for source commit

- [G1 Contract Verification](https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai/actions/runs/38089371239): `success`
- [AccessFix PostgreSQL Runtime Proof](https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai/actions/runs/38089371236): `success`
- [AccessFix MVP Application CI](https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai/actions/runs/38089371190): `success`
- [AccessFix Disposable Chromium Patch Proof](https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai/actions/runs/38089371223): `success`

## Railway and database verification

- All five staging services returned Railway `SUCCESS`, one running replica each, zero crashed, zero pending rollout operations at checkpoint.
- RLS policies retain the original tenant equality in `USING` and `WITH CHECK`; direct `(SELECT current_setting(...))` initPlans remove the advisor warnings.
- No new anonymous or authenticated role grants were created by these policy migrations.
- Disposable PostgreSQL negative tenant tests passed in CI. A **live** role-switched RLS transaction using the available Supabase connector returned permission denied to `SET ROLE`; **do not mark that test passed**.
- External direct `/readyz` test failed due DNS resolution from this execution environment; Railway health/startup evidence is not equivalent to a browser E2E pass.

## Open release blockers

1. Supabase had two Auth identities with product grant metadata, but **zero ACTIVE product memberships** in all five product schemas at last verification. This requires independently validated user/tenant/role provisioning, then real authenticated positive and negative product-flow tests.
2. Leaked-password protection remains disabled per Supabase security advisor. Configure through the supported Auth administrative settings, then verify.
3. The two remaining multiple-permissive-policy warnings involve APIShield's webhook-specific policy behavior. **Do not remove** these authorization policies simply to zero a lint number.
4. Nineteen missing FK-covering indexes, six unused-index notices, and seven RLS-enabled no-policy INFO notices require workload-based review and intentional deny-by-default validation. Do not blindly add policies or remove indexes.
5. Production environment, customer consent/retention, isolated external integration tests, recovery drill, SLO/load evidence, cost monitoring, security and domain reviewer acceptance for G3-G6 are all **OPEN**.

## Acceptance

This checkpoint is evidence of **staging deployment + synthetic CI + current catalog lint state**, not authorization to use real customer data or launch production. Release process: `ops/runbooks/STAGING_RELEASE_AND_ROLLBACK.md`.

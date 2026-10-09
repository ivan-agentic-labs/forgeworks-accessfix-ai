# G1 evidence index

Evidence snapshot: [`docs/evidence/G1_RUNTIME_EVIDENCE.md`](../evidence/G1_RUNTIME_EVIDENCE.md), tested source snapshot `9051010fa29f0d10ac7b8bf342758474cfd1e1d5` captured from `main` before the documentation-only evidence commit.

## Current partial evidence

- [x] **VERIFIED** — Independent OpenAPI semantic validation, local exit 0 and [G1 Contract Verification run](https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai/actions/runs/37877953709) at the current SHA
- [x] **VERIFIED** — Event JSON Schema Draft 2020-12/static contract checks, local exit 0 and the same contract run
- [x] **VERIFIED** — Empty disposable PostgreSQL migration, [DDL job](https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai/actions/runs/37877989982/job/113650870085) at the current SHA
- [x] **VERIFIED** — Non-owner two-tenant PostgreSQL RLS negative test, [RLS job](https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai/actions/runs/37877989982/job/113650869902) at the current SHA
- [x] **PASS_STATIC_LIMITED** — Synthetic auth/tenant negative tests, E2E API fixture, static UI assertions, worker reliability, and artifact/integrity guards in the local 17-test suite
- [x] **VERIFIED** — Current-main application CI, including unit/integration/web tests and verification checks: [run 37877953689](https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai/actions/runs/37877953689)

## Unavailable or residual evidence

- [ ] **NOT_RUN** — Generated TypeScript client compilation/interoperability
- [ ] **NOT_RUN** — Real IdP/OIDC session, CSRF, provisioning, revocation, and deployed authorization
- [ ] **BLOCKED** — Independent browser sandbox, DOM-to-source mapping, axe/manual accessibility, and egress/SSRF proof
- [ ] **NOT_RUN** — External storage/capability and retained artifact-integrity evidence
- [ ] **BLOCKED** — Owner/independent reviewer signoffs, legal/domain/privacy/DPA, operations, and cost/budget approvals
- [ ] **NOT_RUN** — Production backup/restore, disaster recovery, planned-load, crash/partition, and regional-failure runs

The current CI and disposable PostgreSQL results are scoped evidence, not a full G1 pass. G1-D remains conditional/not signed and G1-E remains blocked; no reviewer approval is inferred. The PostgreSQL workflow is a localhost-only disposable proof and is not production migration or RLS certification.

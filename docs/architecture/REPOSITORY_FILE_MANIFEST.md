# AccessFix AI — Canonical repository file ownership (P0)

**Root:** `forgeworks-accessfix-ai/` (design target; repository not created). This file describes **planned files**, not existing application code. `migrations/versions/` is only migration source; only `contracts/openapi.yaml` is machine-API definition; the other contract is the domain-event schema.

| Planned canonical path | Responsibility | Status |
|---|---|---|
| `.github/workflows/ci.yml` | Lint, contracts, unit, negative fixtures and SCA | PLANNED, no application code |
| `.github/workflows/release.yml` | Artifact provenance, guarded staging/prod release | PLANNED, no application code |
| `.github/CODEOWNERS` | Review ownership | PLANNED, no application code |
| `apps/web/app/(workspace)/page.tsx` | Workspace route and accessible UI | PLANNED, no application code |
| `apps/web/app/api/auth/callback/route.ts` | OIDC BFF callback | PLANNED, no application code |
| `apps/web/lib/api-client.ts` | BFF-to-service API delegated user-token client, no exposed tokens | PLANNED, no application code |
| `apps/api/pyproject.toml` | Python packaging and locked dependencies | PLANNED, no application code |
| `apps/api/src/accessfix_ai/presentation/routes_v1.py` | HTTP routing, no business rule | PLANNED, no application code |
| `apps/api/src/accessfix_ai/presentation/auth_context.py` | Issuer/audience/scope+membership checks | PLANNED, no application code |
| `apps/api/src/accessfix_ai/application/uow.py` | Unit of work, transaction+outbox | PLANNED, no application code |
| `apps/api/src/accessfix_ai/domain/entities.py` | Pure aggregates, states, business invariants | PLANNED, no application code |
| `apps/api/src/accessfix_ai/infrastructure/persistence/models.py` | ORM implementation, tenant composite keys | PLANNED, no application code |
| `apps/api/src/accessfix_ai/infrastructure/persistence/repositories.py` | Scoped repository adapters | PLANNED, no application code |
| `apps/api/src/accessfix_ai/infrastructure/llm/provider_adapter.py` | Model provider typed adapter and budget cap | PLANNED, no application code |
| `apps/worker/src/accessfix_ai/handlers/outbox_dispatch.py` | Durable inbox/outbox/effect lifecycle | PLANNED, no application code |
| `contracts/openapi.yaml` | Canonical machine API candidate | PLANNED, no application code |
| `contracts/events.schema.json` | Canonical typed domain event schema candidate | PLANNED, no application code |
| `migrations/versions/` | One canonical DB schema migration directory | PLANNED, no application code |
| `infra/modules/network/` | Private network and security group design | PLANNED, no application code |
| `infra/environments/staging/` | Environment staging IaC | PLANNED, no application code |
| `infra/environments/production/` | Environment production IaC | PLANNED, no application code |
| `ops/runbooks/incident.md` | Escalation, containment, recovery | PLANNED, no application code |
| `ops/runbooks/restore.md` | Restore plus service reconciliation | PLANNED, no application code |
| `ops/runbooks/rollback.md` | Application rollback/reverse migration strategy | PLANNED, no application code |
| `docs/adr/` | Change decision record | PLANNED, no application code |
| `security/threat-model.md` | STRIDE and abuse cases | PLANNED, no application code |
| `tests/unit/` | Pure domain rules | PLANNED, no application code |
| `tests/integration/` | DB/service adapters | PLANNED, no application code |
| `tests/contract/` | OAS, events, authorization | PLANNED, no application code |
| `tests/security/` | Tenant, credential, SSRF, authorization | PLANNED, no application code |
| `tests/eval/` | LLM and agent gold corpus regression | PLANNED, no application code |
| `tests/e2e/` | User workflow and approvals | PLANNED, no application code |
| `tests/resilience/` | Failure injection, restore | PLANNED, no application code |
| `tests/load/` | Capacity and quota | PLANNED, no application code |
| `fixtures/golden/` | Versioned labelled test cases | PLANNED, no application code |
| `README.md` | Scope, setup, architecture, evidence links | PLANNED, no application code |
| `SECURITY.md` | Vulnerability reporting | PLANNED, no application code |
| `CONTRIBUTING.md` | Contribution and secret-handling policy | PLANNED, no application code |
| `LICENSE` | Only after license choice approved | PLANNED, no application code |
| `apps/api/src/accessfix_ai/domain/target_policy.py` | Pure target policy rules | PLANNED, no application code |
| `apps/api/src/accessfix_ai/domain/findings.py` | Pure findings rules | PLANNED, no application code |
| `apps/api/src/accessfix_ai/domain/coverage_policy.py` | Pure coverage policy rules | PLANNED, no application code |
| `apps/api/src/accessfix_ai/domain/manual_review_policy.py` | Pure manual review policy rules | PLANNED, no application code |
| `apps/api/src/accessfix_ai/application/commands/request_verification.py` | Use case for request verification | PLANNED, no application code |
| `apps/api/src/accessfix_ai/application/commands/verify_site.py` | Use case for verify site | PLANNED, no application code |
| `apps/api/src/accessfix_ai/application/commands/start_scan.py` | Use case for start scan | PLANNED, no application code |
| `apps/api/src/accessfix_ai/application/commands/approve_fix.py` | Use case for approve fix | PLANNED, no application code |
| `apps/api/src/accessfix_ai/ports/browser_scan_port.py` | Interface/port to external browser_scan_port.py | PLANNED, no application code |
| `apps/api/src/accessfix_ai/ports/site_ownership_port.py` | Interface/port to external site_ownership_port.py | PLANNED, no application code |
| `apps/api/src/accessfix_ai/ports/source_map_port.py` | Interface/port to external source_map_port.py | PLANNED, no application code |
| `apps/api/src/accessfix_ai/ports/github_pr_port.py` | Interface/port to external github_pr_port.py | PLANNED, no application code |
| `apps/api/src/accessfix_ai/infrastructure/browser/isolated_playwright.py` | Outbound adapter browser/isolated_playwright.py | PLANNED, no application code |
| `apps/api/src/accessfix_ai/infrastructure/browser/axe_adapter.py` | Outbound adapter browser/axe_adapter.py | PLANNED, no application code |
| `apps/api/src/accessfix_ai/infrastructure/network/egress_guard.py` | Outbound adapter network/egress_guard.py | PLANNED, no application code |
| `apps/api/src/accessfix_ai/infrastructure/source_map/dom_to_source.py` | Outbound adapter source_map/dom_to_source.py | PLANNED, no application code |
| `apps/api/src/accessfix_ai/infrastructure/github/draft_pr_writer.py` | Outbound adapter github/draft_pr_writer.py | PLANNED, no application code |
| `apps/worker/src/accessfix_ai/handlers/run_website_scan.py` | Async durable worker handler run_website_scan.py | PLANNED, no application code |
| `apps/worker/src/accessfix_ai/handlers/create_fix_candidate.py` | Async durable worker handler create_fix_candidate.py | PLANNED, no application code |
| `apps/worker/src/accessfix_ai/handlers/retest_candidate.py` | Async durable worker handler retest_candidate.py | PLANNED, no application code |

| `.github/workflows/contract-check.yml` | OpenAPI/event schema lint and breaking-change check | PLANNED, no application code |
| `.github/workflows/security-scan.yml` | SAST, dependency, secret and artifact checks | PLANNED, no application code |
| `.github/dependabot.yml` | Automated dependency-update policy candidate | PLANNED, no application code |
| `apps/web/app/api/auth/logout/route.ts` | Server-side logout/revocation session endpoint | PLANNED, no application code |
| `apps/web/app/api/auth/session/route.ts` | Same-origin session/read endpoint | PLANNED, no application code |
| `apps/web/lib/csrf.ts` | Origin-bound CSRF token utilities | PLANNED, no application code |
| `apps/api/src/accessfix_ai/presentation/problem_details.py` | RFC 9457 consistent error serialization | PLANNED, no application code |
| `apps/api/src/accessfix_ai/application/idempotency.py` | Tenant-actor-operation dedupe policy | PLANNED, no application code |
| `apps/api/src/accessfix_ai/application/commands/commit_artifact.py` | Artifact scan/commit use case | PLANNED, no application code |
| `apps/api/src/accessfix_ai/infrastructure/storage/object_store.py` | Private object storage scoped adapter | PLANNED, no application code |
| `apps/api/src/accessfix_ai/infrastructure/security/tenant_context.py` | Trusted tenant context policy adapter | PLANNED, no application code |
| `apps/api/src/accessfix_ai/infrastructure/persistence/outbox.py` | Transactional outbox persistence adapter | PLANNED, no application code |
| `apps/worker/src/accessfix_ai/handlers/reconcile_effects.py` | Unknown remote effect reconciliation | PLANNED, no application code |
| `contracts/examples/` | Contract request/response/event fixture samples | PLANNED, no application code |
| `infra/environments/development/` | Local/staging-compatible environment design | PLANNED, no application code |
| `ops/runbooks/tenant_breach.md` | Cross-tenant incident response runbook | PLANNED, no application code |
| `tests/tenant_isolation/` | Two-tenant database and object storage negative tests | PLANNED, no application code |
| `tests/idempotency/` | Duplicate and conflicting request replay tests | PLANNED, no application code |
| `tests/effect_recovery/` | Remote write timeout and effect-reconciliation tests | PLANNED, no application code |
| `docs/risks/` | Threat and residual risk decisions | PLANNED, no application code |
| `docs/evidence/` | Signed proof manifest and gate supporting evidence | PLANNED, no application code |
| `ops/restore-drills/` | Backup/restore evidence and reconciliation exercises | PLANNED, no application code |

## Dependency rules (enforced at G2)
1. Domain imports Python standard library and pure domain types only. Domain must not import FastAPI, DB, browser, cloud SDK, or LLM provider.
2. Application knows pure domain and abstract ports; infrastructure implements ports, with dependency inversion configured at composition root.
3. Presentation only validates transport/auth context and invokes application use cases. Client-supplied `tenant_id` is **never** authoritative.
4. Worker obtains scoped command context, commits effects through ledger, and cannot issue external writes unless approval revision/permission valid.
5. Web uses same-origin BFF session, not directly stored long-lived access tokens; integration credentials live encrypted server side.
6. Paths contain no production keys, generated client output committed only when its contract diff and licenses are reviewed.

## Software delivery skeleton
- `pyproject.toml` and `package.json` owner manifests plus lock files; environment/commit SHA must be captured in evidence.
- `.env.example` contains fake variables only, secret manager is authoritative for live environments.
- Branch checks: import boundaries, formatting/lint, unit, DB migration, contract test, static type check, security tests, isolated eval, SBOM/license scan, signed artifacts.
- Every repository gets its own deployment state and a separate encrypted database/tenant namespace; sharing a library is permitted only as a versioned package without runtime cross-product coupling.

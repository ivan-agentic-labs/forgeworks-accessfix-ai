# AccessFix AI — G1 runtime evidence (source snapshot from `main`)

## Snapshot and interpretation

- **Repository:** `ivan-agentic-labs/forgeworks-accessfix-ai`
- **Tested source snapshot:** `9051010fa29f0d10ac7b8bf342758474cfd1e1d5`
- **Branch:** `main` at audit start; the later commit containing only these evidence documents is `65e927a02147054a223290ada5dd95bd456b45da`
- **Evidence date:** 2026-10-09
- **Scope:** synthetic MVP, static contract checks, and disposable PostgreSQL only. This record does **not** approve production use, real customer data, remote browser execution, GitHub writes, or G1-D/G1-E closure.

`VERIFIED` means the named criterion has a successful, reproducible result at the exact revision, including the linked GitHub Actions run where one exists. `PASS_STATIC_LIMITED` means local tests or static/synthetic fixtures passed, but the result does not establish an external integration, production, or security certification. Neither label is a blanket G1 gate approval.

## Exact local commands and outcomes

Executed from the repository root against the tested source snapshot above:

| Exact command | Local outcome |
|---|---|
| `python -W error -m pytest` | **exit 0** — 17 passed in 1.83s (E2E fixture, integration, unit, web-static, and worker tests) |
| `python scripts/verify_bootstrap.py` | **exit 0** — 101 files scanned; `errors: []` |
| `python scripts/verify_contracts.py` | **exit 0** — 13 operations; Draft 2020-12 event schema; `errors: []` |
| `python scripts/validate_openapi_independent.py` | **exit 0** — third-party `openapi-spec-validator` accepted `contracts/openapi.yaml` |
| `node --check apps/web/app.js` | **exit 0** |
| `bash -n scripts/probe_disposable_postgres.sh scripts/test_disposable_postgres_rls.sh` | **exit 0** |
| `git diff --check` | **exit 0** |

The local pytest suite uses synthetic JWTs and SQLite fixtures. It is useful product evidence, but it is not real IdP/OIDC, production PostgreSQL, browser isolation, or egress proof.

## GitHub Actions evidence at this revision

All links below report `success` and have head SHA `9051010fa29f0d10ac7b8bf342758474cfd1e1d5`.

| Area | Run | Job | Exact workflow step/evidence |
|---|---|---|---|
| Application tests | [run 37877953689](https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai/actions/runs/37877953689) | [test job](https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai/actions/runs/37877953689/job/113650750226) | `python -m pytest tests/unit tests/integration tests/web`, bootstrap/contracts/OpenAPI checks, Node syntax, and shell syntax in `.github/workflows/app-ci.yml` |
| Independent contracts | [run 37877953709](https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai/actions/runs/37877953709) | [contract-check job](https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai/actions/runs/37877953709/job/113650750342) | `verify_bootstrap.py`, `verify_contracts.py`, and `validate_openapi_independent.py` in `.github/workflows/g1-contracts.yml` |
| Empty disposable migration | [run 37877989982](https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai/actions/runs/37877989982) | [ddl-probe job](https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai/actions/runs/37877989982/job/113650870085) | `bash scripts/probe_disposable_postgres.sh` against a fresh PostgreSQL 17 service |
| Non-owner two-tenant RLS | [run 37877989982](https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai/actions/runs/37877989982) | [rls-negative job](https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai/actions/runs/37877989982/job/113650869902) | `bash scripts/test_disposable_postgres_rls.sh`; non-owner `fw_accessfix_ai_rw`, tenant A context, tenant B read/update/insert denial, and role safety checks |

The PostgreSQL workflow is intentionally disposable and localhost-only. Its success is not production migration, backup/restore, concurrency, or operational approval evidence.

## Explicit G1 criteria

| Criterion | Status | Evidence observed on current `main` | Limitation / residual risk |
|---|---|---|---|
| Independent OpenAPI semantic validation | **VERIFIED** | Local `python scripts/validate_openapi_independent.py` exit 0; contract CI run/job above succeeded at the exact SHA | No generated-client compilation or interoperability test; not runtime API certification |
| Event schema validation | **VERIFIED** | Local `python scripts/verify_contracts.py` exit 0; event schema checked with JSON Schema Draft 2020-12; contract CI succeeded | Static schema check only; no broker delivery, compatibility, or consumer test |
| Empty disposable PostgreSQL migration | **VERIFIED** | `ddl-probe` CI job succeeded at the exact SHA on an empty PostgreSQL 17 service | Disposable DDL smoke only; no production migration, data migration, or restore proof |
| Non-owner two-tenant PostgreSQL RLS | **VERIFIED** | `rls-negative` CI job succeeded at the exact SHA; script runs as `fw_accessfix_ai_rw` with `NOBYPASSRLS` and checks cross-tenant SELECT/UPDATE/INSERT isolation | The script does not replace broader production concurrency, transaction-reset, or deployment review |
| Auth and tenant negative tests | **PASS_STATIC_LIMITED** | Local pytest exit 0; `test_cross_tenant_and_scope_fail_closed` covers missing scope and another tenant; hardening tests cover fail-closed remote/oversized scans | Synthetic HS256 tokens and SQLite; real IdP/JWKS, CSRF, provisioning, revocation, and deployed authorization remain untested |
| E2E API fixture workflow | **PASS_STATIC_LIMITED** | `tests/e2e/test_fixture_workflow.py` is included in the 17-test local run and exercises ownership, scan, polling, findings, proposal, retest, review, and idempotency paths | Synthetic fixture only; no real browser, remote target, customer data, or external service |
| UI evidence | **PASS_STATIC_LIMITED** | `tests/web/test_static_ui.py` passes; `node --check apps/web/app.js` exits 0; UI tests verify fixture-only/read-only target and fail-closed messaging | Static UI assertions are not a browser sandbox, accessibility review, or egress proof |
| Worker reliability | **PASS_STATIC_LIMITED** | `tests/worker/test_worker_reliability.py` passes four tests covering idempotency, lease reclaim, bounded retry/terminal failure, cancellation, timeout, and stale revision behavior | Synthetic in-process worker; no planned-load, crash/partition, queue, or regional-failure run |
| Artifact/integrity guards | **PASS_STATIC_LIMITED** | Current tests assert evidence SHA-256 shape/source revision, proposal digest-bound review, revision mismatch, idempotency, and duplicate suppression | No signed artifact store, external storage integrity, generated artifact verification, or production key management |
| Generated client compilation/interoperability | **NOT_RUN** | No current generated-client compile evidence | Required before a full contract/runtime gate decision |
| Real IdP/OIDC, CSRF, provisioning, and revocation | **NOT_RUN** | No IdP/JWKS or browser session run is present | Must remain open; local JWT fixtures are not IdP evidence |
| Browser sandbox, DOM-to-source mapping, axe/manual accessibility, and egress/SSRF proof | **BLOCKED** | Remote browser is deliberately fail-closed and no isolated runner evidence is retained | Requires independent sandbox/egress and human accessibility evidence |
| External storage/capability and artifact retention | **NOT_RUN** | No external storage integration run is present | Local SQLite/filesystem fixtures do not establish this criterion |
| Legal, domain, privacy/DPA, operations, reviewer, and cost/budget signoff | **BLOCKED** | No signed reviewer or responsible-owner approval is present | Do not fabricate approval; OD-01–OD-09 remain open |
| Production backup/restore and disaster recovery | **NOT_RUN** | No production restore drill or backup evidence is present | Disposable PostgreSQL success is not DR evidence |
| **G1-D design review gate** | **BLOCKED / CONDITIONAL** | Technical decisions and partial evidence are recorded | Not signed; domain/owner decisions and required external review remain open |
| **G1-E enforcement/runtime gate** | **BLOCKED** | Partial static, synthetic, and disposable runtime evidence is now retained | Do not mark fully PASS: real IdP, browser/egress, external storage, signoff, and production/operations evidence remain unavailable |

## Residual decision

This is a partial evidence update, not a gate approval. The current evidence supports narrowly scoped `VERIFIED` or `PASS_STATIC_LIMITED` criteria above. G1-D remains conditional/not signed and G1-E remains blocked. No production deployment, customer data, real remote scan, GitHub mutation, or legal/domain/operations/cost approval is authorized by this note.

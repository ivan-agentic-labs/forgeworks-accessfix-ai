# AccessFix AI

> **Find accessibility issues, review fixes, and retest changes with explicit scope.**

**Part of ForgeWorks** | Python API + PostgreSQL engineering MVP | **Production readiness: NOT verified**

AccessFix AI is an engineering project aimed at web engineering teams, agencies, and site owners. The repository demonstrates bounded, testable workflows today; its broader product specification is a roadmap, **not a claim that every feature has shipped**.

## What works in the current engineering scope

- A development ownership challenge and fail-closed target policy gate scanning.
- A synthetic fixture scanner records findings and supports review-bound proposals and retesting.
- A local static console demonstrates the fixture workflow; remote browser execution and GitHub writes are deliberately blocked.

These capabilities are described in the repository's source, local development flow, and [scoped evidence register](docs/verification/CURRENT_GATE_EVIDENCE.md). Treat fixture or CI results as evidence for those exact scenarios, not as independently verified customer behavior.

## What remains before production

- Authorized real-site browser auditing, source mapping and safe patch generation in supported codebases.
- Human accessibility validation, hosted/customer acceptance, and production operations.

**Delivery/evidence boundary:** Engineering documents refer to synthetic CI and Railway staging. A staging deployment claim, passing test, signed template, or source revision fingerprint is **not** a substitute for a live authenticated customer journey, independent security review, production operations, or a trusted release acceptance receipt. The current README does **not** assert that those gates passed. Consult the [hosted release verification runbook](ops/runbooks/RUNTIME_RELEASE_VERIFICATION.md).

## Technical overview

| Area | Current engineering approach |
| --- | --- |
| API/runtime | Python service with versioned REST/OpenAPI contracts |
| Persistence | PostgreSQL MVP adapter and tenant isolation checks in disposable verification environments |
| Local development | Explicit development-only authentication, short-lived synthetic tokens, bounded fixture data |
| Quality controls | Automated tests, contract validation, evidence artifacts, review gates |
| Hosted acceptance | Separate release identity and operational checks; not equivalent to production signoff |

See [product scope](docs/product/PRODUCT_SCOPE.md), [architecture documents](docs/architecture/), and [API/event contracts](contracts/openapi.yaml) for details. Never send secrets or real customer data to local fixtures.

## MVP run and test

```bash
python -m pip install --require-hashes -r requirements-runtime.lock
python -m pip install -e 'apps/api[test]' -r scripts/requirements-verification.txt
export APP_ENV=development AUTH_MODE=development
export AUTH_ISSUER=https://issuer.synthetic.invalid AUTH_AUDIENCE=forgeworks-api
export DEV_AUTH_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export ARTIFACT_SIGNING_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
python scripts/development_token.py
ACCESSFIX_SEED_FIXTURE=1 PYTHONPATH=apps/api/src uvicorn accessfix_ai.main:app --reload
```

The printed token lasts 15 minutes and belongs to the local synthetic tenant/user. Use a second terminal with the same explicit development environment to run python -W error -m pytest tests. Never enable fixtures or reuse the development token on hosted infrastructure or customer data.


## Static fixture UI

The dependency-free console in `apps/web/` drives the ownership, scan, findings, fix-proposal,
retest, and human-review flow against `http://fixture.local` only. Remote browser execution is
fail-closed and GitHub writes remain disabled. Run the API and UI in separate terminals:

```bash
ACCESSFIX_SEED_FIXTURE=1 PYTHONPATH=apps/api/src uvicorn accessfix_ai.main:app --port 8000
python -m http.server 8080 --bind 127.0.0.1 --directory apps/web
```

Open `http://127.0.0.1:8080` and provide a local development JWT. The page renders stopped error
states for API failures, including `REMOTE_BROWSER_BLOCKED`. See `apps/web/README.md` and
`docs/evidence/LOCAL_UI_AND_RLS_RUN.md` for the complete run record.

## Documents
- Product scope: `docs/product/PRODUCT_SCOPE.md`
- Architecture and file ownership: `docs/architecture/`
- Source contracts: `contracts/openapi.yaml` and `contracts/events.schema.json`
- Candidate SQL: `docs/verification/sql-candidates/` (NOT migration scripts)
- Signoff / blockers: `docs/verification/DESIGN_GATE_STATUS.md` and `docs/governance/MASTER_G1_DECISION.md`

## Local verification
Install dependencies from `scripts/requirements-verification.txt` then run:

```bash
python scripts/verify_bootstrap.py
python scripts/verify_contracts.py
python scripts/validate_openapi_independent.py
```

The configured CI covers the test suite, OpenAPI/event contracts, generated TypeScript client, PostgreSQL MVP runtime, tenant RLS/concurrency, and disposable logical backup/restore. See the linked evidence register and the latest GitHub Actions run for the scope and outcome of each verification. Passing synthetic checks does not establish production or customer acceptance.

## Non-goals at this stage
No production deployment, customer data, code-execution agent, customer production access, financial mutation, license assertion or fake passing tests.

## Governance
The owner approved proceeding with GitHub bootstrap. Technical G1-E controls are still pending until their tests actually pass and evidence is reviewed. See `docs/governance/MASTER_G1_DECISION.md` for pre-approval baseline language; the owner approval is recorded here as a later decision.


## Engineering continuation

See [current changes and residual gaps](docs/evidence/ENGINEERING_CONTINUATION.md). Configure authentication explicitly; development fixture commands now require `AUTH_MODE=development`, `APP_ENV=development`, a locally generated `DEV_AUTH_SECRET` of at least 32 bytes, and issuer/audience configuration. Never reuse test fixture credentials outside tests.

## Current main engineering status

See [current G1/G2 evidence](docs/verification/CURRENT_GATE_EVIDENCE.md), [exact source receipt](docs/evidence/MAIN_VERIFICATION_2026-10-09.json), and [owner main authorization](docs/governance/ENGINEERING_MAIN_AUTHORIZATION_2026-10-09.md). PostgreSQL adapters exist for all five independent projects. Historical evidence retains its source SHA and narrower scope.

## Hosted release verification

See [runtime identity, private telemetry and production acceptance](ops/runbooks/RUNTIME_RELEASE_VERIFICATION.md). Hosted releases expose a bounded source fingerprint and require a separate server-only metrics credential. Production startup requires separate infrastructure and an actual trusted, signed acceptance receipt. An unsigned template or passing synthetic CI does not establish production acceptance.

## ForgeWorks platform direction

Five independent service repositories are intended to become **one user-facing ForgeWorks application**, with a shared portal and explicit service boundaries. This integration is a **target architecture**, not an already verified unified deployment. See [one-app/five-services decision](docs/platform/ONE_APP_FIVE_SERVICES.md).

- APIShield Agent: [forgeworks-apishield-agent](https://github.com/ivan-agentic-labs/forgeworks-apishield-agent)
- AccessFix AI: [forgeworks-accessfix-ai](https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai)
- SpecForge AI: [forgeworks-specforge-ai](https://github.com/ivan-agentic-labs/forgeworks-specforge-ai)
- AgentTest Lab: [forgeworks-agenttest-lab](https://github.com/ivan-agentic-labs/forgeworks-agenttest-lab)
- DataReconcile AI: [forgeworks-datareconcile-ai](https://github.com/ivan-agentic-labs/forgeworks-datareconcile-ai)

[SealAngel Work](https://github.com/ivan-agentic-labs/sealangel-work) is a **separate application**, not a sixth ForgeWorks module.

## Specification and evidence index

- [Current owner-approved product specification (2026-10-13)](docs/specifications/PRODUCT_SPECIFICATION_2026-10-13.md): future target, not an implementation checklist marked complete.
- [Full source specifications and IR catalogue](docs/specifications/source/README.md): preserved source documents and recorded hashes.
- [Scoped G1/G2 evidence and outstanding acceptance](docs/verification/CURRENT_GATE_EVIDENCE.md): what was checked and the limitations.
- [Hosted runtime/release runbook](ops/runbooks/RUNTIME_RELEASE_VERIFICATION.md): conditions for independently proving an accepted deployment.
- The October 9 bootstrap evidence is historical; do not present it as a fresh hosted acceptance.

## Documentation integrity

This README is a navigational and engineering summary. If it conflicts with verified source behavior or a dated evidence receipt, prefer the scoped evidence and inspect the actual code/test result. Do not interpret a design document, CI fixture, or staging reference as proof of production readiness.

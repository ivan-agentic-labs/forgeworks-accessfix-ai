# AccessFix AI

> **Identify accessibility findings, review proposed fixes, and retest.**

Part of **ForgeWorks**, a collection of five complementary API services for software engineering and operations.

## What the product does

AccessFix AI organizes accessibility review around authorized targets, inspectable findings, human-controlled remediation proposals, and retest results. It gives a web team one traceable flow for discussing and verifying fixes.

**Who uses it:** Web teams, agencies, and site maintainers.

## Capabilities and outputs

| Capability | Input / action | Output |
| --- | --- | --- |
| Target authorization | Development ownership challenge and target policy | A scoped, fail-closed authorization decision |
| Accessibility inspection | Supported local synthetic page fixtures | Recorded findings tied to a scan |
| Fix review | Scan findings and review decisions | Review-bound remediation proposals |
| Retest | A selected fixture and proposed changes | A new result to compare with the earlier findings |

## Example workflow

1. Establish target scope through the ownership challenge.
2. Run the fixture scan and inspect the findings.
3. Review remediation proposals rather than applying changes silently.
4. Retest and inspect the updated results in the local console.

**What a team gets:** explicit inputs, a repeatable processing path, and inspectable outputs for review. The dependency-free console in [apps/web/](apps/web/) supports ownership, scan, findings, proposals, retest, and review flows against the local fixture target.

## Technical design

- **API:** Python service with versioned REST/OpenAPI contracts and structured error handling.
- **Data:** PostgreSQL domain adapter and tenant-scoped data access controls.
- **Auth:** explicit development authentication for local use; never reuse local keys or sample identities on hosted infrastructure.
- **Verification:** automated code tests, contract checks, and scoped evidence documents. Their meaning is limited to the scenarios they exercised.

## Run locally

Install Python and the runtime/test dependencies from the repository root:

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

The generated token is short-lived and is only for local development with synthetic data. To run the test suite, use `python -W error -m pytest tests` with the same explicit development environment.

## API and technical references

- [Product scope](docs/product/PRODUCT_SCOPE.md)
- [Architecture](docs/architecture/)
- [OpenAPI contract](contracts/openapi.yaml) and [event schemas](contracts/events.schema.json)
- [Verification evidence](docs/verification/CURRENT_GATE_EVIDENCE.md)
- [Release verification runbook](ops/runbooks/RUNTIME_RELEASE_VERIFICATION.md)
- [One-app / five-services design](docs/platform/ONE_APP_FIVE_SERVICES.md)

## ForgeWorks service family

- [APIShield Agent](https://github.com/ivan-agentic-labs/forgeworks-apishield-agent) · API contract-change analysis
- [AccessFix AI](https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai) · accessibility review
- [SpecForge AI](https://github.com/ivan-agentic-labs/forgeworks-specforge-ai) · requirements-to-API contracts
- [AgentTest Lab](https://github.com/ivan-agentic-labs/forgeworks-agenttest-lab) · AI agent evaluation
- [DataReconcile AI](https://github.com/ivan-agentic-labs/forgeworks-datareconcile-ai) · reconciliation and exceptions

The services have separate repositories and explicit interfaces. A single customer-facing ForgeWorks portal is an architectural direction, not a claim of independently verified live integration.

## Usage boundary

The scanner and console operate on the local fixture target; remote browser scanning, real website audits and GitHub writes are intentionally blocked. Automated findings do not replace a manual accessibility review. Consult the linked evidence register and runbook before claiming customer-level or production acceptance.

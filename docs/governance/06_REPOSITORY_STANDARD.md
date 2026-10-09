# File/repository standard — target, bukan kode yang sudah ada

```text
forgeworks-<product>/
├── .github/             # CODEOWNERS, CI, security, release, issue templates
├── apps/web/            # Next.js BFF, UI, typed client and session security
├── apps/api/            # Python API: presentation / application / domain / ports / infrastructure
├── apps/worker/         # isolated durable workflows, effect reconcile
├── contracts/           # openapi.yaml, events.schema.json, fixtures; one canonical source
├── migrations/versions/ # single ordered SQL migration source
├── infra/               # IaC staging/prod, networks, secrets, role templates
├── ops/runbooks/        # incident, restore, rollback, quota, tenant-deletion
├── security/            # threat model, permission matrix, disclosure
├── docs/adr/            # option/trade-off/decision/evidence records
├── tests/               # unit, integration, contract, security, eval, e2e, resilience, load
├── fixtures/            # synthetic, versioned labeled test corpus
├── scripts/             # reproducible dev/audit commands (no credentials)
├── README.md
├── SECURITY.md
├── CONTRIBUTING.md
├── .env.example
└── LICENSE             # only after explicit license decision; no auto-added license
```

## Dependency rules
- `domain/` imports no FastAPI, ORM, HTTP, LLM, GitHub, Playwright, or cloud SDK.
- `application/` coordinates domain and abstract `ports/`, contains commands, UoW, policies; no direct platform client code.
- `infrastructure/` implements ports; persistence tenant-scoped, no generic unscoped CRUD helpers.
- `presentation/` validates input/session; cannot bypass use-case or authorize via tenant header.
- `worker/` invokes application commands with dedicated machine identity; no UI/business logic or global secrets.
- `contracts/` generated client/server typing only from versioned source, never duplicate hand-written schemas.
- CI must detect import-boundary violations, secret leaks, unsafe dependencies and breaking changes.

## Repository specific files
See `docs/architecture/REPOSITORY_FILE_MANIFEST.md` and `docs/architecture/DESIGN_REVIEW.md`. Manifest paths remain PLANNED, not source code that exists. Product-specific adapters (GitHub/Playwright/evaluation/deterministic matching) are not merged into generic `domain` modules.

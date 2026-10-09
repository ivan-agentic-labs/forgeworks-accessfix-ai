# AccessFix AI

**Status: synthetic MVP milestone implemented and tested locally. Not deployed, not production-ready, and G1-E remains open.**

Web accessibility analysis, code remediation proposals and measured retesting.

The first executable slice verifies ownership using a development challenge, enforces a fail-closed target policy, runs a synthetic fixture scan through a local worker, stores findings, and supports human-review-bound proposals. Remote browser scanning and GitHub writes remain disabled.

## MVP run and test
```bash
python -m pip install -e 'apps/api[test]'
ACCESSFIX_SEED_FIXTURE=1 PYTHONPATH=apps/api/src uvicorn accessfix_ai.main:app --reload
python -W error -m pytest tests/integration
```
The SQLite store, development issuer, and `fixture.local` are test-only. Automated findings are not WCAG certification. See `docs/evidence/MVP_CHECKPOINT.md`.

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

CI runs on main and verifies the complete test tree, OpenAPI/event contracts, generated TypeScript client, implemented PostgreSQL MVP runtime, tenant RLS/concurrency and disposable logical backup/restore. These are scoped synthetic proofs; full G1-E and production operations remain open.

## Non-goals at this stage
No production deployment, customer data, code-execution agent, public access, financial mutation, license assertion or fake passing tests.

## Governance
The owner approved proceeding with GitHub bootstrap. Technical G1-E controls are still pending until their tests actually pass and evidence is reviewed. See `docs/governance/MASTER_G1_DECISION.md` for pre-approval baseline language; the owner approval is recorded here as a later decision.


## Engineering continuation

See [current changes and residual gaps](docs/evidence/ENGINEERING_CONTINUATION.md). Configure authentication explicitly; development fixture commands now require `AUTH_MODE=development`, `APP_ENV=development`, a locally generated `DEV_AUTH_SECRET` of at least 32 bytes, and issuer/audience configuration. Never reuse test fixture credentials outside tests.

## Current main engineering status

See [current G1/G2 evidence](docs/verification/CURRENT_GATE_EVIDENCE.md), [exact source receipt](docs/evidence/MAIN_VERIFICATION_2026-10-09.json), and [owner main authorization](docs/governance/ENGINEERING_MAIN_AUTHORIZATION_2026-10-09.md). PostgreSQL adapters exist for all five independent projects. Historical evidence retains its source SHA and narrower scope.

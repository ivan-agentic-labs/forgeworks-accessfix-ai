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

CI contains a manual PostgreSQL disposable DDL smoke test. **No live RLS/two-tenant proof or sandbox evidence is claimed.**

## Non-goals at this stage
No production deployment, customer data, code-execution agent, public access, financial mutation, license assertion or fake passing tests.

## Governance
The owner approved proceeding with GitHub bootstrap. Technical G1-E controls are still pending until their tests actually pass and evidence is reviewed. See `docs/governance/MASTER_G1_DECISION.md` for pre-approval baseline language; the owner approval is recorded here as a later decision.

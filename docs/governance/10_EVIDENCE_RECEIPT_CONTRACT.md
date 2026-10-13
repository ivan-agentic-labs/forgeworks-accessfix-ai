# ForgeWorks evidence receipt contract

**Status:** baseline contract v1.0. This is a record-validation format, not a release approval or a replacement for any product's G1–G6 gate.

## Purpose

A receipt records what was checked, against which source, in which environment, and what the check does **not** prove. It makes it harder to confuse a green CI job, staging liveness check, or disposable database test with authenticated customer acceptance or production readiness.

Each repository stores the shared JSON Schema at `contracts/evidence-receipt.schema.json`, the read-only validator at `scripts/verify_evidence_receipts.py`, and dated baseline snapshots under `docs/verification/evidence-receipts/`.

## Required identity and evidence boundaries

- `evaluated_source_commit` is the exact repository commit whose state the baseline assessment describes. A receipt is a historical snapshot; adding the receipt itself does not retroactively change the commit that was tested.
- Each evidence item records `workflow_commit`, the commit containing the test/workflow definition, separately from `subject_commit`, the code actually tested or deployed.
- For CI and disposable tests, the checkout and subject commit must be identified and equal. For a staging smoke test, set `subject_identity` to `UNKNOWN` and `subject_commit` to `null` unless a deployment receipt independently proves the deployed SHA. Never infer deployed identity from the commit that ran the smoke workflow.
- Every result includes both its scope and at least one explicit limitation. A `PASS` means only that the described check passed within that scope.
- G1-D, G1-E, and production acceptance are recorded independently. A passing job does not change gate status. The validator rejects `production_acceptance: ACCEPTED` unless both gates are `PASS` and a reviewer-referenced production acceptance record exists.
- A missing, historical, or stale receipt is not current proof. Preserve old snapshots; create a new dated receipt for new evidence rather than editing history.

## What a receipt cannot assert by itself

The schema and validator do not verify GitHub signatures, reviewer identity, deployment control-plane state, URL reachability, log authenticity, or that a recorded run was honestly described. CI checks format and cross-field invariants only. Human/domain/security/legal/operations approvals remain separate controls. Current baseline files deliberately report `NOT_ACCEPTED` for production and state their open gates and limitations.

## Updating the baseline

1. Record the exact commit that the evidence describes.
2. Link each test to its immutable CI run or review reference and identify the tested/deployed subject SHA. Use `null` plus `UNKNOWN` when deployment identity is not proven.
3. State bounded scope and limitations, including what the run does not prove.
4. Keep gate decisions separate from engineering checks and require reviewer references for production acceptance.
5. Add a new dated receipt and preserve prior records. Run `python scripts/verify_evidence_receipts.py` and the repository's complete test suite.

The baseline snapshots are informational records of existing, scoped checks; they do not authorize a deployment, enable external effects, or declare any product production-ready.

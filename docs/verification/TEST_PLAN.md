# AccessFix AI — Verifiable test and evaluation plan

| Test ID | Scenario | Fixture / setup | Expected acceptance result | Execution |
|---|---|---|---|---|
| AX-T01 | Target redirects to loopback | Injected redirect-chain fixture | deny at network egress | PARTIAL_LOCAL — `tests/integration/test_local_test_plan.py::test_ax_t01_redirect_to_loopback_is_rejected_before_egress`; policy rejects loopback before resolver invocation, but no HTTP client/egress boundary was exercised. |
| AX-T02 | DNS rebinding to metadata endpoint | Injected public→metadata DNS answers | no packets leave to prohibited IP | PARTIAL_LOCAL — `tests/integration/test_local_test_plan.py::test_ax_t02_dns_rebinding_to_metadata_is_rejected_fail_closed`; injected resolver detects a metadata answer, but no network packet/egress monitor was exercised. |
| AX-T03 | Expired ownership token | Disposable SQLite challenge with expired timestamp | scan cannot start | PASS_LOCAL — `tests/integration/test_local_test_plan.py::test_ax_t03_expired_ownership_challenge_cannot_start_scan`; local challenge/scan API only, no external verifier |
| AX-T04 | Axe reports no findings | Empty local static-rule fixture and evidence manifest | never display WCAG certified | PARTIAL_LOCAL — `tests/integration/test_local_test_plan.py::test_ax_t04_empty_local_rule_result_never_claims_wcag_certification`; validates empty supported-rule output and manifest flag, not upstream axe/browser coverage |
| AX-T05 | Modified patch after approval | Disposable SQLite approved proposal with mutated stored patch | PR denied | PARTIAL_LOCAL — `tests/integration/test_local_test_plan.py::test_ax_t05_approved_patch_mutation_fails_closed_at_evidence_gate`; evidence export rejects mutated patch bytes, but no live PR-provider denial was exercised. |
| AX-T06 | Keyboard path fails despite axe pass | Disposable SQLite static retest pass plus failed manual status | release remains blocked | PARTIAL_LOCAL — `tests/integration/test_local_test_plan.py::test_ax_t06_failed_manual_keyboard_review_rejects_after_static_retest`; synthetic manual failure rejects the proposal, but no real keyboard/axe/browser release evaluation was exercised. |

## Coverage and execution gates
- Unit: every pure domain invariant, deterministic cross-validation, state guard, authorization policy and financial arithmetic where relevant.
- Contract: OpenAPI semantic validation, JSON Schema, request/response/error examples, client generation, event backwards compatibility.
- Integration: PostgreSQL tenant/RLS/FKs/transactions, storage capability, OIDC+BFF flow, inbox/outbox/queue, provider-scoped permissions.
- E2E: five canonical success/failure paths including human approval and result retrieval; use separate tenants and consented/synthetic data.
- Agent evaluation: frozen labeled corpus with human adjudication, baseline comparison, model/version pinning, typed outputs, prompt injection and tool abuse fixtures.
- Security: SAST/SCA/secret/DAST and cross-tenant negative tests, SSRF sandbox escape, revocation, external effect uncertainty.
- Reliability: 2x planned load (tentative), forced worker crash, network partitions, point-in-time DB restore, region failure simulation.

## Metrics to establish on actual runs
- supported rule coverage by page type
- confirmed finding precision on labeled pages
- patch retest pass rate
- manual-review completion rate
- false accessibility certification claims = 0

**No arbitrary success numbers:** Define threshold from buyer risk tolerance and pilot corpus before G1. Store observed accuracy and sample size, confidence/coverage when meaningful, source hash, run logs, costs, p95, failure distribution. A test case being designed is not a passed test.

## Evidence format
`{test_id, requirement_id, revision_sha, input_fixture_sha, dataset_version, environment, exact_command, expected, observed, pass_fail, reviewer, trace_id, issues}`.

# AccessFix AI — Verifiable test and evaluation plan

| Test ID | Scenario | Fixture / setup | Expected acceptance result | Execution |
|---|---|---|---|---|
| AX-T01 | Target redirects to loopback | HTTP redirect fixture | deny at network egress | NOT RUN |
| AX-T02 | DNS rebinding to metadata endpoint | rebind fixture | no packets leave to prohibited IP | NOT RUN |
| AX-T03 | Expired ownership token | expired challenge | scan cannot start | NOT RUN |
| AX-T04 | Axe reports no findings | accessible-looking fixture | never display WCAG certified | NOT RUN |
| AX-T05 | Modified patch after approval | patch digest mismatch | PR denied | NOT RUN |
| AX-T06 | Keyboard path fails despite axe pass | manual evaluation script | release remains blocked | NOT RUN |

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

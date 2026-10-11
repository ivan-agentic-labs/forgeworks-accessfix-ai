# Scan crash retry budget — 2026-10-11

Baseline: 820d7b2450cc4454f9351ade0d5eaeb4c8c72516.

Worker error reporting already stopped retries at max_attempts, and stale lease completion was already guarded. Claiming expired RUNNING scans did not check the attempt budget, so repeated process crashes without an error report could restart forever. A regression using the original no-argument claim API proves a fourth claim after three expired attempts.

Claim now validates a positive integer attempt budget, terminalizes eligible exhausted work, and selects only scans below budget. A final live lease remains RUNNING; cancellation wins over exhaustion. SQLite claim and cleanup run in one write transaction across independent adapters. PostgreSQL cleanup is tenant-scoped under the existing runtime-role transaction/advisory lock. Both worker entry points pass the same configured budget to claiming and error handling. No schema migration is required.

Initial new suite: ten failures. One reproduces the original default-budget bug; the others include failures because the new keyword configuration did not exist. Final suite: 13 passing cases for default/configured budgets 1–3, live last attempts, simulated unreported crashes with configured worker budget, invalid configuration without job mutation, cancellation, and continued progress past exhausted work. Expiry is changed explicitly in disposable SQLite fixtures; this is not an OS process-kill proof. The dedicated PostgreSQL runtime test adds actual limited-role claims, expiry, exhaustion without findings/source creation, terminal completion rejection and continued healthy work.

Local validation: 245 Python tests pass, eight skipped (seven rendered Chromium tests and one native PostgreSQL runtime test unavailable locally); three Node tests pass. Bootstrap scan, contract checks, independent OpenAPI validation and whitespace checks pass. Required hosted application, rendered Chromium, native PostgreSQL/restore and contract workflows must pass before merge.

Limits: synthetic fixture scanning, no third-party target/browser scan acceptance. Workers must use a consistent retry policy; immutable per-job policy and heartbeat renewal are not introduced. No external side effects, live database migration or deployment is performed by this change. Production readiness remains unproven.

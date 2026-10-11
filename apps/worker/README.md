# Worker

The MVP worker is a deterministic, fixture-only scan worker shared by the API and
`accessfix_worker` package. It performs no browser, third-party domain, or GitHub
I/O. A scan is claimed with a short lease, retried after an expired lease or
worker error, and moved to a terminal `FAILED`, `CANCELLED`, or `TIMED_OUT`
state within bounded attempts. Fixture findings use a uniqueness constraint and
proposal creation is keyed by finding plus base revision, so restarts cannot
create duplicate findings or proposals.

Both worker entry points pass `WorkerConfig.max_attempts` to claim and failure
handling. SQLite and PostgreSQL stop reclaiming expired work once that budget
is exhausted, even when a worker died without reporting an error. Exhaustion
clears the lease and timeout and records `MAX_ATTEMPTS_EXCEEDED`; requested
cancellation remains `CANCELLED`. A live final attempt is allowed to finish.
All workers serving one queue must use the same retry policy. This does not
persist an immutable per-job retry policy or provide heartbeat renewal.

Reliability coverage is in `tests/worker/test_worker_reliability.py`; the API
workflow and visible remote fail-closed behavior are in
`tests/e2e/test_fixture_workflow.py`.

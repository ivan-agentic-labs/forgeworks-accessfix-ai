# Worker

The MVP worker is a deterministic, fixture-only scan worker shared by the API and
`accessfix_worker` package. It performs no browser, third-party domain, or GitHub
I/O. A scan is claimed with a short lease, retried after an expired lease or
worker error, and moved to a terminal `FAILED`, `CANCELLED`, or `TIMED_OUT`
state within bounded attempts. Fixture findings use a uniqueness constraint and
proposal creation is keyed by finding plus base revision, so restarts cannot
create duplicate findings or proposals.

Reliability coverage is in `tests/worker/test_worker_reliability.py`; the API
workflow and visible remote fail-closed behavior are in
`tests/e2e/test_fixture_workflow.py`.

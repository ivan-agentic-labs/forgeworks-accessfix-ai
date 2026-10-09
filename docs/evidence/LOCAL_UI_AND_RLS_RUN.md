# Local UI and PostgreSQL RLS run record

## Scope

This run is limited to the synthetic `http://fixture.local` origin and a disposable PostgreSQL
instance bound to `127.0.0.1`. No third-party domain is scanned, no remote browser is enabled, and
no GitHub write is attempted.

## Static UI

The dependency-free console is in `apps/web/` and calls the ownership challenge/verify, scan,
findings, fix-proposal, retest, and manual-review endpoints. It uses the seeded API and keeps the
bearer token in memory only:

```bash
python -m pip install -e 'apps/api[test]'
ACCESSFIX_SEED_FIXTURE=1 PYTHONPATH=apps/api/src uvicorn accessfix_ai.main:app --port 8000
python -m http.server 8080 --bind 127.0.0.1 --directory apps/web
```

Open `http://127.0.0.1:8080`, provide a local development JWT, and choose **Run fixture workflow**.
The UI displays each stage and the final JSON evidence. The readonly origin is always
`http://fixture.local`.

### Fail-closed and error evidence

- The API rejects a verified non-fixture origin with `503 REMOTE_BROWSER_BLOCKED`.
- The UI renders that response as **Remote scan blocked (fail-closed)** and stops later requests.
- The UI rejects non-local API hosts before issuing a request; only `localhost` and `127.0.0.1` are allowed.
- Missing/invalid credentials, unreachable API, invalid commit SHA, and other non-2xx responses are
  shown in the same visible error panel; the workflow never continues after a failed stage.
- The UI does not call `/pull-requests`; GitHub write integration remains disabled.

## Disposable PostgreSQL RLS negative test

The runtime test uses `migrations/versions/001_accessfix_mvp.sql`, seeds two tenants as the database
owner, then executes reads, an update, and an insert as the non-owner `fw_accessfix_ai_rw` role.
The role has `NOLOGIN`, `NOSUPERUSER`, `NOBYPASSRLS`, and is granted access only to the tenant-scoped
fixture tables. The test asserts tenant B is invisible and cannot be changed or inserted into while
the transaction carries tenant A context.

Example disposable invocation:

```bash
G1_DISPOSABLE_DB=yes \
PGHOST=127.0.0.1 PGPORT=5432 PGUSER=postgres \
PGPASSWORD='<disposable-only-password>' PGDATABASE=forgeworks_g1 \
bash scripts/test_disposable_postgres_rls.sh
```

The script rejects non-local hosts, unexpected database names, non-`postgres` bootstrap users, and
missing `G1_DISPOSABLE_DB=yes`. It must never be pointed at a production or shared database.

Observed run: a temporary local PostgreSQL 16 cluster on `127.0.0.1:55432` printed
`RLS tenant isolation negative test: PASS` and was dropped after the run. The existing PostgreSQL
service on port 5432 was not modified.

## Verification commands

```bash
python -m pytest
node --check apps/web/app.js
python scripts/verify_bootstrap.py
python scripts/verify_contracts.py
python scripts/validate_openapi_independent.py
bash -n scripts/probe_disposable_postgres.sh scripts/test_disposable_postgres_rls.sh
git diff --check
```

A PostgreSQL result is only recorded as a pass when the disposable runtime is available and the
script prints `RLS tenant isolation negative test: PASS`; otherwise availability is a blocker, not a
passing claim.

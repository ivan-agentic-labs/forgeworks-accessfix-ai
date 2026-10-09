# AccessFix AI MVP

Synthetic-only MVP: ownership challenge, verified-site scan command, fail-closed target policy, deterministic fixture finding, proposal/review state, and a local polling worker.

Run `python -m pip install -e 'apps/api[test]'`, then `ACCESSFIX_SEED_FIXTURE=1 PYTHONPATH=apps/api/src uvicorn accessfix_ai.main:app`.

The local SQLite store, development HS256 issuer, and `fixture.local` are test-only. Remote browser scans fail closed until browser isolation and egress controls are independently verified. Automated findings are not WCAG certification. GitHub write is disabled.

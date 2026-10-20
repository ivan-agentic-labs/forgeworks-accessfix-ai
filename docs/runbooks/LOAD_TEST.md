# Load smoke (staging)

`scripts/load_smoke.py` is a stdlib-only, read-only, rate-limited GET smoke. It complements
`docs/governance/04_OPERATIONS.md` and is **not** a capacity certification (G4 still requires a
planned load test with an owner-approved budget and window).

Endpoints: `/healthz`, `/readyz`, `/versionz`, `/v1/auth/config` (public) and
`/v1/scans/00000000-0000-0000-0000-000000000001/findings` (authenticated read; expects 401/403/404 without a token, so the auth reject path is measured).

```bash
# Safe default: 1 rps for 30 s against staging
python3 scripts/load_smoke.py --base https://accessfix-ai-staging.up.railway.app
# Hard caps: --rps <= 5, --duration <= 300
python3 scripts/load_smoke.py --base https://accessfix-ai-staging.up.railway.app --rps 2 --duration 60
# Optional authenticated read (token from env, never printed; staging test user only)
FW_LOAD_BEARER=... python3 scripts/load_smoke.py --base https://accessfix-ai-staging.up.railway.app
```

Output: JSON with p50/p95/max latency and status codes per path; exit code 1 if any response
had an unexpected status. Never run against production without an approved change window.

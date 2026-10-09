# MVP checkpoint — AccessFix AI

Status: `TESTED` for the synthetic fixture flow; remote browser scan and GitHub write are `BLOCKED` until isolation/egress and permission evidence exist.

Implemented: JWT issuer/audience/expiry/scope/membership checks, one-time ownership challenge, fail-closed target policy, verified-site scan command, persisted scan and polling worker, deterministic fixture finding, source-mapping guard, patch proposal, stale/version/digest-bound human review, and disabled GitHub PR adapter.

Command: `python -W error -m pytest tests/integration -q`  
Acceptance: 3 passed, exit 0, local Sandbox.

Not run: real Playwright/axe isolated browser, PostgreSQL/RLS, real OIDC/JWKS, DNS rebinding/egress network proof, live GitHub PR.

No automated result is called WCAG certification. Local fixture evidence does not prove safety for untrusted remote content.

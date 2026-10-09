# G2 bootstrap status — 9 October 2026

Owner: `ivan-agentic-labs`. Five independent private repositories are authorized. The tested source snapshot captured from `main` is recorded in [`docs/evidence/G1_RUNTIME_EVIDENCE.md`](../evidence/G1_RUNTIME_EVIDENCE.md) at revision `9051010fa29f0d10ac7b8bf342758474cfd1e1d5`; the evidence-document commit is documentation-only.

The tested main source snapshot has successful GitHub Actions evidence for application CI, independent/static contract checks, an empty disposable PostgreSQL migration, and the non-owner two-tenant RLS negative test. Local synthetic API/UI, auth/tenant negative, worker-reliability, and artifact/integrity guard tests also pass. These are partial, scoped results: G1-D remains conditional/not signed and G1-E remains OPEN/BLOCKED until the required external and operational evidence is accepted.

Generated-client compilation, real IdP/OIDC session and CSRF tests, independent browser sandbox/egress testing, external storage, legal/domain/privacy/operations/cost signoff, production backup/restore, and other unavailable evidence remain NOT_RUN or BLOCKED. No production deployment or customer data is authorized.

The PostgreSQL workflow uses an intentionally public, disposable localhost-only test password. This is not a production credential. Never reuse it outside the isolated test service.

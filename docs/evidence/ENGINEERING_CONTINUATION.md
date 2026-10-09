# Engineering continuation — 2026-10-09

## Scope and source

Five independent private repositories remain the project boundary. The original G2 bootstrap ZIP was read and compared with the architecture/handoff documents. Owner authorization permits implementation and GitHub pushes; this record does not assert independent security or domain signoff.

## Implemented changes

- Explicit development authentication; no implicit shared signing-secret fallback.
- Required JWT expiry, issuer, audience, subject and tenant claims; fixed algorithm selection.
- Configurable OIDC RS256/JWKS verification with bounded fetch timeout and key-cache lifetime. Offline tests cover key selection/rotation and algorithm-confusion rejection; no real identity-provider session has been tested.
- All application workflows execute the complete `tests` tree with warnings treated as errors.
- A locked generated TypeScript client and compilation check under `packages/sdk`.

Remote scanning now rejects before DNS lookup when the remote runner is disabled. No remote request or queue entry is created by that disabled path.

## Verification and limitations

Structure/sensitive-pattern scans, static contracts, independent OpenAPI validation and generated TypeScript compilation were executed locally. These checks are bounded evidence, not a certification that every possible secret or privacy issue is absent. Test credentials are explicitly synthetic; test signing private keys are generated at runtime.

The test log and GitHub Actions run linked by the delivery report are authoritative for the exact tested SHA. APIShield's local browser run is blocked because the browser download returned an invalid archive; the test remains mandatory in CI. Local PostgreSQL is unavailable. The dedicated disposable PostgreSQL Actions service passed for the exact source commit recorded below; this does not prove production database operations.

## Remaining gaps

- Real IdP onboarding, user provisioning, BFF/OIDC browser session, CSRF and revocation.
- External S3-compatible storage, scanning/retention/deletion and backup operations.
- Remote sandbox/egress/SSRF/breakout evidence; remote execution remains disabled.
- GitHub App installation/webhook/draft-PR product effects and AI-provider quality/cost proof.
- Real source extraction/scanning/agent execution beyond the documented fixture scope.
- Full database/load/worker crash/partition/regional/PITR acceptance. Logical dump/restore is only a bounded CI check.
- Human-adjudicated evaluation corpora, reviewed thresholds and independent legal/domain/operations/accessibility/cost acceptance.

All five projects now have PostgreSQL runtime adapters and dedicated disposable CI proofs. Prior receipts retain their exact historical scope; the main-branch workflows are authoritative for newer commits. No production readiness follows from their success.

G1-E remains OPEN/BLOCKED. No production deployment, customer data, paid provider calls or product auto-merge is introduced.

## GitHub verification receipt

Source commit: `3e27d8f7569d699e85a69e4eb210deb3901e3d8c`. These results cover that exact implementation; later commits require their own workflow results.

Application test result: 29 passed.

- [G1 Contract Verification](https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai/actions/runs/37883263861): **success**.
- [AccessFix MVP Application CI](https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai/actions/runs/37883263893): **success**.

## PostgreSQL and worker lease continuation

Added a separately migrated non-owner adapter with forced RLS, transaction-local tenants, conservative advisory serialization and allowlisted worker claims. Actual ScanWorker completion/failure now propagates its claimed lease value. A regression test prevents stale workers from changing reclaimed jobs. Dedicated CI must pass before this adapter is marked verified; see ADR 0002.

## Main runtime and recovery continuation

The owner now authorizes engineering directly on main. Tenant JWTs must be UUIDs; unprovisioned opaque subjects fail membership checks before SQL. Dedicated PostgreSQL workflows now include logical dump/restore into a fresh database, exact table-data digest comparison, column/constraint/RLS flag comparison and a restored non-owner membership/RLS test. This is not PITR, regional failover, production RTO/RPO or operations acceptance.

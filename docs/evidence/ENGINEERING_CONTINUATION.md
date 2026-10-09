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

The test log and GitHub Actions run linked by the delivery report are authoritative for the exact tested SHA. APIShield's local browser run is blocked because the browser download returned an invalid archive; the test remains mandatory in CI. Local PostgreSQL is unavailable; the runtime proof must pass in the dedicated CI service before that adapter is claimed verified.

## Remaining gaps

- Real IdP onboarding, BFF/OIDC browser session, CSRF, revocation and provisioning.
- External S3-compatible storage, scanning/retention/deletion and backup/restore.
- Remote sandbox/egress/SSRF/breakout evidence; execution remains disabled.
- GitHub App installation/webhook/draft-PR effects and AI-provider quality/cost proof.
- Full PostgreSQL runtime adapters for AccessFix, SpecForge, AgentTest and DataReconcile.
- Real source extraction/scanning/agent execution beyond the synthetic fixture scope.
- Legal/domain/operations/accessibility/cost and independent reviewer acceptance.

G1-E remains OPEN/BLOCKED. No production deployment, customer data, paid provider calls or product auto-merge is introduced.

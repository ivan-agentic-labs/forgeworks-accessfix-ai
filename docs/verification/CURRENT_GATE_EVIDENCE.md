# Current G1/G2 evidence — 2026-10-09

The owner authorizes engineering directly on main. Owner design approval is permission to proceed; it is not an independent domain/security/legal signoff or a G1-E test result. Five repositories remain independent/private. No production deployment or customer data is included.

| Area | Status | Evidence and limit |
|---|---|---|
| G2 repository bootstrap | VERIFIED | Independent repositories, blueprint documentation, contracts, engineering config, SDK and Actions; committed contents read back from GitHub. |
| Contract semantics/client | VERIFIED, scoped | Independent OpenAPI validator, event-schema checks, generated TypeScript compilation and selected runtime response validation. This does not prove all application response paths. |
| Implemented PostgreSQL MVP runtime | VERIFIED, disposable | Migrations 001/002, non-owner runtime role, forced tenant RLS, negative access and product-specific concurrent commands. Design-candidate schema/FK addendum is not applied or accepted by these tests. |
| Logical restore | VERIFIED, disposable | Fresh database dump/restore, table digests, columns, constraints, RLS flags and restored non-owner membership/context behavior. Not PITR, regional failover or production RTO/RPO. |
| JWT/OIDC | PARTIAL | Fixed algorithms, mandatory claims/UUID tenant, expiry/issuer/audience checks, offline key rotation and explicit configuration. Real IdP sessions, provisioning, BFF, CSRF and revocation remain open. |
| Storage/real source bytes | PARTIAL | APIShield local bytes and DataReconcile/AgentTest persisted report/export downloads have integrity evidence. External storage scanning, retention/deletion and source/dataset ingestion remain open. |
| Remote sandbox/provider/GitHub App | BLOCKED | Remote execution/effects fail closed. No independent escape/egress/SSRF proof, installed product GitHub App or real provider quality/cost proof. |
| Domain/privacy/operations/acceptance | OPEN | Human-adjudicated corpus/thresholds, legal/domain/accessibility review, independent signoff and production operating evidence are not supplied. |
| G1-E overall | OPEN/BLOCKED | Individual test success is not whole-gate acceptance. |

## Exact source receipt

Source: `65bc8f36e594e8f84b0b1b2403cee6b67e8ecd50`. This immutable receipt covers that exact source, including synthetic/disposable limits. Later engineering commits require their own CI results; current main workflow status is authoritative for those commits.

- [AccessFix MVP Application CI](https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai/actions/runs/37888159237): **success** at `65bc8f36e594e8f84b0b1b2403cee6b67e8ecd50`.
- [G1 Contract Verification](https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai/actions/runs/37888159283): **success** at `65bc8f36e594e8f84b0b1b2403cee6b67e8ecd50`.
- [AccessFix PostgreSQL Runtime Proof](https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai/actions/runs/37888159273): **success** at `65bc8f36e594e8f84b0b1b2403cee6b67e8ecd50`.

- AccessFix MVP Application CI: ======================== 35 passed, 1 skipped in 2.91s =========================
- AccessFix PostgreSQL Runtime Proof: 1 passed in 1.15s
- AccessFix PostgreSQL Runtime Proof: {"check": "disposable logical restore and restored membership/RLS", "limits": "Not PITR, regional failover, production RTO/RPO or operational signoff", "result": "PASS", "rows": 12, "tables": 9}

## Current product scope

Disposable logical restore verification now compares actual tenant RLS policy expressions/role bindings, table grants, and non-internal trigger definitions/functions, in addition to row digests, columns, constraints and RLS flags. This remains a logical disposable proof, not PITR, regional failover or production operating acceptance.

Fixture ownership/scan/retest/review state and fenced durable worker leases. Remote browser scans remain blocked; fixture findings are not WCAG certification.

## Remaining dependency and implementation register

1. Configure a real IdP and provisioned internal identities; finish BFF/session/CSRF/revocation and test them. This includes unfinished code, not only credentials.
2. Configure external private storage/scanning/retention/deletion and implement remaining source/dataset/upload adapters; do not treat placeholder metadata or quarantined objects as verified bytes.
3. Supply an isolated runner/network policy and product GitHub App configuration; implement and prove sandbox, webhook/revocation and approval-bound remote effects before enabling them.
4. Supply approved evaluation corpora/thresholds and provider budget; implement real source/scanner/agent paths and establish observed quality/cost/load/recovery results.
5. Obtain domain/legal/privacy/operations/independent acceptance. Production remains outside this authorized execution scope.

No background completion, production readiness or full-G1-E PASS is asserted.

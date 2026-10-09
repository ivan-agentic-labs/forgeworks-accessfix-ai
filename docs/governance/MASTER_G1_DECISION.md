# ForgeWorks AI — G1 closure decision (all five products)

## Decision
- **Five product architecture documents:** consolidated into one canonical handoff candidate, with separate per-product boundaries.
- **G1-D (design review): CONDITIONAL / PENDING SIGNOFF** across all five. Technical default decisions are documented, but unsigned domain and owner decisions cannot be fabricated.
- **G1-E (enforcement/runtime evidence): BLOCKED / NOT RUN** on critical PostgreSQL, independent OpenAPI conformance, real IdP, runner sandbox, legal/domain/operations proof.
- **G2:** no application implementation or GitHub write was initiated here. Product implementation should be limited to a synthetic-only branch after G1-D signoff; no real customer data, code execution, finance mutation, or public release until later security gates pass.

## Evidence coverage matrix
| Area | Offline evidence | Unverified prerequisite |
|---|---|---|
| Product scope and file manifests | Five canonical project documents | Independent product/domain signoff |
| API contracts | Five OpenAPI parsed/checked with available tools | Independent OAS validator, complete generated client compile + interoperability |
| Domain events | JSON Schema checks, event names | Operational message delivery, versioning/compatibility |
| Database | Table/FK/RLS/grant inspection, 16 FK candidates separately flagged | Live DDL execution, data migrations, FK semantics, two-tenant RLS, concurrency |
| Identity and authorization | OIDC+BFF trust boundary documented, membership grants reduced | IdP configuration, provisioning workflows, CSRF tests, access-control runtime |
| Sandbox | Threat model and fail-closed design | Independent runner isolation/egress verification |
| Data, legal, finance, accessibility | documented no-go rules | signed responsible reviewers, privacy/DPA/license and live evidence |
| Release / DR / cost | design runbooks and gate | restore drill, vendor quote, telemetry benchmark, approved budget |

## Open decisions
OD-01–OD-09 in `shared/08_OWNER_DECISION_REGISTER.md` remain **OPEN**. Especially identity provisioning and proposed FK delete/cascade semantics need review. Do not present signed decisions, independent testing or 100% validation without results.

## Acceptance rule
**No false-green:** each G1 claim needs criterion, method, dated logs, exact source hash, reviewer, outcome, and residual risk. The final report will therefore label offline checks `PASS_STATIC_LIMITED` and unavailable tests `NOT_RUN`.

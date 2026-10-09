# accessfix-ai — G1-D / G1-E decision
**G1-D: CONDITIONAL REVIEW, NOT SIGNED. G1-E: BLOCKED (missing external/runtime evidence).**

**Required domain signoff:** domain ownership validation, browser isolation, DOM-to-source mapping, human accessibility testing.
**Fail-closed constraint:** No unauthorised URL scanning; automated a11y results are not full WCAG conformance.

Canonical implementation-input files are `contracts/openapi.yaml`, `contracts/events.schema.json`, `docs/verification/sql-candidates/00_role_candidate.sql`, `docs/verification/sql-candidates/10_schema_candidate.sql`, `docs/verification/sql-candidates/20_grants_candidate.sql`, and the **unapproved** `docs/verification/sql-candidates/30_fk_addendum_REVIEW_ONLY.sql`.

The `30_` file contains proposed composite FKs only. **Do not apply automatically**, migrate real data, or mark it approved before domain/cardinality/delete-semantics review and live PostgreSQL tests. It is deliberately not merged into `10_schema_candidate.sql`.

Required before G1-E PASS: semantic OpenAPI validator+client compilation, PostgreSQL empty-DB migration and two-tenant negative tests, ownership/membership authorization checks, identity provider integration, sandbox escape/egress tests where relevant, and production budget/privacy/domain review.

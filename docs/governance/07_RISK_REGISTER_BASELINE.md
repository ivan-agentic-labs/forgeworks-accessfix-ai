# Findings, conflicts, and disposition (no papered-over blockers)

| Finding | Evidence/observation | Remediation in this package | Remaining limitation | Status |
|---|---|---|---|---|
| GEN-01 Conflicting historic designs | v4.3 historical docs + v4.5 candidate specs not combined under single precedence | `01_SOURCE_OF_TRUTH.md` and canonical path tree; historical frozen separately | Founder design-owner signoff needed | DESIGN ADDRESSED |
| GEN-02 RLS is not authorization | candidate policies use app-set tenant context; owner/BYPASSRLS bypass possible | role matrix, transaction semantics, attack test plan | PG server test absent | BLOCKED |
| GEN-03 SQL candidate not migration | SQLAlchemy-compiled DDL without role grants/reversible migrations | reject direct production execution, prescribe migration/role/restore proof | live SQL not executed | BLOCKED |
| GEN-04 Full OAS conformance missing | type-only generator passed but external validator unavailable | freeze OAS 3.1.2 with explicit test gate; preserve original specs | independent SDK/validator not run | BLOCKED |
| GEN-05 Operations and economics unmeasured | no procurement or customer load evidence | vendor option requirements, bill-of-materials, unit cost and restore gates | budget/vendor selection pending | OPEN_DECISION |
| GEN-06 Legal and retention unsanctioned | controller/processor, licenses, policy lengths undetermined | privacy checklist with data-class classification and lawful deletion constraints | counsel/founder approval pending | OPEN_DECISION |
| GEN-07 Collection pagination semantics | 7 P0 list operations already have `cursor`, `limit`, and page schema (`items`, `next_cursor`, `has_more`) | avoid false gap; explicitly bind cursor to tenant+filters and stable ordering in implementation tests | runtime tamper/stable-pagination check absent | DESIGN_SPECIFIED; TEST_NOT_RUN |
| GEN-08 Auth API vs BFF session split | bearer OAS server, BFF session specified only in markdown | BFF separation clarified, negative test plan | real IdP/session tests pending | BLOCKED |
| GEN-09 External side-effects need evidence | draft PR and finance finalization cannot be rolled back by DB rollback alone | approval/version, outbox, inbox, effect ledger and recovery rules | provider timeout tests pending | BLOCKED |
| GEN-10 Company-level customer acceptance | P0 designs based on hypothesis, no verified customers | ICP + outcome/proof in each product review | interviews and signoff pending | OPEN_DECISION |
| GEN-11 Legacy report download | DataReconcile legacy GET deprecated in original OAS | document migration to artifact download-intent, no silent deletion | compatibility/sunset approval pending | OPEN_DESIGN |
| GEN-12 Brand/license/trademark | ForgeWorks AI is a working project label | no public license inferred or brand availability claimed | trademark/domain/licensing decision open | OPEN_DECISION |

Severity P0 blockers: GEN-02, GEN-03, GEN-04, GEN-05/06 for customer data, GEN-08 for auth, and per-product isolation/domain signoffs. Adding documents does not convert `BLOCKED` to `PASS`.

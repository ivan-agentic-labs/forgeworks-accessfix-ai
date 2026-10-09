# AccessFix AI — Product Design Review (canonical summary)
**Status:** `DESIGN REVIEW CANDIDATE`. G1 domain signoff `BLOCKED`. This note **does not claim tested functionality**.

## Purpose and scope
**ICP:** Web engineering teams responsible for owned websites and code repositories.

**P0 workflow:** Prove site ownership → private browser scan → findings with evidence → map to source → propose fix → visual and axe retests → manual review → draft PR.

**Explicit exclusions:** No scanning arbitrary unowned sites, no automated WCAG compliance certification, no inaccessible site auto-patching without review.

**Subsystems:** Domain verification; Playwright+axe sandbox; DOM/source map; WCAG coverage; patch planner; manual review/PR.

## API inventory (as currently specified)
| Method/path | `operationId` | Scope |
|---|---|---|
| `POST /v1/sites/verification-challenges` | `post_v1_sites_verification_challenges` | `site:verify` |
| `POST /v1/sites/{site_id}/verify` | `post_v1_sites_site_id_verify` | `site:verify` |
| `POST /v1/sites/{site_id}/scans` | `post_v1_sites_site_id_scans` | `scan:start` |
| `GET /v1/scans/{scan_id}/findings` | `get_v1_scans_scan_id_findings` | `scan:read` |
| `POST /v1/findings/{finding_id}/fix-proposals` | `post_v1_findings_finding_id_fix_proposals` | `patch:create` |
| `POST /v1/fix-proposals/{proposal_id}/reviews` | `post_v1_fix_proposals_proposal_id_reviews` | `patch:review` |
| `POST /v1/fix-proposals/{proposal_id}/pull-requests` | `post_v1_fix_proposals_proposal_id_pull_requests` | `github:write` |
| `POST /v1/artifacts/upload-intents` | `post__v1_artifacts_upload_intents` | `artifact:create` |
| `POST /v1/artifacts/{artifact_id}/commit` | `post__v1_artifacts_artifact_id_commit` | `artifact:commit` |
| `GET /v1/artifacts/{artifact_id}` | `get__v1_artifacts_artifact_id` | `artifact:read` |
| `POST /v1/artifacts/{artifact_id}/download-intents` | `post__v1_artifacts_artifact_id_download_intents` | `artifact:download` |
| `GET /v1/jobs/{job_id}` | `get__v1_jobs_job_id` | `job:read` |

`openapi.yaml` is the source. These routes are not running. Remaining contract hardening: independent validator and SDK; verify existing cursor pagination semantics in runtime; security tests and example/runtime parity.

## Database inventory and handling
From candidate SQL (18 tables): `tenants`, `users`, `artifact_references`, `audit_events`, `idempotency_records`, `inbox_receipts`, `jobs`, `memberships`, `outbox_events`, `retest_results`, `scan_targets`, `sites`, `scan_jobs`, `verification_challenges`, `findings`, `fix_proposals`, `source_mappings`, `manual_reviews`.

- Keep physical table names from `docs/verification/sql-candidates/10_schema_candidate.sql` as **candidate canonical**; historical aliases may not be implemented simultaneously.
- Apply `tenant_id` composite relations, invariant constraints and optimistic version where review/approval is relevant.
- Validate DDL in disposable PostgreSQL with owned migration role, nonowner runtime login role, multiple tenants; DDL presently unexecuted.

## Product-specific invariants and required negative proofs
| ID | Invariant | Negative case required | Evidence |
|---|---|---|---|
| `AF-INV-01` | Site verification bound to domain/challenge and expires | Forged DNS/HTML proof or stale verification rejected | Runtime test + reviewer signoff |
| `AF-INV-02` | Every URL and redirect passes DNS/network egress guard | Private/link-local/metadata/IPv6/redirect/rebinding attack blocked | Runtime test + reviewer signoff |
| `AF-INV-03` | Auto scan does not imply complete accessibility conformance | Unknown/manual checkpoints clearly marked NOT ASSESSED | Runtime test + reviewer signoff |
| `AF-INV-04` | Fix review anchored to proposal version and code branch | Stale review or visual regression prevents PR creation | Runtime test + reviewer signoff |

## Modules/files planned for ownership (domain and adapters)
- `apps/api/src/accessfix_ai/domain/entities.py`
- `apps/api/src/accessfix_ai/infrastructure/persistence/models.py`
- `apps/api/src/accessfix_ai/infrastructure/persistence/repositories.py`
- `apps/api/src/accessfix_ai/infrastructure/llm/provider_adapter.py`
- `apps/api/src/accessfix_ai/domain/target_policy.py`
- `apps/api/src/accessfix_ai/domain/findings.py`
- `apps/api/src/accessfix_ai/domain/coverage_policy.py`
- `apps/api/src/accessfix_ai/domain/manual_review_policy.py`
- `apps/api/src/accessfix_ai/application/commands/request_verification.py`
- `apps/api/src/accessfix_ai/application/commands/verify_site.py`
- `apps/api/src/accessfix_ai/application/commands/start_scan.py`
- `apps/api/src/accessfix_ai/application/commands/approve_fix.py`
- `apps/api/src/accessfix_ai/infrastructure/browser/isolated_playwright.py`
- `apps/api/src/accessfix_ai/infrastructure/browser/axe_adapter.py`
- `apps/api/src/accessfix_ai/infrastructure/network/egress_guard.py`
- `apps/api/src/accessfix_ai/infrastructure/source_map/dom_to_source.py`
- `apps/api/src/accessfix_ai/infrastructure/github/draft_pr_writer.py`
- `apps/api/src/accessfix_ai/application/commands/commit_artifact.py`
- `apps/api/src/accessfix_ai/infrastructure/storage/object_store.py`
- `apps/api/src/accessfix_ai/infrastructure/security/tenant_context.py`
- `apps/api/src/accessfix_ai/infrastructure/persistence/outbox.py`

## Failure semantics
Ownership unverifiable: deny scan; source map unknown: report finding only, no patch. If downstream AI/provider fails, persist recoverable explicit job state and do not fabricate a successful output. Remote writes require `approval_snapshot` and idempotent effect ledger.

## Evidence and customer acceptance
**Required positive proof:** Produces reproducible findings with URLs/evidence and verified patches where source mapping supported; manual review tracked.

**Main threats:** Browser isolation, SSRF, font/color false positives, DOM-to-source mapping ambiguity, authenticated page secrets.

**Data/IP/approval:** Open-source axe/Playwright obligations; scan content ownership and privacy approval.

## P0 gates and signoff
- Founder/product owner: validates use-case acceptance from qualified user/buyer; **OPEN**.
- API reviewer: external OAS validation, SDK build, authorization negative tests; **NOT RUN**.
- DB/security reviewer: two-tenant SQL execution, constraints, RLS, IAM and sandbox where required; **NOT RUN**.
- Domain specialist: accessibility, finance, graders, provenance, GitHub contract per product; **OPEN**.
- Ops owner: cost/vendor, data policy, restore and incident evidence; **OPEN**.

**Outcome:** Documentation improved and canonical routes/tables inventoried; no independent product-domain approval or G1 PASS granted.
